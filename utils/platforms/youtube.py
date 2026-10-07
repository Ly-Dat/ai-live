import pytchat
import time
import re
import traceback
import os

from utils.my_log import logger
import utils.my_global as my_global

def start_listen(config, common, my_handle, platform: str):
    def get_video_id():
        try:
            return config.get("room_display_id")
        except Exception as e:
            logger.error("Failed to get the live room ID!\n{0}".format(e))
            return None

    def process_chat(live):
        while live.is_alive():
            try:
                for c in live.get().sync_items():
                    # Filter emoticons
                    chat_raw = re.sub(r":[^\s]+:", "", c.message)
                    chat_raw = chat_raw.replace("#", "")
                    if chat_raw != "":
                        # Reset the idle count
                        my_global.idle_time_auto_clear(config, "comment")

                        content = chat_raw  # Get the danmaku content
                        username = c.author.name  # Get the nickname of the user who sent the danmaku

                        logger.info(f"[{username}]: {content}")

                        data = {
                            "platform": platform,
                            "username": username,
                            "content": content,
                        }

                        my_handle.process_data(data, "comment")

                    # time.sleep(1)
            except Exception as e:
                logger.error(traceback.format_exc())
                logger.error("Error receiving chat: {0}".format(e))
                my_handle.abnormal_alarm_handle("platform")
                break  # Exit the inner while loop to trigger the reconnect mechanism

    try:
        reconnect_attempts = 0
        last_reconnect_time = None

        while True:
            video_id = get_video_id()
            if video_id is None:
                break

            live = pytchat.create(video_id=video_id)
            process_chat(live)

            current_time = time.time()
            # If the reconnect interval is under 30s, only 3 retries are made; if the interval is over 30s, retry indefinitely
            if last_reconnect_time and (current_time - last_reconnect_time < 30):
                reconnect_attempts += 1
                if reconnect_attempts >= 3:
                    logger.error("Reconnect failures reached the limit, exiting the program...")
                    break
                logger.warning(
                    f"Connection closed, interval under 30 seconds, trying to reconnect ({reconnect_attempts}/3)..."
                )
            else:
                reconnect_attempts = 0  # Reset the reconnect count
                logger.warning("Connection closed, trying to reconnect...")

            last_reconnect_time = current_time

    except KeyboardInterrupt:
        logger.warning("The program was forcibly exited")

    finally:
        logger.warning("Close the connection...")
        os._exit(0)