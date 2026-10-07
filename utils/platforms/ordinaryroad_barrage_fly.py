from asyncio import Event
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import AsyncGenerator, Tuple

from reactivestreams.subscriber import Subscriber
from reactivestreams.subscription import Subscription
from rsocket.helpers import single_transport_provider
from rsocket.payload import Payload
from rsocket.rsocket_client import RSocketClient
from rsocket.streams.stream_from_async_generator import StreamFromAsyncGenerator
from rsocket.transports.aiohttp_websocket import TransportAioHttpClient

import json
import aiohttp
import asyncio
import traceback

from utils.my_log import logger
import utils.my_global as my_global

def start_listen(config, common, my_handle, platform: str):
    subscribe_payload_json = {
        "data": {
            "taskIds": [],
            "cmd": "SUBSCRIBE"
        }
    }


    class ChannelSubscriber(Subscriber):
        def __init__(self, wait_for_responder_complete: Event) -> None:
            super().__init__()
            self.subscription = None
            self._wait_for_responder_complete = wait_for_responder_complete

        def on_subscribe(self, subscription: Subscription):
            self.subscription = subscription
            self.subscription.request(0x7FFFFFFF)

        # TODO Message callback received
        def on_next(self, value: Payload, is_complete=False):
            try:
                msg_dto = json.loads(value.data)
                if type(msg_dto) != dict:
                    return
                msg_type = msg_dto.get('type')
                # Output directly
                if msg_type == "DANMU":
                    msg = msg_dto['msg']
                    # logger.info(
                    #     f"{msg_dto['roomId']} Danmaku received {str(msg['badgeLevel']) + str(msg['badgeName']) if msg['badgeLevel'] != 0 else ''} {msg['username']}({str(msg['uid'])}):{msg['content']}"
                    # )
                    username = msg['username']
                    content = msg['content']
                    logger.info(f"[Rang Danmu Fei-{msg_dto['platform']}-{msg_dto['roomId']}] [{username}]: {content}")

                    data = {
                        "platform": platform,
                        "username": username,
                        "content": content,
                    }

                    my_handle.process_data(data, "comment")
                elif msg_type == "GIFT":
                    msg = msg_dto['msg']
                    logger.debug(msg)
                    # logger.info(
                    #     f"{msg_dto['roomId']} Gift received {str(msg['badgeLevel']) + str(msg['badgeName']) if msg['badgeLevel'] != 0 else ''} {msg['username']}({str(msg['uid'])}) {str(msg['data']['action']) if msg.get('data') is not None and msg.get('data').get('action') is not None else 'Gift'} {msg['giftName']}({str(msg['giftId'])})x{str(msg['giftCount'])}({str(msg['giftPrice'])})"
                    # )
                    username = msg['username']
                    gift_name = msg['giftName']
                    combo_num = msg['giftCount']
                    combo_total_coin = combo_num * msg['giftPrice']
                    logger.info(
                        f"[Rang Danmu Fei-{msg_dto['platform']}-{msg_dto['roomId']}] [{username}] gifted {combo_num} x {gift_name}, total {combo_total_coin}"
                    )

                    # TODO: amount conversion
                    data = {
                        "platform": platform,
                        "gift_name": gift_name,
                        "username": username,
                        # "user_face": user_face,
                        "num": combo_num,
                        "unit_price": combo_total_coin / combo_num,
                        "total_price": combo_total_coin,
                    }

                    my_handle.process_data(data, "gift")
                elif msg_type == "ENTER_ROOM":
                    msg = msg_dto['msg']
                    username = msg['username']
                    logger.info(f"[Rang Danmu Fei-{msg_dto['platform']}-{msg_dto['roomId']}] Welcome {username} to the live room")

                    data = {
                        "platform": platform,
                        "username": username,
                        "content": "entered the live room",
                    }

                    # Add the username to the latest username list
                    my_global.add_username_to_last_username_list(username)

                    my_handle.process_data(data, "entrance")
                elif msg_type == "LIKE":
                    msg = msg_dto['msg']
                    logger.debug(msg)
                    username = msg['username']
                    clickCount = msg['clickCount']
                    logger.info(f"[Rang Danmu Fei-{msg_dto['platform']}-{msg_dto['roomId']}] [{username}] liked {clickCount} times")
                # Discard useless messages
                elif msg_type in ["inter_h5_game_data_update"]:
                    pass
                else:
                    # Message received right after connecting to ws
                    if "status" in msg_dto:
                        pass
                    else:
                        logger.debug(msg_dto)
                        logger.debug(f"[Rang Danmu Fei-{msg_dto['platform']}-{msg_dto['roomId']}] Message received " + json.dumps(msg_dto))
                if is_complete:
                    self._wait_for_responder_complete.set()
            except Exception as e:
                logger.error(traceback.format_exc())

        def on_error(self, exception: Exception):
            logger.error('Error from server on channel' + str(exception))
            self._wait_for_responder_complete.set()

        def on_complete(self):
            logger.info('Completed from server on channel')
            self._wait_for_responder_complete.set()


    @asynccontextmanager
    async def connect(websocket_uri):
        """
        Create a Client, establish a connection andreturn
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(websocket_uri) as websocket:
                    async with RSocketClient(
                            single_transport_provider(TransportAioHttpClient(websocket=websocket)),
                            keep_alive_period=timedelta(seconds=30),
                            max_lifetime_period=timedelta(days=1)
                    ) as client:
                        yield client
        except Exception as e:
            logger.error(traceback.format_exc())

    async def main(websocket_uri):
        try:
            # 1 Establish connection
            async with connect(websocket_uri) as client:
                # Block and wait for the Channel close event
                channel_completion_event = Event()

                # Define the messages the Client sends to the ChannelPublisher
                # PythonThere are no anonymous inner classes, so define a method here as a parameter and pass it to the StreamFromAsyncGenerator class
                async def generator() -> AsyncGenerator[Tuple[Payload, bool], None]:
                    # 2 Send the subscription Task request
                    # Payload: message the Client sends to the Server through the Channel; False means no need to closeChannel
                    yield Payload(
                        data=json.dumps(subscribe_payload_json["data"]).encode()
                    ), False
                    # After sending one subscription message, simply pause sending
                    await Event().wait()

                stream = StreamFromAsyncGenerator(generator)

                # ClientRequest a Channel, leave Payload empty,turn StreamHandler
                requested = client.request_channel(Payload(), stream)

                # 3 Subscribe to the Channel; ChannelSubscriber handles the messages the Server replies through the Channel
                requested.subscribe(ChannelSubscriber(channel_completion_event))

                await channel_completion_event.wait()
        except Exception as e:
            logger.error(traceback.format_exc())
            my_handle.abnormal_alarm_handle("platform")

    if config.get("ordinaryroad_barrage_fly", "taskIds") == []:
        logger.error("Please configure the listener task ID list for Rang Danmu Fei first!")
    else:
        subscribe_payload_json["data"]["taskIds"] = config.get("ordinaryroad_barrage_fly", "taskIds") 
        logger.info(subscribe_payload_json)
        asyncio.run(main(config.get("ordinaryroad_barrage_fly", "ws_ip_port")))