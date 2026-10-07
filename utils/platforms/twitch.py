import socks
from emoji import demojize

import json
import re
import traceback

from utils.my_log import logger
import utils.my_global as my_global

def start_listen(config, common, my_handle, platform: str):
    try:
        server = "irc.chat.twitch.tv"
        port = 6667
        nickname = "主人"

        try:
            channel = (
                "#" + config.get("room_display_id")
            )  # The channel to retrieve messages from; note that # must be included at the start The channel you want to retrieve messages from
            token = config.get(
                "twitch", "token"
            )  # Visit https://twitchapps.com/tmi/ to get it
            user = config.get(
                "twitch", "user"
            )  # Your Twitch username Your Twitch username
            # Address and port of the proxy server
            proxy_server = config.get("twitch", "proxy_server")
            proxy_port = int(config.get("twitch", "proxy_port"))
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error("Failed to get the Twitch config!\n{0}".format(e))
            my_handle.abnormal_alarm_handle("platform")

        # Configure the proxy server
        socks.set_default_proxy(socks.HTTP, proxy_server, proxy_port)

        # Create the socket object
        sock = socks.socksocket()

        try:
            sock.connect((server, port))
            logger.info("Connected successfully Twitch IRC server")
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(f"Failed to connect to the Twitch IRC server: {e}")
            my_handle.abnormal_alarm_handle("platform")

        sock.send(f"PASS {token}\n".encode("utf-8"))
        sock.send(f"NICK {nickname}\n".encode("utf-8"))
        sock.send(f"JOIN {channel}\n".encode("utf-8"))

        regex = r":(\w+)!\w+@\w+\.tmi\.twitch\.tv PRIVMSG #\w+ :(.+)"

        # Reconnection count
        retry_count = 0

        while True:
            try:
                resp = sock.recv(2048).decode("utf-8")

                # Output all received content, includingPING/PONG
                # logger.info(resp)

                if resp.startswith("PING"):
                    sock.send("PONG\n".encode("utf-8"))

                elif not user in resp:
                    # Reset the idle count
                    my_global.idle_time_auto_clear(config, "comment")

                    resp = demojize(resp)

                    logger.debug(resp)

                    match = re.match(regex, resp)

                    username = match.group(1)
                    content = match.group(2)
                    content = content.rstrip()

                    logger.info(f"[{username}]: {content}")

                    data = {
                        "platform": platform,
                        "username": username,
                        "content": content,
                    }

                    my_handle.process_data(data, "comment")
            except AttributeError as e:
                logger.error(traceback.format_exc())
                logger.error(f"Exception caught: {e}")
                logger.error("An exception occurred, reconnectingsocket")
                my_handle.abnormal_alarm_handle("platform")

                if retry_count >= 3:
                    logger.error(f"Multiple reconnection attempts failed, program ends!")
                    return

                retry_count += 1
                logger.error(f"Retry count: {retry_count}")

                # Add the code to reconnect the socket here
                # For example, you may want to close the old socket connection and then create a new one
                sock.close()

                # Create the socket object
                sock = socks.socksocket()

                try:
                    sock.connect((server, port))
                    logger.info("Connected successfully Twitch IRC server")
                except Exception as e:
                    logger.error(f"Failed to connect to the Twitch IRC server: {e}")

                sock.send(f"PASS {token}\n".encode("utf-8"))
                sock.send(f"NICK {nickname}\n".encode("utf-8"))
                sock.send(f"JOIN {channel}\n".encode("utf-8"))
            except Exception as e:
                logger.error(traceback.format_exc())
                logger.error("Error receiving chat: {0}".format(e))
                my_handle.abnormal_alarm_handle("platform")
    except Exception as e:
        logger.error(traceback.format_exc())
        my_handle.abnormal_alarm_handle("platform")