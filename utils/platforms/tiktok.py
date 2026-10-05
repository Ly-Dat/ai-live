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
    # 直播间 https://www.tiktok.com/@username/live 的 room_id 就是 username
    room_id = my_handle.get_room_id()

    proxys = None

    client: TikTokLiveClient = TikTokLiveClient(
        unique_id=f"@{room_id}", web_proxy=proxys, ws_proxy=proxys
    )

    @client.on(ConnectEvent)
    async def on_connect(_: ConnectEvent):
        logger.info(f"连接到 房间ID:{client.room_id}")

    @client.on(DisconnectEvent)
    async def on_disconnect(event: DisconnectEvent):
        logger.info("断开连接，稍后自动重连")

    @client.on(JoinEvent)
    async def on_join(event: JoinEvent):
        my_global.idle_time_auto_clear(config, "entrance")

        username = event.user.nickname

        logger.info(f"[🚹🚺直播间成员加入消息] 欢迎 {username} 进入直播间")

        data = {
            "platform": platform,
            "username": username,
            "content": "进入直播间",
        }

        my_global.add_username_to_last_username_list(username)

        my_handle.process_data(data, "entrance")

    @client.on(CommentEvent)
    async def on_comment(event: CommentEvent):
        my_global.idle_time_auto_clear(config, "comment")

        username = event.user.nickname
        content = event.comment

        logger.info(f"[📧直播间弹幕消息] [{username}]：{content}")

        data = {"platform": platform, "username": username, "content": content}

        my_handle.process_data(data, "comment")

    @client.on(GiftEvent)
    async def on_gift(event: GiftEvent):
        my_global.idle_time_auto_clear(config, "gift")

        # 连击礼物还在连击中，等结束再处理
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
                    f"数据文件：{data_path} 中，没有 {gift_name} 对应的价值，请手动补充数据"
                )
                discount_price = 1
        except Exception:
            logger.error(traceback.format_exc())
            discount_price = 1

        combo_total_coin = repeat_count * discount_price

        logger.info(
            f"[🎁直播间礼物消息] 用户：{username} 赠送 {num} 个 {gift_name}，单价 {discount_price}抖币，总计 {combo_total_coin}抖币"
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

        logger.info(f"[➕直播间关注消息] 感谢 {username} 的关注")

        data = {"platform": platform, "username": username}

        my_handle.process_data(data, "follow")

    # 断线/不在线时自动重试
    while True:
        try:
            logger.info(f"连接{room_id}中...")
            client.run()
        except Exception as e:
            logger.error(f"连接失败：{e}")
            logger.info(f"用户ID: @{room_id} 好像不在线, 60秒后重试...")
        time.sleep(60)