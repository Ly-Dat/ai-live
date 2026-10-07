import json
import requests
import traceback
from urllib.parse import urljoin
from loguru import logger

from utils.common import Common

class Dify:
    def __init__(self, data: dict):
        self.config_data = data

        self.conversation_id = ""

        # logger.debug(self.config_data)

        self.common = Common()

    def replace_variables(self, text, variables):
        import re

        for key, value in variables.items():
            text = re.sub(f'{{{{{key}}}}}', value, text)
        return text

    def get_resp(self, data: dict, stream: bool = False):
        """Request the corresponding API and get the return value

        Args:
            data (dict): JSON data containing the question
            stream (bool): Whether to return as a stream

        Returns:
            str: Returned text answer
        """
        try:
            resp_content = None

            if self.config_data["type"] == "Chat assistant":
                API_URL = urljoin(self.config_data["api_ip_port"], '/v1/chat-messages')

                if stream:
                    data_json = {
                        "inputs": {},
                        "query": data["prompt"],
                        # Blocking mode
                        "response_mode": "streaming",
                        # Conversation ID; to continue a conversation based on previous chat history, you must pass the conversation_id of the previous message.
                        "conversation_id": self.conversation_id,
                        # Whether the username is case-sensitive depends on the situation; unified for now for stability
                        "user": "test"
                    }
                else:
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

                if response is None:
                    return None

                # If streaming, return directly
                if stream:
                    return response

                resp_json = json.loads(response.content)
                
                logger.debug(f"[dify] resp_json={resp_json}")

                if "answer" in resp_json:
                    resp_content = resp_json["answer"]

                    # Whether to record history
                    if self.config_data["history_enable"]:
                        self.conversation_id = resp_json["conversation_id"]
                else:
                    logger.error(f"[dify] Failed to get the LLM response.{resp_json}")
                    return None

                return resp_content
            elif self.config_data["type"] == "Workflow":
                API_URL = urljoin(self.config_data["api_ip_port"], '/v1/workflows/run')

                variables = {
                    "cur_time": self.common.get_bj_time(0),
                    "comment": data['prompt'],
                }

                custom_params = self.replace_variables(self.config_data['custom_params'], variables)
                custom_params = json.loads(custom_params)

                if stream:
                    data_json = {
                        "inputs": custom_params,
                        # Blocking mode
                        "response_mode": "streaming",
                        # Whether the username is case-sensitive depends on the situation; unified for now for stability
                        "user": "test"
                    }
                else:
                    data_json = {
                        "inputs": custom_params,
                        # Blocking mode
                        "response_mode": "blocking",
                        # Whether the username is case-sensitive depends on the situation; unified for now for stability
                        "user": "test"
                    }
                    logger.debug(f"[dify] data_json={data_json}")
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.config_data["api_key"]}'
                }
                
                response = requests.request("POST", API_URL, headers=headers, json=data_json)

                if response is None:
                    return None

                # If streaming, return directly
                if stream:
                    return response
                
                resp_json = json.loads(response.content)
                
                logger.debug(f"[dify] resp_json={resp_json}")

                if "data" in resp_json:
                    if "outputs" in resp_json["data"]:
                        resp_content_dict = resp_json["data"]["outputs"]
                        if "text" in resp_content_dict:
                            resp_content = resp_content_dict["text"]
                else:
                    logger.error(f"[dify] Failed to get the LLM response.{resp_json}")
                    return None

                return resp_content
        except Exception as e:
            logger.error(traceback.format_exc())

        return None
    
    # Add the AI reply message to the session to provide contextual memory
    def add_assistant_msg_to_session(self, conversation_id: str):
        try:
            # If history is enabled, remember it for me!
            if self.config_data['history_enable']:
                self.conversation_id = conversation_id
            return {"ret": True}
        except Exception as e:
            logger.error(traceback.format_exc())
            return {"ret": False}

if __name__ == '__main__':
    data = {
        "api_ip_port": "http://172.26.189.21/v1",
        "type": "Chat assistant",
        "api_key": "app-64xu0vQjP2kxN4DKR8Ch7ZGY",
        "history_enable": True
    }

    # Instantiate and call
    dify = Dify(data)
    logger.info(dify.get_resp({"prompt": "Can you play a catgirl and add meow after every sentence"}))
    logger.info(dify.get_resp({"prompt": "Good morning"}))
