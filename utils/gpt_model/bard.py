from bardapi import Bard
import requests
import traceback
import threading

from utils.common import Common
from utils.my_log import logger

class Bard_api(Common):
    def __init__(self, data):
        self.common = Common()

        # Initial interval
        self.interval = 30

        """
        Access https://bard.google.com/
        F12 Open developer tools
        Session: Application -> Cookies -> copy the value of __Secure-1PSID in the cookies.
        """
        self.token = data["token"]

        self.session = requests.Session()
        self.session.headers = {
            "Host": "bard.google.com",
            "X-Same-Domain": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "Origin": "https://bard.google.com",
            "Referer": "https://bard.google.com/",
        }
        self.session.cookies.set("__Secure-1PSID", self.token) 

        # Create the initial timer
        self.timer = threading.Timer(self.interval, self.keep_alive)
        self.timer.daemon = True
        self.timer.start()


    # Function that calls a function periodically
    def keep_alive(self):
        return

        # Seems unable to keep alive
        logger.info("Perform bard keep-alive")
        # Send continue to keep the cookie alive
        resp_content = self.get_resp("Continue")
        logger.info(f"{resp_content}")

        # Create a new timer for the next call
        self.timer = threading.Timer(self.interval, self.keep_alive)
        self.timer.daemon = True  # Set the timer as a daemon timer so that it exits automatically when the program exits
        self.timer.start()


    # Call the API and get the returned content
    def get_resp(self, prompt):
        try:
            bard = Bard(token=self.token, session=self.session, timeout=30)
            resp_content = bard.get_answer(prompt)['content'].replace("\\n", "")
            
            # Cancel the current timer and create a new one so that the new interval is used
            self.timer.cancel()
            self.timer = threading.Timer(self.interval, self.keep_alive)
            self.timer.daemon = True
            self.timer.start()

            return resp_content
        except Exception as e:
            logger.error(traceback.format_exc())
            return None
