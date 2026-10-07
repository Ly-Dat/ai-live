import json, traceback

from xingchen import Configuration, ApiClient, ChatApiSub, ChatReqParams, CharacterKey, Message, UserProfile, \
    ModelParameters, ChatHistoryQueryDTO, ChatHistoryQueryWhere

from utils.my_log import logger

# Official documentation:https://xingchen.aliyun.com/xingchen/document

class TongYiXingChen:
    def __init__(self, data):
        # self.common = Common()
        # # Log file path
        # file_path = "./log/log-" + self.common.get_bj_time(1) + ".txt"
        # Configure_logger(file_path)

        self.config_data = data
        self.timeout = 60

        self.history = []

        self.api_instance = self.init_client()

    def init_client(self):
        configuration = Configuration(
            host="https://nlp.aliyuncs.com"
        )
        configuration.access_token = self.config_data["access_token"]
        with ApiClient(configuration) as api_client:
            api_instance = ChatApiSub(api_client)
        return api_instance

    def build_chat_param(self, prompt):
        # Whether to enable history memory
        if self.config_data["history_enable"]:
            messages_list = []
            for data in self.history:
                messages_list.append(
                    Message(
                        name=data['name'],
                        role=data['role'],
                        content=data['content']
                    )
                )
            
            messages_list.append(
                Message(
                    name=self.config_data[self.config_data["type"]]["username"],
                    role='user',
                    content=prompt
                )
            )

            # messages_list.append(
            #     Message(
            #         name=self.config_data[self.config_data["type"]]["role_name"],
            #         role='assistant',
            #         content=prompt
            #     )
            # )
        else:
            messages_list = [
                Message(
                    name=self.config_data[self.config_data["type"]]["username"],
                    role='user',
                    content=prompt
                )
            ]

        # logger.info(f"messages_list={messages_list}")

        return ChatReqParams(
            bot_profile=CharacterKey(
                character_id=self.config_data[self.config_data["type"]]["character_id"],
                version=1
            ),
            model_parameters=ModelParameters(
                top_p=self.config_data[self.config_data["type"]]["top_p"],    
                temperature=self.config_data[self.config_data["type"]]["temperature"],
                seed=self.config_data[self.config_data["type"]]["seed"],
                incrementalOutput=True # Incremental output
            ),
            messages=[
                Message(
                    name=self.config_data[self.config_data["type"]]["username"],
                    role='user',
                    content=prompt
                ),
            ],
            user_profile=UserProfile(
                user_id=self.config_data[self.config_data["type"]]["user_id"],
                username=self.config_data[self.config_data["type"]]["username"]
            )
        )
    
    def chat_histories(self):
        api = self.init_client()
        body = ChatHistoryQueryDTO(
            where=ChatHistoryQueryWhere(
                characterId=self.config_data[self.config_data["type"]]["character_id"],
                bizUserId=self.config_data[self.config_data["type"]]["user_id"],
                sessionId="7ed48d9881b54ed49d6967be7be01743"
                # startTime="1970-01-01T00:00:00.00Z",
                # endTime="1970-01-01T00:00:00.00Z",
                # messageIds=[
                #     "e5bfc3c7809e47c5ac17181250adcf2b"
                # ],

            ),
            orderBy=[
                "gmtCreate desc"
            ],
            pageNum=1,
            pageSize=10
        )

        # Conversation history
        result = api.chat_histories(chat_history_query_dto=body)
        logger.info(result.data)

    # Non-streaming reply
    def chat_sync(self, prompt):
        chat_param = self.build_chat_param(prompt)
        res = self.api_instance.chat(chat_param, _request_timeout=self.timeout)
        # logger.info(res.to_dict())
        # logger.info(res.to_str())

        return res.to_dict()

    # Streaming reply
    def chat_async(self, prompt):
        # User conversation
        chat_param = self.build_chat_param(prompt)
        chat_param.streaming = True
        responses = self.api_instance.chat(chat_param, _request_timeout=self.timeout)
        return responses

    def get_resp(self, prompt, stream=False):
        """Request the corresponding API and get the return value

        Args:
            prompt (str): Your question
            stream (bool, optional): Whether to return as a stream. Defaults to False.

        Returns:
            str: Returned text answer
        """
        try:
            if self.config_data["type"] == "Fixed role":
                try:
                    if stream:
                        response = self.chat_async(prompt)
                        # Return the response
                        return response
                    else:
                        data_json = self.chat_sync(prompt)

                    resp_content = data_json["data"]["choices"][0]["messages"][0]["content"]

                    # If history is enabled, remember it for me!
                    if self.config_data["history_enable"]:
                        while True:
                            # Get the character count of all strings in a nested list
                            total_chars = sum(len(item['content']) for item in self.history if 'content' in item)
                            # If it exceeds the maximum history limit, remove the first element
                            if total_chars > self.config_data["history_max_len"]:
                                self.history.pop(0)
                            else:
                                # self.history.pop()
                                self.history.append({"role": "user", "name": self.config_data[self.config_data["type"]]["username"], "content": prompt})
                                self.history.append({"role": "assistant", "name": self.config_data[self.config_data["type"]]["role_name"], "content": resp_content})
                                break

                    return resp_content
                except Exception as e:
                    logger.error(traceback.format_exc())
            
        except Exception as e:
            logger.error(traceback.format_exc())

        return None


    # Add the AI reply message to the session to provide contextual memory
    def add_assistant_msg_to_session(self, prompt: str, message: str):
        try:
            if self.config_data["type"] == "Fixed role":
                # If history is enabled, remember it for me!
                if self.config_data["history_enable"]:
                    while True:
                        # Get the character count of all strings in a nested list
                        total_chars = sum(len(item['content']) for item in self.history if 'content' in item)
                        # If it exceeds the maximum history limit, remove the first element
                        if total_chars > self.config_data["history_max_len"]:
                            self.history.pop(0)
                        else:
                            # self.history.pop()
                            self.history.append({"role": "user", "name": self.config_data[self.config_data["type"]]["username"], "content": prompt})
                            self.history.append({"role": "assistant", "name": self.config_data[self.config_data["type"]]["role_name"], "content": message})
                            break

                logger.debug(f"history={self.history}")

                return {"ret": True}
            
            return {"ret": False}
        except Exception as e:
            logger.error(traceback.format_exc())
            return {"ret": False}

if __name__ == '__main__':
    # Configure the log output format
    logger.basicConfig(
        level=logger.DEBUG,  # Set the log level; adjust as needed
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    data = {
        "access_token": "lm-xxx==",
        "type": "Fixed role",
        "Fixed role": {
            "character_id": "1b34205ee8814acc9e7acf593e7cf759",
            "top_p": 0.95,
            "temperature": 0.92,
            "seed": 1683806810,
            "user_id": "1",
            "username": "主人",
            "role_name": "伊卡洛斯"
        },
        "history_enable": True,
        "history_max_len": 300
    }

    # Instantiate and call init_client
    tongyixingchen = TongYiXingChen(data)
    logger.info(tongyixingchen.get_resp("Please remember what I said"))
    logger.info(tongyixingchen.get_resp("What did I just say"))
    logger.info(tongyixingchen.get_resp("What did I just say!"))
