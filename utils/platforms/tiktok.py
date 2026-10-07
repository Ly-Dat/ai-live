"""
tiktok
"""
import asyncio
import time
import traceback
import json

from TikTokLive import TikTokLiveClient
from TikTokLive.events import (
    CommentEvent,
    ConnectEvent,
    DisconnectEvent,
    JoinEvent,
    GiftEvent,
    FollowEvent,
)

from utils.my_log import logger
import utils.my_global as my_global


def start_listen(config, common, my_handle, platform: str):
    # The room_id of the live room https://www.tiktok.com/@username/live is username
    room_id = my_handle.get_room_id()

    proxys = None

    client: TikTokLiveClient = TikTokLiveClient(
        unique_id=f"@{room_id}", web_proxy=proxys, ws_proxy=proxys
    )

    @client.on(ConnectEvent)
    async def on_connect(_: ConnectEvent):
        logger.info(f"Connect to roomID:{client.room_id}")

    @client.on(DisconnectEvent)
    async def on_disconnect(event: DisconnectEvent):
        logger.info("Disconnected, will automatically reconnect later")

    @client.on(JoinEvent)
    async def on_join(event: JoinEvent):
        my_global.idle_time_auto_clear(config, "entrance")

        username = event.user.nickname

        logger.info(f"[🚹🚺Live room member join message] Welcome {username} to the live room")

        data = {
            "platform": platform,
            "username": username,
            "content": "entered the live room",
        }

        my_global.add_username_to_last_username_list(username)

        my_handle.process_data(data, "entrance")

    @client.on(CommentEvent)
    async def on_comment(event: CommentEvent):
        my_global.idle_time_auto_clear(config, "comment")

        username = event.user.nickname
        content = event.comment

        logger.info(f"[📧Live room danmaku message] [{username}]:{content}")

        data = {"platform": platform, "username": username, "content": content}

        my_handle.process_data(data, "comment")

    @client.on(GiftEvent)
    async def on_gift(event: GiftEvent):
        my_global.idle_time_auto_clear(config, "gift")

        # The combo gift is still combo-ing, handle it after it ends
        if event.gift.streakable and event.streaking:
            return

        repeat_count = event.repeat_count if event.gift.streakable else 1

        gift_name = event.gift.name
        username = event.user.nickname
        num = 1

        try:
            data_path = "data/tiktok礼物价格表.json"

            with open(data_path, "r", encoding="utf-8") as file:
                data_json = json.load(file)

            if gift_name in data_json:
                discount_price = data_json[gift_name]
            else:
                logger.warning(
                    f"There is no value for {gift_name} in the data file: {data_path}, please add the data manually"
                )
                discount_price = 1
        except Exception:
            logger.error(traceback.format_exc())
            discount_price = 1

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

    @client.on(FollowEvent)
    async def on_follow(event: FollowEvent):
        my_global.idle_time_auto_clear(config, "follow")

        username = event.user.nickname

        logger.info(f"[➕Live room follow message] Thanks {username} for following")

        data = {"platform": platform, "username": username}

        my_handle.process_data(data, "follow")

    # Automatically retry when disconnected or offline
    while True:
        try:
            logger.info(f"Connecting to {room_id}...")
            client.run()
        except Exception as e:
            logger.error(f"Connection failed:{e}")
            logger.info(f"User ID: @{room_id} seems to be offline, retrying in 60 seconds...")
        time.sleep(60)