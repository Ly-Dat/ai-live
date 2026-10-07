import json, logging
import requests
from urllib.parse import urljoin

# from utils.common import Common
# from utils.logger import Configure_logger


class Koboldcpp:
    def __init__(self, data):
        # self.common = Common()
        # Log file path
        # file_path = "./log/log-" + self.common.get_bj_time(1) + ".txt"
        # Configure_logger(file_path)

        self.config_data = data

        self.history = "[The following is an interesting chat message log between You and AI.]"


    def get_resp(self, data):
        """Request the corresponding API and get the return value

        Args:
            data (dict): Data

        Returns:
            str: Returned text answer
        """
        try:
            prompt = data["prompt"]

            data_json = self.config_data
            url = urljoin(self.config_data["api_ip_port"], "/api/v1/generate")

            data_json["prompt"] = f"{self.history}\nYou: {prompt}"

            logging.info(f"data_json={data_json}")

            response = requests.post(url=url, json=data_json)
            response.raise_for_status()  # Check the response status code

            result = response.content
            ret = json.loads(result)

            logging.info(ret)

            resp_content = ret["results"][0]["text"]

            # If history is enabled, remember it for me!
            if self.config_data["history_enable"]:
                self.history += f'\nYou: {prompt}\nAI: {resp_content}'
                while True:
                    total_chars = len(self.history)
                    # If it exceeds the maximum history limit, remove the first element
                    if total_chars > self.config_data["history_max_len"]:
                        # Suppose self.history is the original string
                        split_list = self.history.split("\n")  # Split the string into a list

                        # Keep the first element, skip the second and third elements, then keep all the remaining elements
                        # Note that list indices start at 0, so the index of the second element is 1 and the third is2
                        processed_list = split_list[:1] + split_list[3:]

                        # Merge the processed list elements back into a string
                        self.history = "\n".join(processed_list)
                    else:
                        break

            return resp_content
        except Exception as e:
            logging.error(e)
            return None


if __name__ == '__main__':
    # Configure the log output format
    logging.basicConfig(
        level=logging.INFO,  # Set the log level; adjust as needed
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    data = {
        "api_ip_port": "http://127.0.0.1:5001",
        "max_context_length": 2048,
        "max_length": 100,
        "quiet": False,
        "rep_pen": 1.1,
        "rep_pen_range": 256,
        "rep_pen_slope": 1,
        "temperature": 0.5,
        "tfs": 1,
        "top_a": 0,
        "top_k": 3,
        "top_p": 0.9,
        "typical": 1,
        "history_enable": True,
        "history_max_len": 600
    }
    koboldcpp = Koboldcpp(data)

    logging.info(koboldcpp.get_resp({"prompt": "what is your name"}))
    logging.info(koboldcpp.get_resp({"prompt": "what can your do"}))
    