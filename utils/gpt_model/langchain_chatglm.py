import json
import requests
import traceback

from utils.common import Common
from utils.my_log import logger


class Langchain_ChatGLM:
    def __init__(self, data):
        self.common = Common()

        self.api_ip_port = data["api_ip_port"]
        self.chat_type = data["chat_type"]
        self.knowledge_base_id = data["knowledge_base_id"]
        self.history_enable = data["history_enable"]
        self.history_max_len = data["history_max_len"]

        self.history = []


    # Get the knowledge base list
    def get_list_knowledge_base(self):
        url = self.api_ip_port + "/local_doc_qa/list_knowledge_base"
        try:
            response = requests.get(url)
            response.raise_for_status()  # Check the response status code

            result = response.content
            ret = json.loads(result)

            logger.debug(ret)
            logger.info(f"Local knowledge base list:{ret['data']}")

            return ret['data']
        except Exception as e:
            logger.error(traceback.format_exc())
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
                data_json = {
                    "question": prompt, 
                    "streaming": False,
                    "history": self.history
                }
                url = self.api_ip_port + "/chat"
            elif self.chat_type == "Knowledge base":
                data_json = {
                    "knowledge_base_id": self.knowledge_base_id,
                    "question": prompt, 
                    "streaming": False,
                    "history": self.history
                }

                url = self.api_ip_port + "/local_doc_qa/local_doc_chat"
            elif self.chat_type == "Bing":
                data_json = {
                    "question": prompt, 
                    "history": self.history
                }

                url = self.api_ip_port + "/local_doc_qa/bing_search_chat"
            else:
                data_json = {
                    "question": prompt, 
                    "streaming": False,
                    "history": self.history
                }
                url = self.api_ip_port + "/chat"

            response = requests.post(url=url, json=data_json)
            response.raise_for_status()  # Check the response status code

            result = response.content
            ret = json.loads(result)

            logger.debug(ret)
            if self.chat_type == "Q&A library" or self.chat_type == "Bing":
                logger.info(f'Source:{ret["source_documents"]}')

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
            logger.error(traceback.format_exc())
            return None


# For testing
if __name__ == '__main__':
    # Configure the log output format
    logger.basicConfig(
        level=logger.DEBUG,  # Set the log level; adjust as needed
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    data = {
        "api_ip_port": "http://127.0.0.1:7861",
        # Model/knowledge base/Bing
        "chat_type": "Model",
        "knowledge_base_id": "ikaros",
        "history_enable": True,
        "history_max_len": 300
    }
    langchain_chatglm = Langchain_ChatGLM(data)


    if data["chat_type"] == "Model":
        logger.info(langchain_chatglm.get_resp("Can you play a catgirl and add meow after every sentence"))
        logger.info(langchain_chatglm.get_resp("Good morning"))
    elif data["chat_type"] == "Knowledge base":  
        langchain_chatglm.get_list_knowledge_base()
        logger.info(langchain_chatglm.get_resp("Who does Icarus like"))
    # please set BING_SUBSCRIPTION_KEY and BING_SEARCH_URL in os ENV
    elif data["chat_type"] == "Bing":  
        logger.info(langchain_chatglm.get_resp("Who is Icarus"))
    