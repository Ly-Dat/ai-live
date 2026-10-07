from sparkdesk_web.core import SparkWeb
from sparkdesk_api.core import SparkAPI

from utils.common import Common
from utils.my_log import logger


class SPARKDESK:
    def __init__(self, data):
        self.common = Common()

        self.type = data["type"]


        self.sparkWeb = None
        self.sparkAPI = None

        if data["cookie"] != "" and data["fd"] != "" and data["GtToken"] != "":
            self.sparkWeb = SparkWeb(
                cookie = data["cookie"],
                fd = data["fd"],
                GtToken = data["GtToken"]
            )
        elif data["app_id"] != "" and data["api_secret"] != "" and data["api_key"] != "":
            if data["assistant_id"] == "":
                self.sparkAPI = SparkAPI(
                    app_id = data["app_id"],
                    api_secret = data["api_secret"],
                    api_key = data["api_key"],
                    version = data["version"]
                )
            else:
                try:
                    self.sparkAPI = SparkAPI(
                        app_id = data["app_id"],
                        api_secret = data["api_secret"],
                        api_key = data["api_key"],
                        version = data["version"],
                        assistant_id = data["assistant_id"]
                    )
                except TypeError as e:
                    logger.error(e)
                    logger.error("If there is no assistant_id parameter, your sparkdesk-api library version is too old, please update to the latest version.\nPlease activate the conda environment first, then update; reference command:pip install git+https://gitee.com/ikaros-521/sparkdesk-api -U")
        else:
            logger.info("iFlytek Spark config is empty")


    def get_resp(self, prompt):
        if self.type == "web":
            return self.sparkWeb.chat(prompt)
        elif self.type == "api":
            return self.sparkAPI.chat(prompt)
        else:
            logger.error("What are you messing with in the config???")
            exit(0)
