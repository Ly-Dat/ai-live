import blivedm
import blivedm.models.web as web_models
import blivedm.models.open_live as open_models

import http.cookies
import json
import aiohttp
import asyncio
import traceback
from typing import Optional
import random

from utils.my_log import logger
import utils.my_global as my_global



session: Optional[aiohttp.ClientSession] = None

def start_listen(config, common, my_handle, platform: str):
    # For the live room ID value, see the live roomURL
    TEST_ROOM_IDS = [my_handle.get_room_id()]
    # Fill in the cookie of a logged-in account here. You can also connect without a cookie, but the usernames in received danmaku will be masked and the UID will become0
    SESSDATA = ""

    try:
        if config.get("bilibili", "login_type") == "cookie":
            bilibili_cookie = config.get("bilibili", "cookie")
            SESSDATA = common.parse_cookie_data(bilibili_cookie, "SESSDATA")
            # logger.info(f"SESSDATA={SESSDATA}")
        elif config.get("bilibili", "login_type") == "open_live":
            # Developer key applied for on the open platform https://open-live.bilibili.com/open-manage
            ACCESS_KEY_ID = config.get("bilibili", "open_live", "ACCESS_KEY_ID")
            ACCESS_KEY_SECRET = config.get(
                "bilibili", "open_live", "ACCESS_KEY_SECRET"
            )
            # Project created on the open platformID
            APP_ID = config.get("bilibili", "open_live", "APP_ID")
            # Streamer identity code, obtained from the live streaming center
            ROOM_OWNER_AUTH_CODE = config.get(
                "bilibili", "open_live", "ROOM_OWNER_AUTH_CODE"
            )

    except Exception as e:
        logger.error(traceback.format_exc())
        my_handle.abnormal_alarm_handle("platform")

    async def main_func():
        global session
        
        if config.get("bilibili", "login_type") == "open_live":
            await run_single_client2()
        else:
            try:
                init_session()

                await run_single_client()
                await run_multi_clients()
            finally:
                await session.close()

    def init_session():
        global session

        cookies = http.cookies.SimpleCookie()
        cookies["SESSDATA"] = SESSDATA
        cookies["SESSDATA"]["domain"] = "bilibili.com"

        # logger.info(f"SESSDATA={SESSDATA}")

        # logger.warning(f"sessdata={SESSDATA}")
        # logger.warning(f"cookies={cookies}")

        session = aiohttp.ClientSession()
        session.cookie_jar.update_cookies(cookies)

    async def run_single_client():
        """
        Demo of listening to one live room
        """
        global session
        
        room_id = random.choice(TEST_ROOM_IDS)
        client = blivedm.BLiveClient(room_id, session=session)
        handler = MyHandler()
        client.set_handler(handler)

        client.start()
        try:
            # Demo stops after 5 seconds
            await asyncio.sleep(5)
            client.stop()

            await client.join()
        finally:
            await client.stop_and_close()

    async def run_single_client2():
        """
        Demo of listening to one live room on the open platform
        """
        client = blivedm.OpenLiveClient(
            access_key_id=ACCESS_KEY_ID,
            access_key_secret=ACCESS_KEY_SECRET,
            app_id=APP_ID,
            room_owner_auth_code=ROOM_OWNER_AUTH_CODE,
        )
        handler = MyHandler2()
        client.set_handler(handler)

        client.start()
        try:
            # Demo stops after 70 seconds
            # await asyncio.sleep(70)
            # client.stop()

            await client.join()
        finally:
            await client.stop_and_close()

    async def run_multi_clients():
        """
        Demo of listening to multiple live rooms at the same time
        """
        global session
        
        clients = [
            blivedm.BLiveClient(room_id, session=session)
            for room_id in TEST_ROOM_IDS
        ]
        handler = MyHandler()
        for client in clients:
            client.set_handler(handler)
            client.start()

        try:
            await asyncio.gather(*(client.join() for client in clients))
        finally:
            await asyncio.gather(*(client.stop_and_close() for client in clients))

    class MyHandler(blivedm.BaseHandler):
        # Demo of how to add a custom callback
        _CMD_CALLBACK_DICT = blivedm.BaseHandler._CMD_CALLBACK_DICT.copy()

        # Entrance message callback
        def __interact_word_callback(
            self, client: blivedm.BLiveClient, command: dict
        ):
            # logger.info(f"[{client.room_id}] INTERACT_WORD: self_type={type(self).__name__}, room_id={client.room_id},"
            #     f" uname={command['data']['uname']}")


            my_global.idle_time_auto_clear(config, "entrance")

            username = command["data"]["uname"]

            logger.info(f"User: {username} entered the live room")

            # Add the username to the latest username list
            my_global.add_username_to_last_username_list(username)

            data = {
                "platform": platform,
                "username": username,
                "content": "entered the live room",
            }

            my_handle.process_data(data, "entrance")

        _CMD_CALLBACK_DICT["INTERACT_WORD"] = __interact_word_callback  # noqa

        def _on_heartbeat(
            self, client: blivedm.BLiveClient, message: web_models.HeartbeatMessage
        ):
            logger.debug(f"[{client.room_id}] Heartbeat")

        def _on_danmaku(
            self, client: blivedm.BLiveClient, message: web_models.DanmakuMessage
        ):
            # Reset the idle count
            my_global.idle_time_auto_clear(config, "comment")

            # logger.info(f'[{client.room_id}] {message.uname}:{message.msg}')
            content = message.msg  # Get the danmaku content
            username = message.uname  # Get the nickname of the user who sent the danmaku
            # Check whether the face attribute exists
            user_face = message.face if hasattr(message, "face") else None

            logger.info(f"[{username}]: {content}")

            data = {
                "platform": platform,
                "username": username,
                "user_face": user_face,
                "content": content,
            }

            my_handle.process_data(data, "comment")

        def _on_gift(
            self, client: blivedm.BLiveClient, message: web_models.GiftMessage
        ):
            # logger.info(f'[{client.room_id}] {message.uname} Gift{message.gift_name}x{message.num}'
            #     f' ({message.coin_type} silver melon seeds x{message.total_coin})')
            my_global.idle_time_auto_clear(config, "gift")

            gift_name = message.gift_name
            username = message.uname
            # Check whether the face attribute exists
            user_face = message.face if hasattr(message, "face") else None

            # Gift quantity
            combo_num = message.num
            # Total amount
            combo_total_coin = message.total_coin

            logger.info(
                f"User: {username} gifted {combo_num} x {gift_name}, total {combo_total_coin} batteries"
            )

            data = {
                "platform": platform,
                "gift_name": gift_name,
                "username": username,
                "user_face": user_face,
                "num": combo_num,
                "unit_price": combo_total_coin / combo_num / 1000,
                "total_price": combo_total_coin / 1000,
            }

            my_handle.process_data(data, "gift")

        def _on_buy_guard(
            self, client: blivedm.BLiveClient, message: web_models.GuardBuyMessage
        ):
            logger.info(
                f"[{client.room_id}] {message.username} Purchase{message.gift_name}"
            )

        def _on_super_chat(
            self, client: blivedm.BLiveClient, message: web_models.SuperChatMessage
        ):
            # logger.info(f'[{client.room_id}] Super Chat ¥{message.price} {message.uname}:{message.message}')
            my_global.idle_time_auto_clear(config, "gift")

            message = message.message
            uname = message.uname
            # Check whether the face attribute exists
            user_face = message.face if hasattr(message, "face") else None
            price = message.price

            logger.info(f"User: {uname} sent a {price} yuan SC:{message}")

            data = {
                "platform": platform,
                "gift_name": "SC",
                "username": uname,
                "user_face": user_face,
                "num": 1,
                "unit_price": price,
                "total_price": price,
                "content": message,
            }

            my_handle.process_data(data, "gift")

            my_handle.process_data(data, "comment")

    class MyHandler2(blivedm.BaseHandler):
        def _on_heartbeat(
            self, client: blivedm.BLiveClient, message: web_models.HeartbeatMessage
        ):
            logger.debug(f"[{client.room_id}] Heartbeat")

        def _on_open_live_danmaku(
            self,
            client: blivedm.OpenLiveClient,
            message: open_models.DanmakuMessage,
        ):
            # Reset the idle count
            my_global.idle_time_auto_clear(config, "comment")

            # logger.info(f'[{client.room_id}] {message.uname}:{message.msg}')
            content = message.msg  # Get the danmaku content
            username = message.uname  # Get the nickname of the user who sent the danmaku
            # Check whether the face attribute exists
            user_face = message.face if hasattr(message, "face") else None

            logger.debug(f"User: {username} avatar:{user_face}")

            logger.info(f"[{username}]: {content}")

            data = {
                "platform": platform,
                "username": username,
                "user_face": user_face,
                "content": content,
            }

            my_handle.process_data(data, "comment")

        def _on_open_live_gift(
            self, client: blivedm.OpenLiveClient, message: open_models.GiftMessage
        ):
            my_global.idle_time_auto_clear(config, "gift")

            gift_name = message.gift_name
            username = message.uname
            # Check whether the face attribute exists
            user_face = message.face if hasattr(message, "face") else None
            # Gift quantity
            combo_num = message.gift_num
            # Total amount
            combo_total_coin = message.price * message.gift_num

            logger.info(
                f"User: {username} gifted {combo_num} x {gift_name}, total {combo_total_coin} batteries"
            )

            data = {
                "platform": platform,
                "gift_name": gift_name,
                "username": username,
                "user_face": user_face,
                "num": combo_num,
                "unit_price": combo_total_coin / combo_num / 1000,
                "total_price": combo_total_coin / 1000,
            }

            my_handle.process_data(data, "gift")

        def _on_open_live_buy_guard(
            self,
            client: blivedm.OpenLiveClient,
            message: open_models.GuardBuyMessage,
        ):
            logger.info(
                f"[{client.room_id}] {message.user_info.uname} Purchase Captain level={message.guard_level}"
            )

        def _on_open_live_super_chat(
            self,
            client: blivedm.OpenLiveClient,
            message: open_models.SuperChatMessage,
        ):
            my_global.idle_time_auto_clear(config, "gift")

            logger.info(
                f"[{message.room_id}] Super Chat ¥{message.rmb} {message.uname}:{message.message}"
            )

            message = message.message
            uname = message.uname
            # Check whether the face attribute exists
            user_face = message.face if hasattr(message, "face") else None
            price = message.rmb

            logger.info(f"User: {uname} sent a {price} yuan SC:{message}")

            data = {
                "platform": platform,
                "gift_name": "SC",
                "username": uname,
                "user_face": user_face,
                "num": 1,
                "unit_price": price,
                "total_price": price,
                "content": message,
            }

            my_handle.process_data(data, "gift")

            my_handle.process_data(data, "comment")

        def _on_open_live_super_chat_delete(
            self,
            client: blivedm.OpenLiveClient,
            message: open_models.SuperChatDeleteMessage,
        ):
            logger.info(
                f"[Live room {message.room_id}] deleted a Super Chat message_ids={message.message_ids}"
            )

        def _on_open_live_like(
            self, client: blivedm.OpenLiveClient, message: open_models.LikeMessage
        ):
            logger.info(f"User: {message.uname} liked")

    asyncio.run(main_func())
