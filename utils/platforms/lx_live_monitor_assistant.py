import websockets
import json
import asyncio
import traceback

from utils.my_log import logger
import utils.my_global as my_global

def start_listen(config, common, my_handle, platform: str):
    async def on_message(websocket, path):

        async for message in websocket:
            # logger.info(f"Message received: {message}")
            # await websocket.send("The server received your message: " + message)

            try:
                data_json = json.loads(message)
                # logger.debug(data_json)
                if data_json["type"] == "comment":
                    # logger.info(data_json)
                    # Reset the idle count
                    my_global.idle_time_auto_clear(config, "comment")

                    username = data_json["username"]
                    content = data_json["content"]

                    logger.info(f"[📧Live room danmaku message] [{username}]:{content}")

                    data = {
                        "platform": platform,
                        "username": username,
                        "content": content,
                    }

                    my_handle.process_data(data, "comment")

                    # Add the username to the latest username list
                    my_global.add_username_to_last_username_list(username)

            except Exception as e:
                logger.error(traceback.format_exc())
                logger.error("Data parsing error!")
                my_handle.abnormal_alarm_handle("platform")
                continue

    async def ws_server():
        ws_url = "127.0.0.1"
        ws_port = 5001
        server = await websockets.serve(on_message, ws_url, ws_port)
        logger.info(f"WebSocket Server started at {ws_url}:{ws_port}")
        await server.wait_closed()

    asyncio.run(ws_server())