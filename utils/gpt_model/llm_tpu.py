import traceback
from gradio_client import Client
import re

from utils.common import Common
from utils.my_log import logger


class LLM_TPU:
    def __init__(self, data):
        self.common = Common()

        self.config_data = data
        self.history = []

        self.history_enable = data["history_enable"]
        self.history_max_len = data["history_max_len"]


    def get_resp(self, data):
        """Request the corresponding API and get the return value

        Args:
            data (dict): Your question, etc.

        Returns:
            str: Returned text answer
        """
        try:
            client = Client(self.config_data["api_ip_port"])

            result = client.predict(
                input=data["prompt"],
                chatbot=self.history,
                max_length=self.config_data["max_length"],
                top_p=self.config_data["top_p"],
                temperature=self.config_data["temperature"],
                api_name="/predict"
            )
            
            response_text = result[-1][1]
            # Remove <p> and </p> tags using regex
            resp_content = re.sub(r'</?p>', '', response_text)

            self.history = result

            # If history is enabled, remember it for me!
            if self.history_enable:
                while True:
                    # Get the character count of all strings in a nested list
                    total_chars = sum(len(string) for sublist in self.history for string in sublist)
                    # If it exceeds the maximum history limit, remove the first element
                    if total_chars > self.history_max_len:
                        self.history.pop(0)
                    else:
                        break

            return resp_content
        except Exception as e:
            logger.error(traceback.format_exc())
            return None

if __name__ == '__main__':
    # Configure the log output format
    logger.basicConfig(
        level=logger.DEBUG,  # Set the log level; adjust as needed
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    data = {
        "api_ip_port": "http://127.0.0.1:8003/",
        "max_length": 1,
        "top_p": 0.8,
        "temperature": 0.95,
        "history_enable": True,
        "history_max_len": 300
    }

    llm_tpu = LLM_TPU(data)
    logger.info(f'{llm_tpu.get_resp("Can you play a catgirl and add meow after every sentence")}')
    logger.info(f'{llm_tpu.get_resp("Good morning")}')

