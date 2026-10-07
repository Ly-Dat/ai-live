import json
import requests
from urllib.parse import urljoin
import re

from utils.my_log import logger

def extract_and_parse_json(data_string):
    # If data_string is bytes or bytearray, decode it to a string
    if isinstance(data_string, (bytes, bytearray)):
        data_string = data_string.decode('utf-8')

    # Use a regular expression to match the JSON part
    match = re.search(r'{.*}', data_string)
    if match:
        json_string = match.group(0)
        try:
            return json.loads(json_string)
        except json.JSONDecodeError:
            logger.error("Invalid JSON string: %s", json_string)
            return None
    
# from utils.common import Common
# from utils.logger import Configure_logger


class Langchain_ChatChat:
    def __init__(self, data):
        # self.common = Common()
        # Log file path
        # file_path = "./log/log-" + self.common.get_bj_time(1) + ".txt"
        # Configure_logger(file_path)

        self.api_ip_port = data["api_ip_port"]
        self.chat_type = data["chat_type"]
        self.config_data = data

        self.history = []


    # Get the knowledge base list
    def get_list_knowledge_base(self):
        url = urljoin(self.api_ip_port, "/knowledge_base/list_knowledge_bases")
        try:
            response = requests.get(url)
            response.raise_for_status()  # Check the response status code

            result = response.content
            ret = extract_and_parse_json(result)

            if ret is None:
                logger.error("Failed to parse JSON: %s", result)
                # handle error here
            else:
                # continue with your code using parsed_json
                logger.debug(ret)
                logger.info(f"Local knowledge base list:{ret['data']}")

            return ret['data']
        except Exception as e:
            logger.error(e)
            return None


    def get_resp(self, prompt):
        """Request the corresponding API and get the return value

        Args:
            prompt (str): Your question

        Returns:
            str: Returned text answer
        """
        try:
            if self.chat_type == "Model":
                data_json = self.config_data["llm"]
                
                url = self.api_ip_port + "/chat/chat"
            elif self.chat_type == "Knowledge base":
                data_json = self.config_data["knowledge_base"]

                url = self.api_ip_port + "/chat/knowledge_base_chat"
            elif self.chat_type == "Search engine":
                data_json = self.config_data["search_engine"]

                url = self.api_ip_port + "/chat/search_engine_chat"
            else:
                data_json = self.config_data["llm"]
                url = self.api_ip_port + "/chat"

            data_json["query"] = prompt
            data_json["history"] = self.history

            response = requests.post(url=url, json=data_json)
            response.raise_for_status()  # Check the response status code

            result = response.content
            ret = extract_and_parse_json(result)
            if ret is None:
                logger.error("Failed to parse JSON: %s", result)
                # handle error here
            else:
                # continue with your code using parsed_json
                logger.debug(ret)

                if self.chat_type == "Model":
                    resp_content = ret["text"]
                elif self.chat_type == "Knowledge base":
                    resp_content = ret["answer"]
                elif self.chat_type == "Search engine":
                    resp_content = ret["answer"]
                else:
                    resp_content = ret["text"]

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
            logger.error(e)
            return None


if __name__ == '__main__':
    # Configure the log output format
    logger.basicConfig(
        level=logger.DEBUG,  # Set the log level; adjust as needed
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    data = {
        "api_ip_port": "http://127.0.0.1:7861",
        # Model/knowledge base/search engine
        "chat_type": "Model",
        "llm": {
            "stream": False,
            "model_name": "openai-api",
            "temperature": 0.7,
            "max_tokens": 4096,
            "prompt_name": "default"
        },
        "search_engine": {
            "search_engine_name": "metaphor",
            "top_k": 3,
            "stream": False,
            "model_name": "chatglm3-6b-int4",
            "temperature": 0.7,
            "max_tokens": 4096,
            "prompt_name": "default",
            "split_result": False
        },
        "knowledge_base" : {
            "knowledge_base_name": "astro",
            "top_k": 3,
            "score_threshold": 1,
            "stream": False,
            "model_name": "openai-api",
            "temperature": 0.7,
            "max_tokens": 4096,
            "prompt_name": "default"
        },
        "history_enable": True,
        "history_max_len": 300
    }
    langchain_chatchat = Langchain_ChatChat(data)


    if data["chat_type"] == "Model":
        logger.info(langchain_chatchat.get_resp("What is a black hole"))
        logger.info(langchain_chatchat.get_resp("What is a primordial black hole"))
    elif data["chat_type"] == "Knowledge base":  
        langchain_chatchat.get_list_knowledge_base()
        logger.info(langchain_chatchat.get_resp("What is a black hole"))
        logger.info(langchain_chatchat.get_resp("What is a primordial black hole"))
    # please set BING_SUBSCRIPTION_KEY and BING_SEARCH_URL in os ENV
    elif data["chat_type"] == "Search engine":  
        logger.info(langchain_chatchat.get_resp("Who is Icarus"))
        logger.info(langchain_chatchat.get_resp("The English name of Icarus"))
    