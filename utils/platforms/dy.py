import websocket
import json
import aiohttp
import random
import traceback
import string
import requests
from typing import Optional

from utils.my_log import logger
import utils.my_global as my_global
from utils.config import Config

# Config file path
config_path = "config.json"
config = None

def start_listen(new_config, common, my_handle, platform: str, schedule_thread):
    global config
    config = new_config

    def on_message(ws, message):
        global config
        
        message_json = json.loads(message)
        # logger.debug(message_json)
        if "Type" in message_json:
            type = message_json["Type"]
            data_json = json.loads(message_json["Data"])

            if type == 1:
                # Reset the idle count
                my_global.idle_time_auto_clear(config, "comment")

                username = data_json["User"]["Nickname"]
                content = data_json["Content"]

                logger.info(f"[📧Live room danmaku message] [{username}]:{content}")

                data = {
                    "platform": platform,
                    "username": username,
                    "content": content,
                }

                my_handle.process_data(data, "comment")

                pass

            elif type == 2:
                username = data_json["User"]["Nickname"]
                count = data_json["Count"]

                logger.info(f"[👍Live room like message] {username} liked {count} times")

            elif type == 3:
                my_global.idle_time_auto_clear(config, "entrance")

                username = data_json["User"]["Nickname"]

                logger.info(f"[🚹🚺Live room member join message] Welcome {username} to the live room")

                data = {
                    "platform": platform,
                    "username": username,
                    "content": "entered the live room",
                }

                # Add the username to the latest username list
                my_global.add_username_to_last_username_list(username)

                my_handle.process_data(data, "entrance")

            elif type == 4:
                my_global.idle_time_auto_clear(config, "follow")

                username = data_json["User"]["Nickname"]

                logger.info(
                    f'[➕Live room follow message] Thanks {data_json["User"]["Nickname"]} follow of'
                )

                data = {"platform": platform, "username": username}

                my_handle.process_data(data, "follow")

                pass

            elif type == 5:
                my_global.idle_time_auto_clear(config, "gift")

                gift_name = data_json["GiftName"]
                username = data_json["User"]["Nickname"]
                # Gift quantity
                num = data_json["GiftCount"]
                # Gift repeat count
                repeat_count = data_json["RepeatCount"]

                try:
                    # Hard-coded for now
                    data_path = "data/抖音礼物价格表.json"

                    # Read the JSON file
                    with open(data_path, "r", encoding="utf-8") as file:
                        # Parse JSON data
                        data_json = json.load(file)

                    if gift_name in data_json:
                        # Single gift amount; you need to maintain the gift value table yourself
                        discount_price = data_json[gift_name]
                    else:
                        logger.warning(
                            f"There is no value for {gift_name} in the data file: {data_path}, please add the data manually"
                        )
                        discount_price = 1
                except Exception as e:
                    logger.error(traceback.format_exc())
                    discount_price = 1

                # Total amount
                combo_total_coin = repeat_count * discount_price

                logger.info(
                    f"[🎁Live room gift message] User: {username} gifted {num} x {gift_name}, unit price {discount_price} Douyin coins, total {combo_total_coin} Douyin coins"
                )

                data = {
                    "platform": platform,
                    "gift_name": gift_name,
                    "username": username,
                    "num": num,
                    "unit_price": discount_price / 10,
                    "total_price": combo_total_coin / 10,
                }

                my_handle.process_data(data, "gift")

            elif type == 6:
                logger.info(f'[Live room data] {data_json["Content"]}')
                # {'OnlineUserCount': 50, 'TotalUserCount': 22003, 'TotalUserCountStr': '2.210k', 'OnlineUserCountStr': '50',
                # 'MsgId': 7260517442466662207, 'User': None, 'Content': 'Current live room viewers 50, cumulative live room viewers 22k', 'RoomId': 7260415920948906807}
                # logger.info(f"data_json={data_json}")

                my_global.last_liveroom_data = data_json

                # Current online viewer count
                OnlineUserCount = data_json["OnlineUserCount"]

                try:
                    # Whether the dynamic config feature is enabled
                    if config.get("trends_config", "enable"):
                        for path_config in config.get("trends_config", "path"):
                            online_num_min = int(
                                path_config["online_num"].split("-")[0]
                            )
                            online_num_max = int(
                                path_config["online_num"].split("-")[1]
                            )

                            # Check whether the online viewer count is within this range
                            if (
                                OnlineUserCount >= online_num_min
                                and OnlineUserCount <= online_num_max
                            ):
                                logger.debug(f"Current config file:{path_config['path']}")
                                # If the config files are the same, skip
                                if config_path == path_config["path"]:
                                    break

                                config_path = path_config["path"]
                                config = Config(config_path)

                                my_handle.reload_config(config_path)

                                logger.info(f"Switch config file:{config_path}")

                                break
                except Exception as e:
                    logger.error(traceback.format_exc())

                pass

            elif type == 8:
                logger.info(
                    f'[Share live room] Thanks {data_json["User"]["Nickname"]} Shared the live room'
                )

                pass

    def on_error(ws, error):
        logger.error(f"Error:{error}")

    def on_close(ws, close_status_code, close_msg):
        logger.debug("WebSocket connection closed")

    def on_open(ws):
        logger.debug("WebSocket connection established")

    try:
        # WebSocketConnectURL
        ws_url = "ws://127.0.0.1:8888"

        logger.info(f"Listening address:{ws_url}")

        # Do not set the log level
        websocket.enableTrace(False)
        # Create a WebSocket connection
        ws = websocket.WebSocketApp(
            ws_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open,
        )

        # Run the WebSocket connection
        ws.run_forever()
    except KeyboardInterrupt:
        logger.warning("The program was forcibly exited")
    finally:
        logger.warning(
            "Closing the ws connection... please confirm that you have started the Douyin danmaku listener and the ws service is running normally!\nAfter the listener starts successfully, please rerun the program to connect and use it!"
        )
        # os._exit(0)

    # Wait for the child threads to finish
    schedule_thread.join()