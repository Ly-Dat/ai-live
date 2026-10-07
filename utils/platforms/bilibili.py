from bilibili_api import Credential, live, sync, login
import os
import traceback

from utils.my_log import logger
import utils.my_global as my_global

def start_listen(config, common, my_handle, platform: str):
    platform = "bilibili"

    try:
        if config.get("bilibili", "login_type") == "cookie":
            logger.info(
                "bAfter logging in to the site, press F12 and capture network packets to get the cookie; using an alt account is strongly recommended! There is a risk of being banned"
            )
            logger.info(
                "bAfter logging in to the site, open the F12 console, enter window.localStorage.ac_time_value and press Enter to get it (if there is none, please log in again)"
            )

            bilibili_cookie = config.get("bilibili", "cookie")
            bilibili_ac_time_value = config.get("bilibili", "ac_time_value")
            if bilibili_ac_time_value == "":
                bilibili_ac_time_value = None

            # logger.info(f'SESSDATA={common.parse_cookie_data(bilibili_cookie, "SESSDATA")}')
            # logger.info(f'bili_jct={common.parse_cookie_data(bilibili_cookie, "bili_jct")}')
            # logger.info(f'buvid3={common.parse_cookie_data(bilibili_cookie, "buvid3")}')
            # logger.info(f'DedeUserID={common.parse_cookie_data(bilibili_cookie, "DedeUserID")}')

            # Generate a Credential object
            credential = Credential(
                sessdata=common.parse_cookie_data(bilibili_cookie, "SESSDATA"),
                bili_jct=common.parse_cookie_data(bilibili_cookie, "bili_jct"),
                buvid3=common.parse_cookie_data(bilibili_cookie, "buvid3"),
                dedeuserid=common.parse_cookie_data(bilibili_cookie, "DedeUserID"),
                ac_time_value=bilibili_ac_time_value,
            )
        elif config.get("bilibili", "login_type") == "Scan QR with phone":
            credential = login.login_with_qrcode()
        elif config.get("bilibili", "login_type") == "Scan QR with phone - terminal":
            credential = login.login_with_qrcode_term()
        elif config.get("bilibili", "login_type") == "Account & password login":
            bilibili_username = config.get("bilibili", "username")
            bilibili_password = config.get("bilibili", "password")

            credential = login.login_with_password(
                bilibili_username, bilibili_password
            )
        elif config.get("bilibili", "login_type") == "No login":
            credential = None
        else:
            credential = login.login_with_qrcode()

        # Initialize the Bilibili live room
        room = live.LiveDanmaku(my_handle.get_room_id(), credential=credential)
    except Exception as e:
        logger.error(traceback.format_exc())
        my_handle.abnormal_alarm_handle("platform")
        # os._exit(0)

    """
    DANMU_MSG: User sends danmaku
    SEND_GIFT: Gift
    COMBO_SEND: gift combo
    GUARD_BUY: Captain renewal
    SUPER_CHAT_MESSAGE: Super Chat (SC)
    SUPER_CHAT_MESSAGE_JPN: Super Chat (with Japanese translation?)
    WELCOME: Master entering the room
    WELCOME_GUARD: Administrator entering the room
    NOTICE_MSG: System notification (such as site-wide broadcasts)
    PREPARING: Stream is being prepared
    LIVE: Stream started
    ROOM_REAL_TIME_MESSAGE_UPDATE: Follower count and other updates
    ENTRY_EFFECT: Entrance effect
    ROOM_RANK: Room ranking update
    INTERACT_WORD: User enters the live room
    ACTIVITY_BANNER_UPDATE_V2: It seems to be the xx-hour ranking next to the room name
    Custom events of this module:
    VIEW: Live room popularity update
    ALL: All events
    DISCONNECT: Disconnect (pass the connection status code parameter)
    TIMEOUT: Heartbeat response timeout
    VERIFICATION_SUCCESSFUL: Authentication succeeded
    """

    @room.on("DANMU_MSG")
    async def _(event):
        """
        Handle live room danmaku events
        :param event: Danmaku event data
        """

        # Reset the idle count
        my_global.idle_time_auto_clear(config, "comment")

        content = event["data"]["info"][1]  # Get the danmaku content
        username = event["data"]["info"][2][1]  # Get the nickname of the user who sent the danmaku

        logger.info(f"[{username}]: {content}")

        data = {"platform": platform, "username": username, "content": content}

        my_handle.process_data(data, "comment")

    @room.on("COMBO_SEND")
    async def _(event):
        """
        Handle live room gift combo events
        :param event: Gift combo event data
        """
        my_global.idle_time_auto_clear(config, "gift")

        gift_name = event["data"]["data"]["gift_name"]
        username = event["data"]["data"]["uname"]
        # Gift quantity
        combo_num = event["data"]["data"]["combo_num"]
        # Total amount
        combo_total_coin = event["data"]["data"]["combo_total_coin"]

        logger.info(
            f"User: {username} gifted {combo_num} x {gift_name}, total {combo_total_coin} batteries"
        )

        data = {
            "platform": platform,
            "gift_name": gift_name,
            "username": username,
            "num": combo_num,
            "unit_price": combo_total_coin / combo_num / 1000,
            "total_price": combo_total_coin / 1000,
        }

        my_handle.process_data(data, "gift")

    @room.on("SEND_GIFT")
    async def _(event):
        """
        Handle live room gift events
        :param event: Gift event data
        """
        my_global.idle_time_auto_clear(config, "gift")

        # logger.info(event)

        gift_name = event["data"]["data"]["giftName"]
        username = event["data"]["data"]["uname"]
        # Gift quantity
        num = event["data"]["data"]["num"]
        # Total amount
        combo_total_coin = event["data"]["data"]["combo_total_coin"]
        # Single gift amount
        discount_price = event["data"]["data"]["discount_price"]

        logger.info(
            f"User: {username} gifted {num} x {gift_name}, unit price {discount_price} batteries, total {combo_total_coin} batteries"
        )

        data = {
            "platform": platform,
            "gift_name": gift_name,
            "username": username,
            "num": num,
            "unit_price": discount_price / 1000,
            "total_price": combo_total_coin / 1000,
        }

        my_handle.process_data(data, "gift")

    @room.on("GUARD_BUY")
    async def _(event):
        """
        Handle live room Captain renewal events
        :param event: Captain renewal event data
        """

        logger.info(event)

    @room.on("SUPER_CHAT_MESSAGE")
    async def _(event):
        """
        Handle live room Super Chat (SC) events
        :param event: Super Chat (SC) event data
        """
        my_global.idle_time_auto_clear(config, "gift")

        message = event["data"]["data"]["message"]
        uname = event["data"]["data"]["user_info"]["uname"]
        price = event["data"]["data"]["price"]

        logger.info(f"User: {uname} sent a {price} yuan SC:{message}")

        data = {
            "platform": platform,
            "gift_name": "SC",
            "username": uname,
            "num": 1,
            "unit_price": price,
            "total_price": price,
            "content": message,
        }

        my_handle.process_data(data, "gift")

        my_handle.process_data(data, "comment")

    @room.on("INTERACT_WORD")
    async def _(event):
        """
        Handle live room user entering the live room events
        :param event: User entering the live room event data
        """

        my_global.idle_time_auto_clear(config, "entrance")

        username = event["data"]["data"]["uname"]

        logger.info(f"User: {username} entered the live room")

        # Add the username to the latest username list
        my_global.add_username_to_last_username_list(username)

        data = {"platform": platform, "username": username, "content": "entered the live room"}

        my_handle.process_data(data, "entrance")

    # @room.on('WELCOME')
    # async def _(event):
    #     """
    #     Handle live room Master entering the room events
    #     :param event: Master entering the room event data
    #     """

    #     logger.info(event)

    # @room.on('WELCOME_GUARD')
    # async def _(event):
    #     """
    #     Handle live room administrator entering the room events
    #     :param event: Administrator entering the room event data
    #     """

    #     logger.info(event)

    try:
        # Start the Bilibili live room connection
        sync(room.connect())
    except KeyboardInterrupt:
        logger.warning("The program was forcibly exited")
    finally:
        logger.warning("Closing the connection... it may be caused by a wrong live room number config or other reasons")
        os._exit(0)