#!/usr/bin/python
# coding:utf-8

# @FileName:    liveMan.py
# @Time:        2024/1/2 21:51
# @Author:      bubu
# @Project:     douyinLiveWebFetcher
import gzip
import random
import re
import string

import requests
import websocket
from protobuf.douyin import *


def generateMsToken(length=107):
    """
    Generate the msToken field in the request header cookie, which is actually a random 107-character string
    :param length:Number of characters
    :return:msToken
    """
    random_str = ''
    base_str = string.ascii_letters + string.digits + '=_'
    _len = len(base_str) - 1
    for _ in range(length):
        random_str += base_str[random.randint(0, _len)]
    return random_str


def generateTtwid():
    """
    Generate the ttwid field in the request header cookie, which can be obtained from the response cookie when visiting the Douyin web live room home pagettwid
    :return: ttwid
    """
    url = "https://live.douyin.com/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except Exception as err:
        print("[X]request the live url error: ", err)
    else:
        return response.cookies.get('ttwid')


class DouyinLiveWebFetcher:
    
    def __init__(self, live_id):
        """
        Live room danmaku (chat) scraper object
        :param live_id: The live id of the live room, e.g. the link to the live room web home page: https://live.douyin.com/261378947940,
                        Where 261378947940 is thelive_id
        """
        self.__ttwid = None
        self.__room_id = None
        self.is_connected = None
        self.live_id = live_id
        self.live_url = "https://live.douyin.com/"
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) " \
                          "Chrome/120.0.0.0 Safari/537.36"
    
    def send_heartbeat(self, ws):
        import time, threading

        def heartbeat():
            while True:
                time.sleep(15)#Send a heartbeat every 15 seconds
                if self.is_connected:
                    ws.send("hi")#Use the actual heartbeat message format
                else:
                    print( "Connection lost, stopping heartbeat.")
                    return
        threading.Thread(target=heartbeat).start()

            
    def start(self):
        self._connectWebSocket()
    
    def stop(self):
        self.ws.close()
    
    @property
    def ttwid(self):
        """
        Generate the ttwid field in the request header cookie, which can be obtained from the response cookie when visiting the Douyin web live room home pagettwid
        :return: ttwid
        """
        if self.__ttwid:
            return self.__ttwid
        headers = {
            "User-Agent": self.user_agent,
        }
        try:
            response = requests.get(self.live_url, headers=headers)
            response.raise_for_status()
        except Exception as err:
            print("[X]Request the live url error: ", err)
        else:
            self.__ttwid = response.cookies.get('ttwid')
            return self.__ttwid
    
    @property
    def room_id(self):
        """
        Get the real live room roomId from the live room address; errors sometimes occur and can be fixed by retrying the request
        :return:room_id
        """
        if self.__room_id:
            return self.__room_id
        url = self.live_url + self.live_id
        headers = {
            "User-Agent": self.user_agent,
            "cookie": f"ttwid={self.ttwid}&msToken={generateMsToken()}; __ac_nonce=0123407cc00a9e438deb4",
        }
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
        except Exception as err:
            print("[X]Request the live room url error: ", err)
        else:
            match = re.search(r'roomId\\":\\"(\d+)\\"', response.text)
            if match is None or len(match.groups()) < 1:
                print("[X]No match found for roomId")
            
            self.__room_id = match.group(1)
            
            return self.__room_id
    
    def _connectWebSocket(self):
        """
        Connect to the Douyin live room websocket server and request live room data
        """
        # wss = f"wss://webcast3-ws-web-lq.douyin.com/webcast/im/push/v2/?" \
        #       f"app_name=douyin_web&version_code=180800&webcast_sdk_version=1.3.0&update_version_code=1.3.0" \
        #       f"&compress=gzip" \
        #       f"&internal_ext=internal_src:dim|wss_push_room_id:{self.room_id}|wss_push_did:{self.room_id}" \
        #       f"|dim_log_id:202302171547011A160A7BAA76660E13ED|fetch_time:1676620021641|seq:1|wss_info:0-1676" \
        #       f"620021641-0-0|wrds_kvs:WebcastRoomStatsMessage-1676620020691146024_WebcastRoomRankMessage-167661" \
        #       f"9972726895075_AudienceGiftSyncData-1676619980834317696_HighlightContainerSyncData-2&cursor=t-1676" \
        #       f"620021641_r-1_d-1_u-1_h-1" \
        #       f"&host=https://live.douyin.com&aid=6383&live_id=1" \
        #       f"&did_rule=3&debug=false&endpoint=live_pc&support_wrds=1&" \
        #       f"im_path=/webcast/im/fetch/&user_unique_id={self.room_id}&" \
        #       f"device_platform=web&cookie_enabled=true&screen_width=1440&screen_height=900&browser_language=zh&" \
        #       f"browser_platform=MacIntel&browser_name=Mozilla&" \
        #       f"browser_version=5.0%20(Macintosh;%20Intel%20Mac%20OS%20X%2010_15_7)%20AppleWebKit/537.36%20(KHTML,%20" \
        #       f"like%20Gecko)%20Chrome/110.0.0.0%20Safari/537.36&" \
        #       f"browser_online=true&tz_name=Asia/Shanghai&identity=audience&" \
        #       f"room_id={self.room_id}&heartbeatDuration=0&signature=00000000"

        wss = "wss://webcast5-ws-web-lq.douyin.com/webcast/im/push/v2/?app_name=douyin_web&version_code=180800&webcast_sdk_version=1.0.14-beta.0&update_version_code=1.0.14-beta.0&compress=gzip&device_platform=web&cookie_enabled=true&screen_width=2048&screen_height=1152&browser_language=zh-CN&browser_platform=Win32&browser_name=Mozilla&browser_version=5.0%20(Windows%20NT%2010.0;%20Win64;%20x64)%20AppleWebKit/537.36%20(KHTML,%20like%20Gecko)%20Chrome/126.0.0.0%20Safari/537.36%20Edg/126.0.0.0&browser_online=true&tz_name=Etc/GMT-8&cursor=h-7383323426352862262_t-1719063974519_r-1_d-1_u-1&internal_ext=internal_src:dim|wss_push_room_id:7383264938631973686|wss_push_did:7293153952199050788|first_req_ms:1719063974385|fetch_time:1719063974519|seq:1|wss_info:0-1719063974519-0-0|wrds_v:7383323492227230262&host=https://live.douyin.com&aid=6383&live_id=1&did_rule=3&endpoint=live_pc&support_wrds=1&user_unique_id=7293153952199050788&im_path=/webcast/im/fetch/&identity=audience&need_persist_msg_count=15&insert_task_id=&live_reason=&room_id=7383264938631973686&heartbeatDuration=0&signature=6DJMtCOOuubiYZP4"

        headers = {
            "cookie": f"ttwid={self.ttwid}",
            'user-agent': self.user_agent,
        }
        self.ws = websocket.WebSocketApp(wss,
                                         header=headers,
                                         on_open=self._wsOnOpen,
                                         on_message=self._wsOnMessage,
                                         on_error=self._wsOnError,
                                         on_close=self._wsOnClose)
        try:
            self.ws.run_forever()
        except Exception:
            self.stop()
            raise
    
    def _wsOnOpen(self, ws):
        """
        Connection established successfully
        """
        print("WebSocket connected.")
        self.is_connected = True
    
    def _wsOnMessage(self, ws, message):
        """
        Data received
        :param ws: websocketInstance
        :param message: Data
        """
        
        # Parse the object according to the proto structure
        package = PushFrame().parse(message)
        response = Response().parse(gzip.decompress(package.payload))
        
        # Return a keep-alive confirmation message to the live room server connection so data keeps coming
        if response.need_ack:
            ack = PushFrame(log_id=package.log_id,
                            payload_type='ack',
                            payload=response.internal_ext.encode('utf-8')
                            ).SerializeToString()
            ws.send(ack, websocket.ABNF.OPCODE_BINARY)
        
        # Parse the message body according to the message type
        for msg in response.messages_list:
            method = msg.method
            try:
                {
                    'WebcastChatMessage': self._parseChatMsg,  # Chat message
                    'WebcastGiftMessage': self._parseGiftMsg,  # Gift message
                    'WebcastLikeMessage': self._parseLikeMsg,  # Like message
                    'WebcastMemberMessage': self._parseMemberMsg,  # Enter live room message
                    'WebcastSocialMessage': self._parseSocialMsg,  # Follow message
                    'WebcastRoomUserSeqMessage': self._parseRoomUserSeqMsg,  # Live room stats
                    'WebcastFansclubMessage': self._parseFansclubMsg,  # Fan club message
                    'WebcastControlMessage': self._parseControlMsg,  # Live room status message
                    'WebcastEmojiChatMessage': self._parseEmojiChatMsg,  # Chat emoji message
                    'WebcastRoomStatsMessage': self._parseRoomStatsMsg,  # Live room stats info
                    'WebcastRoomMessage': self._parseRoomMsg,  # Live room info
                    'WebcastRoomRankMessage': self._parseRankMsg,  # Live room ranking info
                }.get(method)(msg.payload)
            except Exception:
                pass
    
    def _wsOnError(self, ws, error):
        print("WebSocket error: ", error)
        self.is_connected = False
    
    def _wsOnClose(self, ws):
        print("WebSocket connection closed.")
        self.is_connected = False
    
    def _parseChatMsg(self, payload):
        '''Chat message'''
        message = ChatMessage().parse(payload)
        user_name = message.user.nick_name
        user_id = message.user.id
        content = message.content
        print(f"[Chat msg][{user_id}]{user_name}: {content}")
    
    def _parseGiftMsg(self, payload):
        '''Gift message'''
        message = GiftMessage().parse(payload)
        user_name = message.user.nick_name
        gift_name = message.gift.name
        gift_cnt = message.combo_count
        print(f"[Gift msg] {user_name} sent {gift_name}x{gift_cnt}")
    
    def _parseLikeMsg(self, payload):
        '''Like message'''
        message = LikeMessage().parse(payload)
        user_name = message.user.nick_name
        count = message.count
        print(f"[Like msg] {user_name} liked {count} times")
    
    def _parseMemberMsg(self, payload):
        '''Enter live room message'''
        message = MemberMessage().parse(payload)
        user_name = message.user.nick_name
        user_id = message.user.id
        gender = ["Female", "Male"][message.user.gender]
        print(f"[Entry msg] [{user_id}][{gender}]{user_name} entered the live room")
    
    def _parseSocialMsg(self, payload):
        '''Follow message'''
        message = SocialMessage().parse(payload)
        user_name = message.user.nick_name
        user_id = message.user.id
        print(f"[Follow msg] [{user_id}]{user_name} followed the streamer")
    
    def _parseRoomUserSeqMsg(self, payload):
        '''Live room stats'''
        message = RoomUserSeqMessage().parse(payload)
        current = message.total
        total = message.total_pv_for_anchor
        print(f"[Stats msg] Current viewers: {current}, total viewers: {total}")
    
    def _parseFansclubMsg(self, payload):
        '''Fan club message'''
        message = FansclubMessage().parse(payload)
        content = message.content
        print(f"[Fan club msg] {content}")
    
    def _parseEmojiChatMsg(self, payload):
        '''Chat emoji message'''
        message = EmojiChatMessage().parse(payload)
        emoji_id = message.emoji_id
        user = message.user
        common = message.common
        default_content = message.default_content
        print(f"[Chat emoji id] {emoji_id},user: {user},common:{common},default_content:{default_content}")
    
    def _parseRoomMsg(self, payload):
        message = RoomMessage().parse(payload)
        common = message.common
        room_id = common.room_id
        print(f"[Live room msg] Live roomid:{room_id}")
    
    def _parseRoomStatsMsg(self, payload):
        message = RoomStatsMessage().parse(payload)
        display_long = message.display_long
        print(f"[Live room stats msg]{display_long}")
    
    def _parseRankMsg(self, payload):
        message = RoomRankMessage().parse(payload)
        ranks_list = message.ranks_list
        print(f"[Live room ranking msg]{ranks_list}")
    
    def _parseControlMsg(self, payload):
        '''Live room status message'''
        message = ControlMessage().parse(payload)
        
        if message.status == 3:
            print("Live room has ended")
            self.stop()


if __name__ == '__main__':
    live_id = '386798490464'
    DouyinLiveWebFetcher(live_id).start()
