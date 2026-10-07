import json, logging, copy
import traceback

from utils.common import Common
from utils.logger import Configure_logger

def convert_cookies(cookies: list) -> dict:
    """Convertcookies"""
    cookies_dict = {}
    for cookie in cookies:
        cookies_dict[cookie["name"]] = cookie["value"]
    return cookies_dict

class TongYi:
    def __init__(self, data):
        self.common = Common()
        # Log file path
        file_path = "./log/log-" + self.common.get_bj_time(1) + ".txt"
        Configure_logger(file_path)

        self.config_data = data
        self.cookie_path = data["cookie_path"]
        self.parentId = None
        self.chatbot = None
        
        self.history = []

        self.cookies_dict = {}

        try:
            if self.config_data["type"] == "web":
                # Non-streaming mode
                import revTongYi.qianwen as qwen
                
                with open(self.cookie_path, "r") as f:
                    self.cookies_dict = convert_cookies(json.load(f))
                self.chatbot = qwen.Chatbot(
                    cookies=self.cookies_dict  # Provided as a dictcookies
                )
                
            elif self.config_data["type"] == "api":
                import dashscope
                
                dashscope.api_key = self.config_data["api_key"]
        except Exception as e:
            logging.error(traceback.format_exc())

    def get_resp(self, prompt):
        """Request the corresponding API and get the return value

        Args:
            prompt (str): Your question

        Returns:
            str: Returned text answer
        """
        try:
            if self.config_data["type"] == "web":
                if self.parentId:
                    ret = self.chatbot.ask(prompt=prompt, parentId=self.parentId)
                else:
                    ret = self.chatbot.ask(prompt=prompt)
                
                # logging.info(ret)
                
                # Whether to enable context memory
                if self.config_data['history_enable']:
                    self.parentId = ret['msgId']
                resp_content = ret['content'][0]

                return resp_content
            elif self.config_data["type"] == "api":
                from http import HTTPStatus
                from dashscope import Generation
                from dashscope.api_entities.dashscope_response import Role
                
                if self.config_data['history_enable'] == False:
                    messages = [{'role': Role.SYSTEM, 'content': self.config_data["preset"]},
                                    {'role': Role.USER, 'content': prompt}]
                else:
                    messages = copy.copy(self.history)
                    messages.append({'role': Role.USER, 'content': prompt})
                    messages.insert(0, {'role': Role.SYSTEM, 'content': self.config_data["preset"]})
                
                logging.debug(f"messages={messages}")

                response = Generation.call(
                    self.config_data['model'],
                    messages=messages,
                    result_format='message',  # set the result to be "message" format.
                    temperature=self.config_data['temperature'],
                    top_p=self.config_data['top_p'],
                    top_k=self.config_data['top_k'],
                    enable_search=self.config_data['enable_search'],
                    max_tokens=self.config_data['max_tokens'],
                )
                if response.status_code == HTTPStatus.OK:
                    logging.debug(response)

                    resp_content = response.output.choices[0]['message']['content']
                    
                    if self.config_data['history_enable']:
                        self.history.append({'role': Role.USER, 'content': prompt})
                        self.history.append({'role': response.output.choices[0]['message']['role'],
                                        'content': resp_content})
                        while True:
                            # Get the character count of all strings in a nested list
                            total_chars = sum(len(item['content']) for item in self.history if 'content' in item)
                            # If it exceeds the maximum history limit, remove the first element
                            if total_chars > int(self.config_data["history_max_len"]):
                                self.history.pop(0)
                                self.history.pop(0)
                            else:
                                break
                        
                    return resp_content
                else:
                    logging.error(f'Request id: {response.request_id}, Status code: {response.status_code}, error code: {response.code}, error message: {response.message}')
                    return None
        except Exception as e:
            logging.error(traceback.format_exc())
            return None


if __name__ == '__main__':
    # Configure the log output format
    logging.basicConfig(
        level=logging.INFO,  # Set the log level; adjust as needed
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    data = {
        "cookie_path": 'cookies.json',
        "type": 'api',
        "model": "qwen-max",
        "preset": "你是一个专业的虚拟主播",
        "api_key": "sk-",
        "temperature": 0.9,
        "top_p": 0.9,
        "top_k": 3,
        "enable_search": True,
        "max_tokens": 1024,
        "history_enable": True,
        "history_max_len": 20,
    }
    
    tongyi = TongYi(data)


    logging.info(tongyi.get_resp("You are now called Xiaoyi, a catgirl, add meow after every sentence"))
    logging.info(tongyi.get_resp("Good morning, what is your name"))
    