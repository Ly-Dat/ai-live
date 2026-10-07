import json, logging
# pip install undetected_chromedriver platformdirs curl_cffi aiohttp_socks g4f 
import g4f
from g4f.client import Client

# from utils.common import Common
# from utils.logger import Configure_logger


class GPT4Free:
    def __init__(self, data):
        # self.common = Common()
        # Log file path
        # file_path = "./log/log-" + self.common.get_bj_time(1) + ".txt"
        # Configure_logger(file_path)

        self.config_data = data
        self.api_key = None if self.config_data["api_key"] == "" else self.config_data["api_key"]

        # Create a mapping dict
        provider_mapping = {
            "none": None,
            "g4f.Provider.Bing": g4f.Provider.Bing,
            "g4f.Provider.ChatgptAi": g4f.Provider.ChatgptAi,
        }

        proxy = None if data["proxy"] == "" else {"all": data["proxy"]}

        self.client = Client(provider=provider_mapping.get(data["provider"], None), proxies=proxy)

        self.history = []


    def get_resp(self, data):
        """Request the corresponding API and get the return value

        Args:
            data (dict): jsonData

        Returns:
            str: Returned text answer
        """
        try:
            messages = [
                {"role": "system", "content": self.config_data["preset"]}
            ]

            if self.config_data["history_enable"]:
                for message in self.history:
                    messages.append(message)

                messages.append({"role": "user", "content": data["prompt"]})
            else:
                messages.append({"role": "user", "content": data["prompt"]})

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                max_tokens=self.config_data["max_tokens"],
                api_key=self.api_key,
                messages=messages
            )
            resp_content = response.choices[0].message.content

            if self.config_data["history_enable"]:
                if len(self.history) > self.config_data["history_max_len"]:
                    self.history.pop(0)
                while True:
                    # Get the character count of all strings in a nested list
                    total_chars = sum(len(string) for sublist in self.history for string in sublist)
                    # If it exceeds the maximum history limit, remove the first element
                    if total_chars > self.config_data["history_max_len"]:
                        self.history.pop(0)
                    else:
                        self.history.append({"role": "user", "content": data["prompt"]})
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
        "provider": "none",
        "api_key": "",
        "model": "gpt-3.5-turbo",
        "max_tokens": 2048,
        "proxy": "http://127.0.0.1:10809",
        "preset": "你是一个虚拟主播",
        "history_enable": True,
        "history_max_len": 300
    }
    gpt4free = GPT4Free(data)


    logging.info(gpt4free.get_resp({"prompt": "Can you play a catgirl and add meow after every sentence"}))
    logging.info(gpt4free.get_resp({"prompt": "Good morning"}))
    