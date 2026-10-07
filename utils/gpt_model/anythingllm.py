import json, traceback
import requests
from urllib.parse import urljoin

from utils.common import Common
from utils.my_log import logger


class AnythingLLM:
    def __init__(self, data):
        self.common = Common()

        self.config_data = data
        self.headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.config_data['api_key']}"
        }
        self.workspaces_list = []

    # Verify the key
    def verify_auth(self):
        try:
            url = urljoin(self.config_data["api_ip_port"], "/api/v1/auth")
        

            response = requests.get(url, headers=self.headers)
            response.raise_for_status()  # Check the response status code

            result = response.content
            ret = json.loads(result)

            logger.debug(ret)
            if "authenticated" in ret:
                return True

            logger.error(f"AnythingLLM APIKey verification failed: {ret['message']}")
            return False
        except Exception as e:
            logger.error(traceback.format_exc())
            return False

    # Get the workspace list
    def get_workspaces_list(self):
        try:
            url = urljoin(self.config_data["api_ip_port"], "/api/v1/workspaces")
        

            response = requests.get(url, headers=self.headers)
            response.raise_for_status()  # Check the response status code

            result = response.content
            ret = json.loads(result)

            logger.debug(ret)
            if "workspaces" in ret:
                self.workspaces_list = ret["workspaces"]
                return ret["workspaces"]

            logger.error(f"AnythingLLM Failed to get the workspace list: {ret['message']}")
            return None
        except Exception as e:
            logger.error(traceback.format_exc())
            return None

    def get_resp(self, data):
        """Request the corresponding API and get the return value

        Args:
            data (dict): Your question

        Returns:
            str: Returned text answer
        """
        try:
            url = urljoin(self.config_data["api_ip_port"], f"/api/v1/workspace/{self.config_data['workspace_slug']}/chat")

            if "mode" in data:
                mode = data["mode"]
            else:
                mode = self.config_data["mode"]

            data_json = {
                "message": data["prompt"],
                "mode": mode
            }

            response = requests.post(url=url, json=data_json, headers=self.headers)
            response.raise_for_status()  # Check the response status code

            result = response.content
            ret = json.loads(result)

            logger.debug(ret)

            if "textResponse" in ret:
                return ret["textResponse"]

            logger.error(f"AnythingLLM Conversation failed: {ret['message']}")
            return None
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
        "api_ip_port": "http://127.0.0.1:3001",
        "api_key": "S1PPG9B-YP2M8NX-Q64ZBF1-Y4K5DCS",
        "mode": "chat",
        "workspace_slug": "test"
    }
    anythingllm = AnythingLLM(data)

    # Verify the key
    if anythingllm.verify_auth():
        # Get the return value
        
        anythingllm.get_workspaces_list()

        logger.info(anythingllm.get_resp({"prompt": "Can you play a catgirl and add meow after every sentence"}))
        logger.info(anythingllm.get_resp({"prompt": "Good morning"}))
    
        logger.info(anythingllm.get_resp({"prompt": "The relationship between Icarus and Nymph", "mode": "chat"}))
        #logger.info(anythingllm.get_resp({"prompt": "The English name of Icarus", "mode": "chat"}))