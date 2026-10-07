from playwright.sync_api import sync_playwright, TimeoutError
from google.protobuf.json_format import MessageToDict
from configparser import ConfigParser
import kuaishou_pb2

import os
import threading
import traceback
import time

from utils.my_log import logger
import utils.my_global as my_global

def start_listen(config, common, my_handle, platform: str):
    class kslive(object):
        def __init__(self):
            global config, common, my_handle

            self.path = os.path.abspath("")
            self.chrome_path = r"\firefox-1419\firefox\firefox.exe"
            self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0"
            self.uri = "https://live.kuaishou.com/u/"
            self.context = None
            self.browser = None
            self.page = None

            try:
                self.live_ids = config.get("room_display_id")
                self.thread = 2
                # A mostly useless phone number config, just for convenient login
                self.phone = "123"
            except Exception as e:
                logger.error(traceback.format_exc())
                logger.error("Please check the config file")
                my_handle.abnormal_alarm_handle("platform")
                exit()

        def find_file(self, find_path, file_type) -> list:
            """
            Find files
            :param find_path: Subpath
            :param file_type: File type
            :return:
            """
            path = self.path + "\\" + find_path
            data_list = []
            for root, dirs, files in os.walk(path):
                if root != path:
                    break
                for file in files:
                    file_path = os.path.join(root, file)
                    if file_path.find(file_type) != -1:
                        data_list.append(file_path)
            return data_list

        def main(self, lid, semaphore):
            if not os.path.exists(self.path + "\\cookie"):
                os.makedirs(self.path + "\\cookie")

            cookie_path = self.path + "\\cookie\\" + self.phone + ".json"
            # if not os.path.exists(cookie_path):
            #     with open(cookie_path, 'w') as file:
            #         file.write('{"a":"a"}')
            #     logger.info(f"'{cookie_path}' Created successfully")
            # else:
            #     logger.info(f"'{cookie_path}' Already exists, no need to create")

            with semaphore:
                thread_name = threading.current_thread().name.split("-")[0]
                with sync_playwright() as p:
                    self.browser = p.chromium.launch(headless=False)
                    # self.browser = p.firefox.launch(headless=False)
                    # executable_path=self.path + self.chrome_path
                    cookie_list = self.find_file("cookie", "json")

                    live_url = self.uri + lid

                    if not os.path.exists(cookie_path):
                        self.context = self.browser.new_context(
                            storage_state=None, user_agent=self.ua
                        )
                    else:
                        self.context = self.browser.new_context(
                            storage_state=cookie_list[0], user_agent=self.ua
                        )
                    self.page = self.context.new_page()
                    self.page.add_init_script(
                        "Object.defineProperties(navigator, {webdriver:{get:()=>undefined}});"
                    )
                    self.page.goto("https://live.kuaishou.com/")
                    # self.page.goto(live_url)
                    element = self.page.get_attribute(".no-login", "style")

                    if not element:
                        logger.info("Not logged in, please log in first~")
                        self.page.locator(".login").click()
                        self.page.locator(
                            "li.tab-panel:nth-child(2) > h4:nth-child(1)"
                        ).click()
                        self.page.locator(
                            "div.normal-login-item:nth-child(1) > div:nth-child(1) > input:nth-child(1)"
                        ).fill(self.phone)
                    try:
                        self.page.wait_for_selector(
                            "#app > section > div.header-placeholder > header > div.header-main > "
                            "div.right-part > div.user-info > div.tooltip-trigger > span",
                            timeout=1000 * 60 * 2,
                        )
                        if not os.path.exists(self.path + "\\cookie"):
                            os.makedirs(self.path + "\\cookie")
                        self.context.storage_state(path=cookie_path)
                        # Check whether streaming has started
                        selector = (
                            "html body div#app div.live-room div.detail div.player "
                            "div.kwai-player.kwai-player-container.kwai-player-rotation-0 "
                            "div.kwai-player-container-video div.kwai-player-plugins div.center-state div.state "
                            "div.no-live-detail div.desc p.tip"
                        )  # Selector for detecting the stream ending while live
                        try:
                            msg = self.page.locator(selector).text_content(
                                timeout=3000
                            )
                            logger.info("Current%s" % thread_name + "," + msg)
                            self.context.close()
                            self.browser.close()

                        except Exception as e:
                            logger.info("Current %s, [%s] is live streaming" % (thread_name, lid))

                            logger.info(f"Navigate to the live room:{live_url}")
                            # self.page.goto(live_url)
                            # time.sleep(1)

                            self.page.goto(live_url)

                            # Wait a while and check whether a captcha popup appears
                            try:
                                captcha_selector = "html body div.container"  # Assume this is the selector of the captcha popup
                                self.page.wait_for_selector(
                                    captcha_selector, timeout=5000
                                )  # Wait 5 seconds to see whether a captcha appears
                                logger.info("Captcha detected, handling the captcha...")
                                # Wait for the captcha popup to be completely removed from the DOM
                                self.page.wait_for_selector(
                                    captcha_selector,
                                    state="detached",
                                    timeout=10000,
                                )  # Assume the captcha verification completes within 10 seconds at most
                                logger.info("Captcha verified, popup removed")
                                # Wait 1 second after the popup handling logic
                                time.sleep(1)
                                # After handling the captcha, you may need to navigate to the page again
                                # self.page.goto(live_url)
                            except TimeoutError:
                                logger.error("No captcha detected, continuing...")

                            logger.info(f"Please manually open the live room within 10s:{live_url}")

                            time.sleep(10)

                            self.page.on("websocket", self.web_sockets)
                            logger.info(f"24hListen to the live room and wait for the stream to end...")
                            self.page.wait_for_selector(selector, timeout=86400000)
                            logger.error(
                                "Current %s, the live stream of [%s] has ended" % (thread_name, lid)
                            )
                            self.context.close()
                            self.browser.close()

                    except Exception as e:
                        logger.error(traceback.format_exc())
                        self.context.close()
                        self.browser.close()

        def web_sockets(self, web_socket):
            logger.info("web_sockets...")
            urls = web_socket.url
            logger.info(urls)
            if "/websocket" in urls:
                logger.info("websocketConnected successfully, creating listener events")
                web_socket.on("close", self.websocket_close)
                web_socket.on("framereceived", self.handler)

        def websocket_close(self):
            self.context.close()
            self.browser.close()

        def handler(self, websocket):
            Message = kuaishou_pb2.SocketMessage()
            Message.ParseFromString(websocket)
            if Message.payloadType == 310:
                SCWebFeedPUsh = kuaishou_pb2.SCWebFeedPush()
                SCWebFeedPUsh.ParseFromString(Message.payload)
                obj = MessageToDict(SCWebFeedPUsh, preserving_proto_field_name=True)

                logger.debug(obj)

                if obj.get("commentFeeds", ""):
                    msg_list = obj.get("commentFeeds", "")
                    for i in msg_list:
                        # Reset the idle count
                        my_global.idle_time_auto_clear(config, "comment")

                        username = i["user"]["userName"]
                        pid = i["user"]["principalId"]
                        content = i["content"]
                        logger.info(f"[📧Live room danmaku message] [{username}]:{content}")

                        data = {
                            "platform": platform,
                            "username": username,
                            "content": content,
                        }

                        my_handle.process_data(data, "comment")
                if obj.get("giftFeeds", ""):
                    my_global.idle_time_auto_clear(config, "gift")

                    msg_list = obj.get("giftFeeds", "")
                    for i in msg_list:
                        username = i["user"]["userName"]
                        # pid = i['user']['principalId']
                        giftId = i["giftId"]
                        comboCount = i["comboCount"]
                        logger.info(
                            f"[🎁Live room gift message] User: {username} gifted gift Id={giftId} combo count={comboCount}"
                        )
                if obj.get("likeFeeds", ""):
                    msg_list = obj.get("likeFeeds", "")
                    for i in msg_list:
                        username = i["user"]["userName"]
                        pid = i["user"]["principalId"]
                        logger.info(f"{username}")

    class run(kslive):
        def __init__(self):
            super().__init__()
            self.ids_list = self.live_ids.split(",")

        def run_live(self):
            """
            Main program entry
            :return:
            """
            t_list = []
            # Maximum number of threads allowed
            if self.thread < 1:
                self.thread = 1
            elif self.thread > 8:
                self.thread = 8
                logger.info("The maximum number of threads allowed is 8; it is best to set the thread count to the number of CPU cores")

            semaphore = threading.Semaphore(self.thread)
            # Used to record the count
            n = 0
            if not self.live_ids:
                logger.info("Please import the web live stream ids, separate multiple with','Interval")
                return

            for i in self.ids_list:
                n += 1
                t = threading.Thread(
                    target=kslive().main, args=(i, semaphore), name=f"Thread: {n}-{i}"
                )
                t.start()
                t_list.append(t)
            for i in t_list:
                i.join()

    run().run_live()