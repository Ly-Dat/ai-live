import zhipuai
import logging
import traceback
import re

import time
import jwt  # Make sure this is the PyJWT library
import requests
from urllib.parse import urljoin
from packaging import version

# from utils.common import Common
# from utils.logger import Configure_logger

class Zhipu:
    def __init__(self, data):
        # self.common = Common()
        # # Log file path
        # file_path = "./log/log-" + self.common.get_bj_time(1) + ".txt"
        # Configure_logger(file_path)

        self.config_data = data

        # Check whether the zhipuai module has a __version__ attribute
        if hasattr(zhipuai, '__version__'):
            # Check the zhipu library version; 1.x.x and 2.x.x have breaking changes
            if version.parse(zhipuai.__version__) < version.parse('2.0.0'):
                zhipuai.api_key = data["api_key"]
                self.zhipu_ver = "1.x.x"
            else:
                from zhipuai import ZhipuAI
                self.client = ZhipuAI(api_key=data["api_key"])
                self.zhipu_ver = "2.x.x"
        else:
            zhipuai.api_key = data["api_key"]
            self.zhipu_ver = "1.x.x"

        self.model = data["model"]

        # Non-SDK
        self.base_url = "https://open.bigmodel.cn"
        self.token = None
        self.headers = None
        if self.model == "应用":
            try:
                self.token = self.generate_token(apikey=self.config_data["api_key"], exp_seconds=30 * 24 * 3600)

                self.headers = {
                    "Authorization": f"Bearer {self.token}",
                }

                url = urljoin(self.base_url, "/api/llm-application/open/application")

                data = {
                    "page": 1,
                    "size": 100
                }

                # getRequest
                response = requests.get(url=url, data=data, headers=self.headers)

                logging.debug(response.json())

                resp_json = response.json()

                tmp_content = "智谱应用列表："
            
                for data in resp_json["data"]["list"]:
                    tmp_content += f"\n应用名：{data['name']}，应用ID：{data['id']}，知识库：{data['knowledge_ids']}"

                logging.info(tmp_content)
            except Exception as e:
                logging.error(traceback.format_exc())


        self.history = []

    def invoke_example(self, prompt):
        response = zhipuai.model_api.invoke(
            model=self.model,
            prompt=prompt,
            top_p=float(self.config_data["top_p"]),
            temperature=float(self.config_data["temperature"]),
        )
        # logging.info(response)

        return response
    
    def invoke_characterglm(self, prompt):
        response = zhipuai.model_api.invoke(
            model=self.model,
            prompt=prompt,
            meta={
                "user_info": self.config_data["user_info"],
                "bot_info": self.config_data["bot_info"],
                "bot_name": self.config_data["bot_name"],
                "username": self.config_data["username"]
            },
            top_p=float(self.config_data["top_p"]),
            temperature=float(self.config_data["temperature"]),
        )
        # logging.info(response)

        return response

    def async_invoke_example(self, prompt):
        response = zhipuai.model_api.async_invoke(
            model="chatglm_pro",
            prompt=prompt,
            top_p=float(self.config_data["top_p"]),
            temperature=float(self.config_data["temperature"]),
        )
        logging.info(response)

        return response

    '''
    Description:
    add: Event stream opened
    error: Platform service or model exception, the exception event in the response
    interrupted: Interrupt event, e.g. triggered by a sensitive word
    finish: Data reception complete, close the event stream
    '''

    def sse_invoke_example(self, prompt):
        response = zhipuai.model_api.sse_invoke(
            model="chatglm_pro",
            # [{"role": "user", "content": "Artificial intelligence"}]
            prompt=prompt,
            top_p=float(self.config_data["top_p"]),
            temperature=float(self.config_data["temperature"]),
        )

        for event in response.events():
            if event.event == "add":
                logging.info(event.data)
            elif event.event == "error" or event.event == "interrupted":
                logging.info(event.data)
            elif event.event == "finish":
                logging.info(event.data)
                logging.info(event.meta)
            else:
                logging.info(event.data)

    def query_async_invoke_result_example(self):
        response = zhipuai.model_api.query_async_invoke_result("your task_id")
        logging.info(response)

        return response

    # Non-SDK authentication
    def generate_token(self, apikey: str, exp_seconds: int):
        try:
            id, secret = apikey.split(".")
        except Exception as e:
            raise Exception("invalid apikey", e)

        payload = {
            "api_key": id,
            "exp": int(round(time.time())) + exp_seconds,  # PyJWTThe exp field in expects a timestamp in seconds
            "timestamp": int(round(time.time() * 1000)),  # If you need a millisecond timestamp, you can keep this line
        }

        # Encode with PyJWTpayload
        token = jwt.encode(
            payload,
            secret,
            headers={"alg": "HS256", "sign_type": "SIGN"}
        )

        return token

    # Use a regular expression to replace multiple backslashes with a single backslash
    def remove_extra_backslashes(self, input_string):
        """Use a regular expression to replace multiple backslashes with a single backslash

        Args:
            input_string (str): Original string

        Returns:
            str: String after replacing multiple backslashes with a single backslash
        """
        cleaned_string = re.sub(r'\\+', r'\\', input_string)
        return cleaned_string


    def remove_useless_and_contents(self, input_string):
        """Use a regular expression to replace parentheses and their contents with an empty string, plus special characters

        Args:
            input_string (str): Original string

        Returns:
            str: String after replacement
        """
        result = re.sub(r'\（.*?\）', '', input_string)
        result = re.sub(r'\(.*?\)', '', result)
        result = result.replace('"', '').replace('“', '').replace('”', '').replace('\\', '')

        return result

    # Synchronous callzhipu api
    def get_zhipu_resp(self, data):
        """Request the corresponding API and get the return value

        Args:
            data (dict): zhipuConfiguration of model, msg, etc.

        Returns:
            dict: Return data
        """
        try:
            response = self.client.chat.completions.create(
                model=data["model"],  # Fill in the name of the model to call
                messages=data["messages"],
                meta=data.get("meta", None)
            )
        except Exception as e:
            logging.error(traceback.format_exc())
            return None

        return response


    def get_resp(self, prompt):
        """Request the corresponding API and get the return value

        Args:
            prompt (str): Your question

        Returns:
            str: Returned text answer
        """
        try:
            if self.zhipu_ver == "1.x.x":
                if self.config_data["history_enable"]:
                    self.history.append({"role": "user", "content": prompt})
                    data_json = self.history
                else:
                    data_json = [{"role": "user", "content": prompt}]

                logging.debug(f"data_json={data_json}")
                
                if self.model == "characterglm":
                    ret = self.invoke_characterglm(data_json)
                elif self.model == "应用":
                    url = urljoin(self.base_url, f"/api/llm-application/open/model-api/{self.config_data['app_id']}/invoke")

                    self.history.append({"role": "user", "content": prompt})
                    data = {
                        "prompt": self.history,
                        "returnType": "json_string",
                        # "knowledge_ids": [],
                        # "document_ids": []
                    }

                    response = requests.post(url=url, json=data, headers=self.headers)

                    try:
                        resp_json = response.json()

                        logging.debug(resp_json)

                        resp_content = resp_json["data"]["content"]

                        # If history is enabled, remember it for me!
                        if self.config_data["history_enable"]:
                            # Add the robot answer to the history
                            self.history.append({"role": "assistant", "content": resp_content})

                            while True:
                                # Get the character count of all strings in a nested list
                                total_chars = sum(len(string) for sublist in self.history for string in sublist)
                                # If it exceeds the maximum history limit, remove the 1st and 2nd elements
                                if total_chars > int(self.config_data["history_max_len"]):
                                    self.history.pop(0)
                                    self.history.pop(0)
                                else:
                                    break

                        return resp_content
                    except Exception as e:
                        def is_odd(number):
                            # Check whether the remainder of the number divided by 2 is1
                            return number % 2 != 0
                        
                        # Keep history always at an even number of items
                        if is_odd(len(self.history)):
                            self.history.pop(0)

                        logging.error(traceback.format_exc())
                        return None
                    
                else:
                    ret = self.invoke_example(data_json)

                logging.debug(f"ret={ret}")

                if False == ret['success']:
                    logging.error(f"Failed to request Zhipu AI, error code:{ret['code']},{ret['msg']}")
                    return None

                # If history is enabled, remember it for me!
                if self.config_data["history_enable"]:
                    while True:
                        # Get the character count of all strings in a nested list
                        total_chars = sum(len(string) for sublist in self.history for string in sublist)
                        # If it exceeds the maximum history limit, remove the first element
                        if total_chars > int(self.config_data["history_max_len"]):
                            self.history.pop(0)
                        else:
                            self.history.append(ret['data']['choices'][0])
                            break

                return ret['data']['choices'][0]['content']
            else:
                if self.model == "应用":
                    url = urljoin(self.base_url, f"/api/llm-application/open/model-api/{self.config_data['app_id']}/invoke")

                    self.history.append({"role": "user", "content": prompt})
                    data = {
                        "prompt": self.history,
                        "returnType": "json_string",
                        # "knowledge_ids": [],
                        # "document_ids": []
                    }

                    response = requests.post(url=url, json=data, headers=self.headers)

                    try:
                        resp_json = response.json()

                        logging.debug(resp_json)

                        resp_content = resp_json["data"]["content"]

                        # If history is enabled, remember it for me!
                        if self.config_data["history_enable"]:
                            # Add the robot answer to the history
                            self.history.append({"role": "assistant", "content": resp_content})

                            while True:
                                # Get the character count of all strings in a nested list
                                total_chars = sum(len(string) for sublist in self.history for string in sublist)
                                # If it exceeds the maximum history limit, remove the 1st and 2nd elements
                                if total_chars > int(self.config_data["history_max_len"]):
                                    self.history.pop(0)
                                    self.history.pop(0)
                                else:
                                    break

                        return resp_content
                    except Exception as e:
                        def is_odd(number):
                            # Check whether the remainder of the number divided by 2 is1
                            return number % 2 != 0
                        
                        # Keep history always at an even number of items
                        if is_odd(len(self.history)):
                            self.history.pop(0)

                        logging.error(traceback.format_exc())
                        return None
                else:
                    if self.config_data["history_enable"]:
                        import copy 
                        tmp_msg = copy.copy(self.history)
                        tmp_msg.append({"role": "user", "content": prompt})
                        logging.debug(f"tmp_msg={tmp_msg}")

                        if self.model == "charglm-3":
                            response = self.get_zhipu_resp(
                                { 
                                    "model": self.model,  # Fill in the name of the model to call
                                    "messages": tmp_msg,
                                    "meta": {
                                        "user_info": self.config_data["user_info"],
                                        "bot_info": self.config_data["bot_info"],
                                        "bot_name": self.config_data["bot_name"],
                                        "username": self.config_data["username"]
                                    }
                                }
                            )
                        else:
                            response = self.get_zhipu_resp(
                                { 
                                    "model": self.model,  # Fill in the name of the model to call
                                    "messages": tmp_msg
                                }
                            )
                    else:
                        if self.model == "charglm-3":
                            response = self.get_zhipu_resp(
                                { 
                                    "model": self.model,  # Fill in the name of the model to call
                                    "messages": [
                                        {
                                            "role": "user",
                                            "content": prompt
                                        }
                                    ],
                                    "meta": {
                                        "user_info": self.config_data["user_info"],
                                        "bot_info": self.config_data["bot_info"],
                                        "bot_name": self.config_data["bot_name"],
                                        "username": self.config_data["username"]
                                    }
                                }
                            )
                        else:
                            response = self.get_zhipu_resp(
                                { 
                                    "model": self.model,  # Fill in the name of the model to call
                                    "messages": [
                                        {
                                            "role": "user",
                                            "content": prompt
                                        }
                                    ]
                                }
                            )

                    if response is None:
                        return None
            
                    resp_content = response.choices[0].message.content.strip()

                    # If history is enabled, remember it for me!
                    if self.config_data["history_enable"]:
                        while True:
                            # Get the character count of all strings in a nested list
                            total_chars = sum(len(string) for sublist in self.history for string in sublist)
                            # If it exceeds the maximum history limit, remove the 1st and 2nd elements
                            if total_chars > int(self.config_data["history_max_len"]):
                                self.history.pop(0)
                                self.history.pop(0)
                            else:
                                self.history.append({"role": "user", "content": prompt})
                                self.history.append({"role": "assistant", "content": resp_content})
                                break
                    
                    return resp_content
        except Exception as e:
            logging.error(traceback.format_exc())
            return None

    def get_resp_with_img(self, prompt, img_data):
        try:
            # Check the type of img_data
            if isinstance(img_data, str):  # If it is a string, assume it is a file path
                import base64

                # Read the local image file
                with open(img_data, "rb") as image_file:
                    # Convert the image content to base64 encoding
                    img = base64.b64encode(image_file.read()).decode("utf-8")
            else:
                img = img_data

            response = self.get_zhipu_resp(
                { 
                    "model": "glm-4v-plus",  # Fill in the name of the model to call
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": prompt
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url" : img
                                    }
                                }
                            ]
                        }
                    ]
                }
            )

            if response is None:
                return None

            resp_content = response.choices[0].message.content.strip()
        
            logging.debug(f"resp_content={resp_content}")

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

    data = {
        "api_key": "",
        "app_id": "1761340125461340161",
        # chatglm_pro/chatglm_std/chatglm_lite/characterglm /glm-3-turbo/glm-4/charglm-3
        "model": "chatglm_lite",
        "top_p": 0.7,
        "temperature": 0.9,
        "history_enable": True,
        "history_max_len": 300,
        "user_info": "我是陆星辰，是一个男性，是一位知名导演，也是苏梦远的合作导演。我擅长拍摄音乐题材的电影。苏梦远对我的态度是尊敬的，并视我为良师益友。",
        "bot_info": "苏梦远，本名苏远心，是一位当红的国内女歌手及演员。在参加选秀节目后，凭借独特的嗓音及出众的舞台魅力迅速成名，进入娱乐圈。她外表美丽动人，但真正的魅力在于她的才华和勤奋。苏梦远是音乐学院毕业的优秀生，善于创作，拥有多首热门原创歌曲。除了音乐方面的成就，她还热衷于慈善事业，积极参加公益活动，用实际行动传递正能量。在工作中，她对待工作非常敬业，拍戏时总是全身心投入角色，赢得了业内人士的赞誉和粉丝的喜爱。虽然在娱乐圈，但她始终保持低调、谦逊的态度，深得同行尊重。在表达时，苏梦远喜欢使用“我们”和“一起”，强调团队精神。",
        "bot_name": "苏梦远",
        "username": "陆星辰",
        "remove_useless": True
    }

    zhipu = Zhipu(data)

    # logging.info(zhipu.get_resp("Can you play a catgirl and add meow after every sentence"))
    # logging.info(zhipu.get_resp("Good morning"))
    # logging.info(zhipu.get_resp("Who are you"))

    logging.info(zhipu.get_resp_with_img("Determine the image content", "E:\\GitHub_pro\\AI-Vtuber\\docs\\xmind.png"))
