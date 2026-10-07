import os
import qianfan
import requests, copy
import json, logging
import traceback

class My_QianFan():
    def __init__(self, data):
        self.config_data = data
        self.history = []
        
        try:
            os.environ["QIANFAN_ACCESS_KEY"] = data["access_key"]
            os.environ["QIANFAN_SECRET_KEY"] = data["secret_key"]
            # Select the application to use by App Id
            # This parameter is optional; if not provided, the SDK automatically selects the most recently created application
            # os.environ["QIANFAN_APPID"]="44916356"
        except Exception as e:
            logging.error("Qianfan large model, configuration error, please check whether the config has a format problem!")
            logging.error(traceback.format_exc())

    def get_resp(self, prompt):
        """Request the corresponding API and get the return value

        Args:
            prompt (str): Your question

        Returns:
            str: Returned text answer
        """
        try:
            chat_comp = qianfan.ChatCompletion(model=self.config_data["model"])
            tmp_history = copy.copy(self.history)
            tmp_history.append({
                "role": "user",
                "content": prompt
            })
            logging.debug(f"History={tmp_history}")
            resp = chat_comp.do(messages=tmp_history, top_p=self.config_data["top_p"], temperature=self.config_data["temperature"], penalty_score=self.config_data["penalty_score"])

            logging.debug(resp)
            logging.info(f'tokenTotal consumption:{resp["usage"]["total_tokens"]}')

            resp_content = resp["result"]
        
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
            logging.error(traceback.format_exc())

            return None


if __name__ == '__main__':
    # Configure the log output format
    logging.basicConfig(
        level=logging.DEBUG,  # Set the log level; adjust as needed
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    '''
    support model:
        - ERNIE-Bot-turbo
        - ERNIE-Bot
        - ERNIE-Bot-4
        - BLOOMZ-7B
        - Llama-2-7b-chat
        - Llama-2-13b-chat
        - Llama-2-70b-chat
        - Qianfan-BLOOMZ-7B-compressed
        - Qianfan-Chinese-Llama-2-7B
        - ChatGLM2-6B-32K
        - AquilaChat-7B
    '''

    data = {
        "model": "Llama-2-7b-chat",
        "access_key": "",
        "secret_key": "",
        "top_p": 0.8,
        "temperature": 0.9,
        "penalty_score": 1.0,
        "history_enable": True,
        "history_max_len": 300
    }

    my_qian_fan = My_QianFan(data)
    logging.info(f'{my_qian_fan.get_resp("Can you play a catgirl and add meow after every sentence")}')
    logging.info(f'{my_qian_fan.get_resp("Good morning")}')
