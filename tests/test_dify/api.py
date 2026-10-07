import json, logging
import re, requests
import traceback
from urllib.parse import urljoin
import sys
sys.path.insert(1, "../../utils")
#from utils.common import Common
from loguru import logger


class Dify:
    def __init__(self, data):
        #self.common = Common()
        self.config_data = data

        self.conversation_id = ""

        logger.debug(self.config_data)


    def get_resp(self, data):
        """Request the corresponding API and get the return value

        Args:
            data (dict): JSON data containing the question

        Returns:
            str: Returned text answer
        """
        try:
            resp_content = None

            if self.config_data["type"] == "聊天助手":
                API_URL = urljoin(self.config_data["api_ip_port"], '/v1/chat-messages')

                data_json = {
                    "inputs": {},
                    "query": data["prompt"],
                    # Blocking mode
                    "response_mode": "blocking",
                    # Conversation ID; to continue a conversation based on previous chat history, you must pass the conversation_id of the previous message.
                    "conversation_id": self.conversation_id,
                    # Whether the username is case-sensitive depends on the situation; unified for now for stability
                    "user": "test"
                }
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.config_data["api_key"]}'
                }
                
                response = requests.request("POST", API_URL, headers=headers, json=data_json)
                resp_json = json.loads(response.content)
                
                logger.debug(f"resp_json={resp_json}")

                if "answer" in resp_json:
                    resp_content = resp_json["answer"]

                    # Whether to record history
                    if self.config_data["history_enable"]:
                        self.conversation_id = resp_json["conversation_id"]
                else:
                    logger.error(f"Failed to get the LLM response.{resp_json}")
                    return None

                return resp_content
            
        except Exception as e:
            logger.error(traceback.format_exc())

        return None

if __name__ == '__main__':


    data = {
        "api_ip_port": "http://172.26.189.21/v1",
        "type": "聊天助手",
        "api_key": "app-64xu0vQjP2kxN4DKR8Ch7ZGY",
        "history_enable": True
    }

    # Instantiate and call
    dify = Dify(data)
    logger.info(dify.get_resp({"prompt": "Can you play a catgirl and add meow after every sentence"}))
    logger.info(dify.get_resp({"prompt": "Good morning"}))
