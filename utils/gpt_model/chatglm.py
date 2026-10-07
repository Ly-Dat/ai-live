import json
import requests

from utils.common import Common
from utils.my_log import logger

class Chatglm:
    def __init__(self, data):
        self.common = Common()

        self.api_ip_port = data["api_ip_port"]
        self.max_length = data["max_length"]
        self.top_p = data["top_p"]
        self.temperature = data["temperature"]
        self.history_enable = data["history_enable"]
        self.history_max_len = data["history_max_len"]

        self.history = []


    # Call the chatglm API and get the returned content
    def get_resp(self, prompt):
        data_json = {
            "prompt": prompt, 
            "history": self.history,
            "max_length": self.max_length,
            "top_p": self.top_p,
            "temperature": self.temperature
        }

        try:
            response = requests.post(url=self.api_ip_port, json=data_json)
            response.raise_for_status()  # Check the response status code

            result = response.content
            ret = json.loads(result)

            logger.debug(ret)

            resp_content = ret['response']

            # If history is enabled, remember it for me!
            if self.history_enable:
                while True:
                    # Get the character count of all strings in a nested list
                    total_chars = sum(len(string) for sublist in self.history for string in sublist)
                    # If it exceeds the maximum history limit, remove the first element
                    if total_chars > self.history_max_len:
                        self.history.pop(0)
                    else:
                        self.history.append(ret['history'][-1])
                        break

            return resp_content
        except Exception as e:
            logger.info(e)
            return None