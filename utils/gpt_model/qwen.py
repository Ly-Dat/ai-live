import json
from typing import Dict
import requests
import re
from loguru import logger

from utils.common import Common



def remove_emotion(message: str) -> str:
    """
    Remove the parts describing expressions (e.g. [happy]; requires the AI output format to be fixed)
    """
    pattern = r'\【[^\】^\]]*[\]\】]'
    match = re.findall(pattern, message)
    if not len(match) == 0:
        print(match)
        print(f"emotion:{match[0]}")
        return message.replace(match[0], "")
    else:
        return message


def remove_action(line: str) -> str:
    """
    Remove the parts in parentheses that describe actions (requires the AI output format to be fixed)
    :param line:
    :return:
    """
    line = line.replace("(", "（")
    line = line.replace(")", "）")
    pattern = r'\（[^\（^\）]*\）'
    match = re.findall(pattern, line)
    if len(match) == 0:
        return line
    else:
        print(f"There are {len(match)+1} sentences describing actions")
        for i in range(len(match)):
            print(match[i])
            line = line.replace(match[i], "")
        return line


class Qwen:

    def __init__(self, data):
        self.common = Common()

        self.api_ip_port = data["api_ip_port"]
        self.max_length = data["max_length"]
        self.top_p = data["top_p"]
        self.temperature = data["temperature"]
        self.history_enable = data["history_enable"]
        self.history_max_len = data["history_max_len"]
        self.preset = data["preset"]
        self.history = []


    def construct_query(self, username, prompt: str, **kwargs) -> Dict:
        """Build the request body
        """

        messages = self.history + [{"role": "user", "content": f"{prompt}"}]
        query = {
            "model": "gpt-3.5-turbo",
            "messages": messages,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "stream": False,  # Streaming not enabledAPI
        }

        self.history = self.history + [{"role": "user", "content": prompt}]
        return query


    def construct_observation(self, prompt: str, **kwargs) -> Dict:
        """Build the request body
        """
        embedding = ""
        for key, value in kwargs.items():
            if key == "embedding":
                embedding = value
        messages = self.history + [{"role": "function", "content": prompt}]
        query = {
            "functions": self.functions,
            "system": self.system,
            "model": "gpt-3.5-turbo",
            "messages": messages,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "stream": False,  # Streaming not enabledAPI
        }
        self.history = messages
        return query


    # Call the API and get the returned content
    def get_resp(self, username, prompt):
        # construct query
        query = self.construct_query(username, prompt)

        try:
            response = requests.post(url=self.api_ip_port, json=query)
            response.raise_for_status()  # Check the response status code

            result = response.content
            ret = json.loads(result)
            predictions = "..."

            logger.debug(ret)
            finish_reason = ret['choices'][0]['finish_reason']
            if finish_reason != "":
                predictions = ret['choices'][0]['message']['content'].strip()
                self.history = self.history + [
                    {"role": "assistant", "content": f"{predictions}"}]

                # If history is enabled, remember it for me!
                if self.history_enable:
                    if len(self.history) > self.history_max_len:
                        temp_history = self.history[-self.history_max_len:]
                        if temp_history[0].get("role") != "function":
                            self.history = self.history[-self.history_max_len:]
                else:
                    self.history = []

            return remove_action(remove_emotion(predictions))
        except Exception as e:
            logger.info(e)
            return None


if __name__ == "__main__":
    llm = Qwen
    llm.__init__(llm,
                 {"api_ip_port": "http://localhost:8000/v1/chat/completions",
                    "max_length": 4096,
                    "top_p": 0.5,
                    "temperature": 0.9,
                    "max_new_tokens": 250,
                    "history_enable": True,
                    "history_max_len": 20})
    resp = llm.get_resp(self=llm, prompt="你好")
    print(resp)
