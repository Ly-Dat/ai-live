import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from utils.models import SendMessage, LLMMessage, CallbackMessage, CommonResult

import traceback

from utils.my_log import logger
import utils.my_global as my_global
from utils.config import Config

def start_listen(config, common, my_handle, platform: str):
    # Define the FastAPI app
    app = FastAPI()
    seq_list = []

    # Allow cross-origin requests
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.post("/wxlive")
    async def wxlive(request: Request):
        try:
            # Get the data in the POST request
            data = await request.json()
            # Code to process the received data can be added here
            logger.debug(data)

            if data["events"][0]["seq"] in seq_list:
                return CommonResult(code=-1, message="Filter duplicate data")

            # If the list length reaches 30, remove the oldest element
            if len(seq_list) >= 30:
                seq_list.pop(0)

            # Add a new element
            seq_list.append(data["events"][0]["seq"])

            # Danmaku data
            if data["events"][0]["decoded_type"] == "comment":
                # Reset the idle count
                my_global.idle_time_auto_clear(config, "comment")

                content = data["events"][0]["content"]  # Get the danmaku content
                username = data["events"][0]["nickname"]  # Get the nickname of the user who sent the danmaku

                logger.info(f"[{username}]: {content}")

                data = {
                    "platform": platform,
                    "username": username,
                    "content": content,
                }

                my_handle.process_data(data, "comment")
            # Entrance data
            elif data["events"][0]["decoded_type"] == "enter":
                my_global.idle_time_auto_clear(config, "entrance")

                username = data["events"][0]["nickname"]

                logger.info(f"User: {username} entered the live room")

                # Add the username to the latest username list
                my_global.add_username_to_last_username_list(username)

                data = {
                    "platform": platform,
                    "username": username,
                    "content": "entered the live room",
                }

                my_handle.process_data(data, "entrance")
                pass

            # Response
            return CommonResult(code=200, message="Received successfully")
        except Exception as e:
            logger.error(traceback.format_exc())
            my_handle.abnormal_alarm_handle("platform")
            return CommonResult(code=-1, message=f"Failed to send data!{e}")

    # Define the POST request path and handler function
    @app.post("/send")
    async def send(msg: SendMessage):
        try:
            tmp_json = msg.dict()
            logger.info(f"APIData received: {tmp_json}")
            data_json = tmp_json["data"]
            if "type" not in data_json:
                data_json["type"] = tmp_json["type"]

            if data_json["type"] in ["reread", "reread_top_priority"]:
                my_handle.reread_handle(data_json, type=data_json["type"])
            elif data_json["type"] == "comment":
                my_handle.process_data(data_json, "comment")
            elif data_json["type"] == "tuning":
                my_handle.tuning_handle(data_json)
            elif data_json["type"] == "gift":
                my_handle.gift_handle(data_json)
            elif data_json["type"] == "entrance":
                my_handle.entrance_handle(data_json)

            return CommonResult(code=200, message="Success")
        except Exception as e:
            logger.error(f"Failed to send data!{e}")
            return CommonResult(code=-1, message=f"Failed to send data!{e}")

    @app.post("/llm")
    async def llm(msg: LLMMessage):
        try:
            data_json = msg.dict()
            logger.info(f"APIData received: {data_json}")

            resp_content = my_handle.llm_handle(
                data_json["type"], data_json, webui_show=False
            )

            return CommonResult(
                code=200, message="Success", data={"content": resp_content}
            )
        except Exception as e:
            logger.error(f"LLM call failed!{e}")
            return CommonResult(code=-1, message=f"LLM call failed!{e}")

    @app.post("/callback")
    async def callback(msg: CallbackMessage):
        try:
            data_json = msg.dict()
            logger.info(f"APIData received: {data_json}")

            # Audio playback finished
            if data_json["type"] in ["audio_playback_completed"]:
                # If the number of audio clips waiting to play is greater than10
                if data_json["data"]["wait_play_audio_num"] > int(
                    config.get("idle_time_task", "wait_play_audio_num_threshold")
                ):
                    logger.info(
                        f'The number of audio clips waiting to play is greater than the limit; the idle timing of the idle task is handled by {my_global.global_idle_time} -> {int(config.get("idle_time_task", "idle_time_reduce_to"))}seconds'
                    )
                    # Reset the idle timer of the idle task
                    my_global.global_idle_time = int(
                        config.get("idle_time_task", "idle_time_reduce_to")
                    )

            return CommonResult(code=200, message="callbackProcessing succeeded!")
        except Exception as e:
            logger.error(f"callbackProcessing failed!{e}")
            return CommonResult(code=-1, message=f"callbackProcessing failed!{e}")

    logger.info("HTTP APIThread started!")
    uvicorn.run(app, host="0.0.0.0", port=config.get("api_port"))