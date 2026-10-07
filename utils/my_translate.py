import requests
import random
import json
from hashlib import md5
import traceback
from pygtrans import Translate

from .common import Common
from .my_log import logger
from .config import Config


class My_Translate:
    def __init__(self, config_path):
        self.config = Config(config_path)
        self.common = Common()

        self.config_data = self.config.get("translate")
        self.baidu_config = self.config.get("translate", "baidu")
        self.google_config = self.config.get("translate", "google")


    # Reloadconfig
    def reload_config(self, config_path):
        self.config = Config(config_path)

    def trans(self, text, type=None) -> str:
        """General translation calls this function

        Args:
            text (str): Text to be translated
            type (str): Translation type (baidu/google)

        Returns:
            (str): translated text
        """
        if type is None:
            type = self.config_data["type"]

        # Whether subtitle output is enabled
        if self.config.get("captions", "enable"):
            # Output the text of the audio file currently being played to the subtitle file, that is, save the original text before translation
            self.common.write_content_to_file(self.config.get("captions", "raw_file_path"), text, write_log=False)

        if type == "baidu":
            return self.baidu_trans(text)
        elif type == "google":
            return self.google_trans(text)
        else:
            return self.google_trans(text)
        

    def baidu_trans(self, text):
        """Baidu Translate

        Args:
            text (str): Text to be translated

        Return:
            (str): translated text
        """

        # Set your own appid/appkey.
        appid = self.baidu_config["appid"]
        appkey = self.baidu_config["appkey"]

        # For list of language codes, please refer to `https://api.fanyi.baidu.com/doc/21`
        from_lang = self.baidu_config["from_lang"]
        to_lang =  self.baidu_config["to_lang"]

        endpoint = 'http://api.fanyi.baidu.com'
        path = '/api/trans/vip/translate'
        url = endpoint + path

        # Generate salt and sign
        def make_md5(s, encoding='utf-8'):
            return md5(s.encode(encoding)).hexdigest()

        salt = random.randint(32768, 65536)
        sign = make_md5(appid + text + str(salt) + appkey)

        # Build request
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        payload = {'appid': appid, 'q': text, 'from': from_lang, 'to': to_lang, 'salt': salt, 'sign': sign}

        try:
            # Send request
            r = requests.post(url, params=payload, headers=headers)
            result = r.json()

            logger.info(f"Baidu Translate result={result}")
            translation = result["trans_result"][0]["dst"]
            translation = translation.replace("パパパパ", "パンパカパーン")
            translation = translation.replace("ボンボン", "パンパカパーン")
            translation = translation.replace("RPG", "アールピージー")
            translation = translation.replace("HP", "エイチピー")
            translation = translation.replace("桃ちゃん", "モモイ")
            translation = translation.replace("緑ちゃん", "ミドリ")
            translation = translation.replace("みどりちゃん", "ミドリ")
            translation = translation.replace("ゆずさん", "ユズ")
            translation = translation.replace("優香さん", "ユウカ")
            translation = translation.replace("優香", "ユウカ")
            translation = translation.replace("孥", "ヌ")

            return translation
            # Show response
            # print(json.dumps(result, indent=4, ensure_ascii=False))
        except Exception as e:
            logger.error(traceback.format_exc())

            return None


    def google_trans(self, text):
        """Google Translate

        Args:
            text (str): Text to be translated

        Return:
            (str): translated text
        """
        try:
            if self.config_data['google']['proxy'] != "":
                proxies = {'https': self.config_data['google']['proxy']}
            else:
                proxies = None

            client = Translate(proxies=proxies)

            src_lang = self.config_data['google']['src_lang']
            if src_lang == "auto":
                src_lang = None

            # Translate the sentence
            ret = client.translate(text, target=self.config_data['google']['tgt_lang'], source=src_lang)
            logger.debug(ret)

            return ret.translatedText
        except Exception as e:
            logger.error(traceback.format_exc())

            return None