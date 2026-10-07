import json, logging
import requests, time
from requests.exceptions import ConnectionError, RequestException

# from utils.common import Common
# from utils.logger import Configure_logger

# Originally planned to integrate:https://github.com/zhuweiyou/yiyan-api
class Yiyan:
    def __init__(self, data):
        # self.common = Common()
        # # Log file path
        # file_path = "./log/log-" + self.common.get_bj_time(1) + ".txt"
        # Configure_logger(file_path)

        self.config_data = data
        self.type = data["type"]

        self.history = []


    def get_access_token(self):
        """
        Use the API Key and Secret Key to get the access_token, replacing the application API Key and application in the example belowSecret Key
        """
            
        url = f'https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={self.config_data["api"]["api_key"]}&client_secret={self.config_data["api"]["secret_key"]}'
        
        payload = json.dumps("")
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        response = requests.request("POST", url, headers=headers, data=payload)
        return response.json().get("access_token")


    def get_resp(self, prompt):
        """Request the corresponding API and get the return value

        Args:
            prompt (str): Your question

        Returns:
            str: Returned text answer
        """
        try:
            if self.type == "web":
                try:
                    data_json = {
                        "cookie": self.config_data["web"]["cookie"], 
                        "prompt": prompt
                    }

                    # logging.debug(data_json)

                    url = self.config_data["web"]["api_ip_port"] + "/headless"

                    response = requests.post(url=url, data=data_json)
                    response.raise_for_status()  # Check the response status code

                    result = response.content
                    ret = json.loads(result)

                    logging.debug(ret)

                    resp_content = ret['text'].replace('\n', '').replace('\\n', '')

                    # If history is enabled, remember it for me!
                    if self.config_data["history_enable"]:
                        while True:
                            # Get the character count of all strings in a nested list
                            total_chars = sum(len(string) for sublist in self.history for string in sublist)
                            # If it exceeds the maximum history limit, remove the first element
                            if total_chars > self.config_data["history_max_len"]:
                                self.history.pop(0)
                            else:
                                self.history.append({"role": "user", "content": prompt})
                                self.history.append({"role": "assistant", "content": resp_content})
                                break

                    return resp_content
                except ConnectionError as ce:
                    # Handle connection exceptions
                    logging.error(f"Please check whether you have started the server or whether the config matches; connection exception:{ce}")

                except RequestException as re:
                    # Handle other request exceptions
                    logging.error(f"Request exception:{re}")
                except Exception as e:
                    logging.error(e)
            else:
                url = "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions?access_token=" + self.get_access_token()

                data_json = {
                    "messages": self.history + [{"role": "user", "content": prompt}]
                }

                payload = json.dumps(data_json)

                headers = {
                    'Content-Type': 'application/json'
                }
                
                response = requests.request("POST", url, headers=headers, data=payload)
                
                logging.info(payload)
                logging.info(response.text)

                resp_content = json.loads(response.text)["result"]

                # If history is enabled, remember it for me!
                if self.config_data["history_enable"]:
                    while True:
                        # Get the character count of all strings in a nested list
                        total_chars = sum(len(string) for sublist in self.history for string in sublist)
                        # If it exceeds the maximum history limit, remove the first element
                        if total_chars > self.config_data["history_max_len"]:
                            self.history.pop(0)
                        else:
                            self.history.append({"role": "user", "content": prompt})
                            self.history.append({"role": "assistant", "content": resp_content})
                            break

                return resp_content
        except Exception as e:
            logging.error(e)

        return None


if __name__ == '__main__':
    # Configure the log output format
    logging.basicConfig(
        level=logging.DEBUG,  # Set the log level; adjust as needed
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    data = {
        "type": 'api',
        "web": {
            "api_ip_port": "http://127.0.0.1:3000",
            "cookie": ''
        },
        "api": {
            "api_key": "",
            "secret_key": ""
        },
        "history_enable": True,
        "history_max_len": 300
    }
    yiyan = Yiyan(data)


    logging.info(yiyan.get_resp("Can you play a catgirl and add meow after every sentence"))
    time.sleep(1)
    logging.info(yiyan.get_resp("Good morning"))
    