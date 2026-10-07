import requests
import json, threading
import traceback

from utils.my_log import logger

# Integrate with the AUDIO_PLAYER audio player project
class AUDIO_PLAYER:
    def __init__(self, data):
        try:
            self.api_ip_port = data["api_ip_port"]
        except Exception as e:
            logger.error(traceback.format_exc())
            return None

    def play(self, data):
        try:
            url = f"{self.api_ip_port}/play"

            headers = {"Content-Type": "application/json"}
            response = requests.post(url, json=data, headers=headers)

            if response.status_code == 200:
                data_json = response.json()
                # logger.info(data_json)
                if data_json["code"] != 200:
                    logger.error(data_json["message"])
                    return False
                    
                return True
            else:
                logger.error(response.text)
                return False
        except Exception as e:
            logger.error(traceback.format_exc())
            return False

    def pause_stream(self):
        try:
            url = f"{self.api_ip_port}/pause_stream"
            response = requests.get(url)

            if response.status_code == 200:
                data = response.json()
                if data["code"] != 200:
                    logger.error(data["message"])
                    return False
                    
                return True
            else:
                logger.error(response.text)
                return False
        except Exception as e:
            logger.error(traceback.format_exc())
            return False

    def resume_stream(self):
        try:
            url = f"{self.api_ip_port}/resume_stream"
            response = requests.get(url)

            if response.status_code == 200:
                data = response.json()
                if data["code"] != 200:
                    logger.error(data["message"])
                    return False
                    
                return True
            else:
                logger.error(response.text)
                return False
        except Exception as e:
            logger.error(traceback.format_exc())
            return False

    def skip_current_stream(self):
        """
        Skip the currently playing audio
        """
        try:
            url = f"{self.api_ip_port}/skip_current_stream"
            response = requests.get(url)

            if response.status_code == 200:
                data = response.json()
                if data["code"] != 200:
                    logger.error(data["message"])
                    return False
                    
                return True
            else:
                logger.error(response.text)
                return False
        except Exception as e:
            logger.error(traceback.format_exc())
            return False

    def get_list(self):
        """
        Get the audio playback queue list
        """
        try:
            url = f"{self.api_ip_port}/get_list"
            response = requests.get(url)

            if response.status_code == 200:
                data = response.json()
                if data["code"] != 200:
                    logger.error(data["message"])
                    return None
                
                return data["message"]
            else:
                logger.error(response.text)
                return None
        except Exception as e:
            logger.error(traceback.format_exc())
            return None

    def clear(self):
        """
        Clear the playback queue
        """
        try:
            url = f"{self.api_ip_port}/clear"
            response = requests.get(url)

            if response.status_code == 200:
                data = response.json()
                if data["code"] != 200:
                    logger.error(data["message"])
                    return False

                return True
            else:
                logger.error(response.text)
                return False
        except Exception as e:
            logger.error(traceback.format_exc())
            return False
        