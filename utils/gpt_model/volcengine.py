import json
import copy
import traceback
from volcenginesdkarkruntime import Ark

from utils.common import Common
from utils.my_log import logger

# Official documentation:https://www.volcengine.com/docs/82379/1302008

class VolcEngine:
    def __init__(self, data):
        self.common = Common()

        self.config_data = data
        
        self.history = []

        try:
            self.client = Ark(api_key=self.config_data["api_key"])
        except Exception as e:
            logger.error(traceback.format_exc())

    def get_resp(self, data: dict, stream: bool=False):
        """Request the corresponding API and get the return value

        Args:
            data (dict): jsonData
            stream (bool, optional): Whether to return as a stream. Defaults to False.

        Returns:
            str: Returned text answer
        """
        try:
            prompt = data["prompt"]
        
            # Prepare messages
            if not self.config_data['history_enable']:
                preset = self.config_data["preset"] or "Please act as an AI and answer my question"
                messages = [
                    {'role': 'system', 'content': preset},
                    {'role': 'user', 'content': prompt}
                ]
            else:
                messages = self.history.copy()
                messages.append({'role': 'user', 'content': prompt})
                messages.insert(0, {'role': 'system', 'content': self.config_data["preset"]})

            logger.debug(f"messages={messages}")

            # Create a chat completion
            response = self.client.chat.completions.create(
                model=self.config_data["model"],
                messages=messages,
                stream=stream
            )

            if response is None:
                return None

            if stream:
                return response

            logger.debug(response)
            resp_content = response.choices[0].message.content

            # Update the history
            if self.config_data['history_enable']:
                self.history.append({'role': 'user', 'content': prompt})
                self.history.append({'role': 'assistant', 'content': resp_content})
                
                # Trim the history
                while sum(len(item['content']) for item in self.history if 'content' in item) > int(self.config_data["history_max_len"]):
                    self.history = self.history[2:]  # Remove the oldest message pair

            return resp_content

        except Exception as e:
            logger.error(f"Error in get_resp: {str(e)}")
            logger.error(traceback.format_exc())
            return None

    # Add the AI reply message to the session to provide contextual memory
    def add_assistant_msg_to_session(self, prompt: str, message: str):
        try:
            # If history is enabled, remember it for me!
            if self.config_data['history_enable']:
                self.history.append({'role': 'user', 'content': prompt})
                self.history.append({'role': 'assistant', 'content': message})
                while True:
                    # Get the character count of all strings in a nested list
                    total_chars = sum(len(item['content']) for item in self.history if 'content' in item)
                    # If it exceeds the maximum history limit, remove the first element
                    if total_chars > int(self.config_data["history_max_len"]):
                        self.history.pop(0)
                        self.history.pop(0)
                    else:
                        break

            logger.debug(f"history={self.history}")

            return {"ret": True}
        except Exception as e:
            logger.error(traceback.format_exc())
            return {"ret": False}

if __name__ == '__main__':
    # Configure the log output format
    logger.basicConfig(
        level=logger.INFO,  # Set the log level; adjust as needed
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    data = {
        "model": "ep-20240904192312-r4rkc",
        "preset": "You are a professional virtual streamer",
        "api_key": "408a2af4-1669-440a-a141-90850e1c615e",
        "history_enable": True,
        "history_max_len": 1024,
        "stream": False
    }
    
    volcengine = VolcEngine(data)

    logger.info(volcengine.get_resp("You are now called Xiaoyi, a catgirl, add meow after every sentence"))
    logger.info(volcengine.get_resp("Good morning, what is your name"))
    