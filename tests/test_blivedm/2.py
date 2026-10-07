# -*- coding: utf-8 -*-
import asyncio

import blivedm
import blivedm.models.open_live as open_models
import blivedm.models.web as web_models

config_json = {
    "ACCESS_KEY_ID": "",
    "ACCESS_KEY_SECRET": "",
    "APP_ID": 0,
    "ROOM_OWNER_AUTH_CODE": ""
}

# Developer key applied for on the open platform
ACCESS_KEY_ID = config_json["ACCESS_KEY_ID"]
ACCESS_KEY_SECRET = config_json["ACCESS_KEY_SECRET"]
# Project created on the open platformID
APP_ID = config_json["APP_ID"]
# Streamer identity code
ROOM_OWNER_AUTH_CODE = config_json["ROOM_OWNER_AUTH_CODE"]


async def main():
    await run_single_client()


async def run_single_client():
    """
    Demo of listening to one live room
    """
    client = blivedm.OpenLiveClient(
        access_key_id=ACCESS_KEY_ID,
        access_key_secret=ACCESS_KEY_SECRET,
        app_id=APP_ID,
        room_owner_auth_code=ROOM_OWNER_AUTH_CODE,
    )
    handler = MyHandler()
    client.set_handler(handler)

    client.start()
    try:
        # Demo stops after 70 seconds
        # await asyncio.sleep(70)
        # client.stop()

        await client.join()
    finally:
        await client.stop_and_close()


class MyHandler(blivedm.BaseHandler):
    def _on_heartbeat(self, client: blivedm.BLiveClient, message: web_models.HeartbeatMessage):
        print(f'[{client.room_id}] Heartbeat')

    def _on_open_live_danmaku(self, client: blivedm.OpenLiveClient, message: open_models.DanmakuMessage):
        print(f'[{message.room_id}] {message.uname}:{message.msg}')

    def _on_open_live_gift(self, client: blivedm.OpenLiveClient, message: open_models.GiftMessage):
        coin_type = '金瓜子' if message.paid else '银瓜子'
        total_coin = message.price * message.gift_num
        print(f'[{message.room_id}] {message.uname} Gift{message.gift_name}x{message.gift_num}'
              f' ({coin_type}x{total_coin})')

    def _on_open_live_buy_guard(self, client: blivedm.OpenLiveClient, message: open_models.GuardBuyMessage):
        print(f'[{message.room_id}] {message.user_info.uname} Purchase Captain level={message.guard_level}')

    def _on_open_live_super_chat(
        self, client: blivedm.OpenLiveClient, message: open_models.SuperChatMessage
    ):
        print(f'[{message.room_id}] Super Chat ¥{message.rmb} {message.uname}:{message.message}')

    def _on_open_live_super_chat_delete(
        self, client: blivedm.OpenLiveClient, message: open_models.SuperChatDeleteMessage
    ):
        print(f'[{message.room_id}] Delete super chat message_ids={message.message_ids}')

    def _on_open_live_like(self, client: blivedm.OpenLiveClient, message: open_models.LikeMessage):
        print(f'[{message.room_id}] {message.uname} Like')


if __name__ == '__main__':
    asyncio.run(main())