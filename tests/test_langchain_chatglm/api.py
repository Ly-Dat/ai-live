import json, logging
import requests

# from utils.common import Common
# from utils.logger import Configure_logger


class Langchain_ChatGLM:
    def __init__(self, data):
        # self.common = Common()
        # Log file path
        # file_path = "./log/log-" + self.common.get_bj_time(1) + ".txt"
        # Configure_logger(file_path)

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

            logging.debug(ret)
            logging.info(f"Local knowledge base list:{ret['data']}")

            return ret['data']
        except Exception as e:
            logging.error(e)
            return None


    def get_resp(self, prompt):
        """Request the corresponding API and get the return value

        Args:
            prompt (str): Your question

        Returns:
            str: Returned text answer
        """
        try:
            if self.chat_type == "模型":
                data_json = {
                    "question": prompt, 
                    "streaming": False,
                    "history": self.history
                }
                url = self.api_ip_port + "/chat"
            elif self.chat_type == "知识库":
                data_json = {
                    "knowledge_base_id": self.knowledge_base_id,
                    "question": prompt, 
                    "streaming": False,
                    "history": self.history
                }

                url = self.api_ip_port + "/local_doc_qa/local_doc_chat"
            elif self.chat_type == "必应":
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

            logging.debug(ret)
            if self.chat_type == "问答库" or self.chat_type == "必应":
                logging.info(f'Source:{ret["source_documents"]}')

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
        "api_ip_port": "http://127.0.0.1:7861",
        # Model/knowledge base/Bing
        "chat_type": "必应",
        "knowledge_base_id": "ikaros",
        "history_enable": True,
        "history_max_len": 300
    }
    langchain_chatglm = Langchain_ChatGLM(data)


    if data["chat_type"] == "模型":
        logging.info(langchain_chatglm.get_resp("Can you play a catgirl and add meow after every sentence"))
        logging.info(langchain_chatglm.get_resp("Good morning"))
    elif data["chat_type"] == "知识库":  
        langchain_chatglm.get_list_knowledge_base()
        logging.info(langchain_chatglm.get_resp("Who does Icarus like"))
    # please set BING_SUBSCRIPTION_KEY and BING_SEARCH_URL in os ENV
    elif data["chat_type"] == "必应":  
        logging.info(langchain_chatglm.get_resp("Who is Icarus"))
    