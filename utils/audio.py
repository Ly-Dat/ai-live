import re
import threading
import asyncio
from copy import deepcopy
import aiohttp
import os, random
import copy
import traceback

from elevenlabs import generate, play, set_api_key

from pydub import AudioSegment

from .common import Common
from .my_log import logger
from .config import Config
from utils.audio_handle.my_tts import MY_TTS
from utils.audio_handle.audio_player import AUDIO_PLAYER


class Audio:
    # Copywriting playback flag 0 manual pause 1 temporary pause 2 loop playback
    copywriting_play_flag = -1

    # pygame.mixerInstance
    mixer_normal = None
    mixer_copywriting = None

    # Global variable to hold the timer object for resuming copywriting playback
    unpause_copywriting_play_timer = None

    audio_player = None

    # Message list, stores the JSON data waiting for audio synthesis
    message_queue = []
    message_queue_lock = threading.Lock()
    message_queue_not_empty = threading.Condition(lock=message_queue_lock)
    # Create the queue of audio paths to play
    voice_tmp_path_queue = []
    voice_tmp_path_queue_lock = threading.Lock()
    voice_tmp_path_queue_not_empty = threading.Condition(lock=voice_tmp_path_queue_lock)
    # # Copywriting is queued for playback in its own separate thread
    # only_play_copywriting_thread = None

    # The first time the voice_tmp_path_queue_not_empty flag is triggered
    voice_tmp_path_queue_not_empty_flag = False

    # Exception alert data
    abnormal_alarm_data = {
        "platform": {
            "error_count": 0
        },
        "llm": {
            "error_count": 0
        },
        "tts": {
            "error_count": 0
        },
        "svc": {
            "error_count": 0
        },
        "visual_body": {
            "error_count": 0
        },
        "other": {
            "error_count": 0
        }
    }

    def __init__(self, config_path, type=1):
        self.config_path = config_path  
        self.config = Config(config_path)
        self.common = Common()
        self.my_tts = MY_TTS(config_path)

        # Copywriting mode
        if type == 2:
            logger.info("Audio initialization for copywriting mode...")
            return
    
        # Copywriting is queued for playback in its own separate thread
        self.only_play_copywriting_thread = None

        if self.config.get("play_audio", "player") in ["pygame"]:
            import pygame

            # Initialize multiple pygame.mixer instances
            Audio.mixer_normal = pygame.mixer
            Audio.mixer_copywriting = pygame.mixer

        # Old synchronous way of writing
        # threading.Thread(target=self.message_queue_thread).start()
        # Change to async
        threading.Thread(target=lambda: asyncio.run(self.message_queue_thread())).start()

        # Audio synthesis is queued for playback in its own separate thread
        threading.Thread(target=lambda: asyncio.run(self.only_play_audio())).start()
        # self.only_play_audio_thread = threading.Thread(target=self.only_play_audio)
        # self.only_play_audio_thread.start()

        # Copywriting is queued for playback in its own separate thread
        if self.only_play_copywriting_thread == None:
            # self.only_play_copywriting_thread = threading.Thread(target=lambda: asyncio.run(self.only_play_copywriting()))
            self.only_play_copywriting_thread = threading.Thread(target=self.start_only_play_copywriting)
            self.only_play_copywriting_thread.start()

        Audio.audio_player =  AUDIO_PLAYER(self.config.get("audio_player"))

        # Virtual body section
        if self.config.get("visual_body") == "live2d-TTS-LLM-GPT-SoVITS-Vtuber":
            pass

    # Clear the waiting-to-synthesize message queue | to-play audio queue
    def clear_queue(self, type: str="message_queue"):
        """Clear the waiting-to-synthesize message queue | to-play audio queue

        Args:
            type (str, optional): Queue type. Defaults to "message_queue".

        Returns:
            bool: Clear the result
        """
        try:
            if type == "voice_tmp_path_queue":
                if len(Audio.voice_tmp_path_queue) == 0:
                    return True
                with self.voice_tmp_path_queue_lock:
                    Audio.voice_tmp_path_queue.clear()
                return True
            elif type == "message_queue":
                if len(Audio.message_queue) == 0:
                    return True
                with self.message_queue_lock:
                    Audio.message_queue.clear()
                return True
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(f"Failed to clear the {type} queue: {e}")
            return False

    # Stop audio playback
    def stop_audio(self, type: str="pygame", mixer_normal: bool=True, mixer_copywriting: bool=True):
        try:
            if type == "pygame":
                if mixer_normal:
                    Audio.mixer_normal.music.stop()
                    logger.info("Stop normal audio playback")
                if mixer_copywriting:
                    Audio.mixer_copywriting.music.stop()
                    logger.info("Stop copywriting audio playback")
                return True
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(f"Failed to stop audio playback: {e}")
            return False
        

    # Check whether the number of the waiting-to-synthesize message queue | to-play audio queue is less or greater than some value, and returnTrue
    def is_queue_less_or_greater_than(self, type: str="message_queue", less: int=None, greater: int=None):
        if less:
            if type == "voice_tmp_path_queue":
                if len(Audio.voice_tmp_path_queue) < less:
                    return True
                return False
            elif type == "message_queue":
                if len(Audio.message_queue) < less:
                    return True
                return False
        
        if greater:
            if type == "voice_tmp_path_queue":
                if len(Audio.voice_tmp_path_queue) > greater:
                    return True
                return False
            elif type == "message_queue":
                if len(Audio.message_queue) > greater:
                    return True
                return False
        
        return False
    
    def get_audio_info(self):
        return {
            "wait_play_audio_num": len(Audio.voice_tmp_path_queue),
            "wait_synthesis_msg_num": len(Audio.message_queue),
        }

    # Check whether the waiting-to-synthesize and already-synthesized queues are empty
    def is_audio_queue_empty(self):
        """Check whether the waiting-to-synthesize and already-synthesized queues are empty

        Returns:
            int: 0 Neither is empty | 1 message_queue is empty | 2 voice_tmp_path_queue is empty | 3 message_queue and voice_tmp_path_queue are empty |
                 4 mixer_normal Not playing | 5 message_queue is empty, mixer_normal not playing | 6 voice_tmp_path_queue is empty, mixer_normal not playing |
                 7 message_queueAnd voice_tmp_path_queue is empty, mixer_normal not playing | 8 mixer_copywriting not playing | 9 message_queue is empty, mixer_copywriting not playing |
                 10 voice_tmp_path_queue Is empty, mixer_copywriting not playing | 11 message_queue and voice_tmp_path_queue are empty, mixer_copywriting not playing |
                 12 message_queue Is empty, voice_tmp_path_queue is empty, mixer_normal not playing | 13 message_queue is empty, voice_tmp_path_queue is empty, mixer_copywriting not playing |
                 14 voice_tmp_path_queueIs empty, mixer_normal not playing, mixer_copywriting not playing | 15 message_queue and voice_tmp_path_queue are empty, mixer_normal not playing, mixer_copywriting not playing |
       
        """

        flag = 0

        # Check whether the queue is empty
        if len(Audio.message_queue) == 0:
            flag += 1
        
        if len(Audio.voice_tmp_path_queue) == 0:
            flag += 2
        
        # TODO: This part only works under pygame playback, but it affects functionality in other player modes, to be optimized
        if self.config.get("play_audio", "player") in ["pygame"]:
            # Check whether mixer_normal is playing
            if not Audio.mixer_normal.music.get_busy():
                flag += 4

            # Check whether mixer_copywriting is playing
            if not Audio.mixer_copywriting.music.get_busy():
                flag += 8

        return flag


    # Reloadconfig
    def reload_config(self, config_path):
        self.config = Config(config_path)
        self.my_tts = MY_TTS(config_path)

    # Search for the specified file in the specified folder and return the found file path
    def search_files(self, root_dir, target_file="", ignore_extension=False):
        matched_files = []

        # If the extension is ignored, take only the base name of the target file
        target_for_comparison = os.path.splitext(target_file)[0] if ignore_extension else target_file

        for root, dirs, files in os.walk(root_dir):
            for file in files:
                # Based on ignore_extension, decide whether to strip the extension before comparing
                file_to_compare = os.path.splitext(file)[0] if ignore_extension else file

                if file_to_compare == target_for_comparison:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, root_dir)
                    relative_path = relative_path.replace("\\", "/")  # Replace backslashes with slashes
                    matched_files.append(relative_path)

        return matched_files


    # Get all audio file names in the local audio folder
    def get_dir_audios_filename(self, audio_path, type=0):
        """Get all audio file names in the local audio folder

        Args:
            audio_path (str): Audio file path
            type (int, Optional): distinguish the return content, 0 returns the full file name, 1 returns the file name without extension. Default is0

        Returns:
            list: File name list
        """
        try:
            # Use os.walk to traverse the folder and its subfolders
            audio_files = []
            for root, dirs, files in os.walk(audio_path):
                for file in files:
                    if file.endswith(('.mp3', '.wav', '.MP3', '.WAV', '.flac', '.aac', '.ogg', '.m4a')):
                        audio_files.append(os.path.join(root, file))

            # Extract the file name or keep the full file name
            if type == 1:
                # Return only the file name without extension
                file_names = [os.path.splitext(os.path.basename(file))[0] for file in audio_files]
            else:
                # Return the full file name
                file_names = [os.path.basename(file) for file in audio_files]
                # Keep the subfolder path
                # file_names = [os.path.relpath(file, audio_path) for file in audio_files]

            logger.debug("The local audio file name list obtained is as follows: ")
            logger.debug(file_names)

            return file_names
        except Exception as e:
            logger.error(traceback.format_exc())
            return None


    # Audio synthesis message queue thread
    async def message_queue_thread(self):
        logger.info("Create the audio synthesis message queue thread")
        while True:  # Infinite loop, exit when the queue is empty
            try:
                # Acquire the thread lock to avoid simultaneous operations
                with Audio.message_queue_lock:
                    while not Audio.message_queue:
                        # After the consumer finishes consuming a message, if the list is empty, it calls wait() to block itself until a new message arrives
                        Audio.message_queue_not_empty.wait()  # Block until the list is non-empty
                    message = Audio.message_queue.pop(0)
                logger.debug(message)

                # The message data here is the data waiting for audio synthesis; it was queued by priority and taken out in this thread, and is about to be synthesized into audio.
                # Some integrated projects have built-in audio playback, so to keep the related mechanism while integrating, source code for this type of integration should be written here
                if self.config.get("visual_body") == "metahuman_stream":
                    logger.debug(f"Raw data before audio synthesis: {message['content']}")
                    # If config parameters were omitted, fill them in proactively to avoid exceptions
                    if "config" not in message:
                        message["config"] = self.config.get("filter")
                    message["content"] = self.common.remove_extra_words(message["content"], message["config"]["max_len"], message["config"]["max_char_len"])
                    # logger.info("Trimmed synthesis text:" + text)

                    message["content"] = message["content"].replace('\n', '。')

                    if message["content"] != "":
                        await self.metahuman_stream_api(message['content'])
                else:
                    # Synthesize audio and insert it into the to-play queue
                    await self.my_play_voice(message)

                # message = Audio.message_queue.get(block=True)
                # logger.debug(message)
                # await self.my_play_voice(message)
                # Audio.message_queue.task_done()

                # Add a delay to reduce load on edge-tts
                # await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(traceback.format_exc())


    # Call so-vits-svc APIapi
    async def so_vits_svc_api(self, audio_path=""):
        try:
            url = f"{self.config.get('so_vits_svc', 'api_ip_port')}/wav2wav"
            
            params = {
                "audio_path": audio_path,
                "tran": self.config.get("so_vits_svc", "tran"),
                "spk": self.config.get("so_vits_svc", "spk"),
                "wav_format": self.config.get("so_vits_svc", "wav_format")
            }

            # logger.info(params)

            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=params) as response:
                    if response.status == 200:
                        file_name = 'so-vits-svc_' + self.common.get_bj_time(4) + '.wav'

                        voice_tmp_path = self.common.get_new_audio_path(self.config.get("play_audio", "out_path"), file_name)
                        
                        with open(voice_tmp_path, 'wb') as file:
                            file.write(await response.read())

                        logger.debug(f"so-vits-svcConversion finished, audio saved at: {voice_tmp_path}")

                        return voice_tmp_path
                    else:
                        logger.error(await response.text())

                        return None
        except Exception as e:
            logger.error(traceback.format_exc())
            return None


    # Call ddsp_svc APIapi
    async def ddsp_svc_api(self, audio_path=""):
        try:
            url = f"{self.config.get('ddsp_svc', 'api_ip_port')}/voiceChangeModel"
                
            # Read the audio file
            with open(audio_path, "rb") as file:
                audio_file = file.read()

            data = aiohttp.FormData()
            data.add_field('sample', audio_file)
            data.add_field('fSafePrefixPadLength', str(self.config.get('ddsp_svc', 'fSafePrefixPadLength')))
            data.add_field('fPitchChange', str(self.config.get('ddsp_svc', 'fPitchChange')))
            data.add_field('sSpeakId', str(self.config.get('ddsp_svc', 'sSpeakId')))
            data.add_field('sampleRate', str(self.config.get('ddsp_svc', 'sampleRate')))

            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as response:
                    # Check the response status
                    if response.status == 200:
                        file_name = 'ddsp-svc_' + self.common.get_bj_time(4) + '.wav'

                        voice_tmp_path = self.common.get_new_audio_path(self.config.get("play_audio", "out_path"), file_name)
                        
                        with open(voice_tmp_path, 'wb') as file:
                            file.write(await response.read())

                        logger.debug(f"ddsp-svcConversion finished, audio saved at: {voice_tmp_path}")

                        return voice_tmp_path
                    else:
                        logger.error(f"Request to ddsp-svc failed, status code: {response.status}")
                        return None

        except Exception as e:
            logger.error(traceback.format_exc())
            return None
        

    # Call xuniren APIapi
    async def xuniren_api(self, audio_path=""):
        try:
            url = f"{self.config.get('xuniren', 'api_ip_port')}/audio_to_video?file_path={os.path.abspath(audio_path)}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    # Check the response status
                    if response.status == 200:
                        logger.info(f"xunirenSynthesis completed")

                        return True
                    else:
                        logger.error(f"xunirenSynthesis failed, status code: {response.status}")
                        return False

        except Exception as e:
            logger.error(traceback.format_exc())
            return False

    # Call EasyAIVtuber APIapi
    async def EasyAIVtuber_api(self, audio_path=""):
        try:
            from urllib.parse import urljoin

            url = urljoin(self.config.get('EasyAIVtuber', 'api_ip_port'), "/alive")
            
            data = {
                "type": "speak",  # Speaking action
                "speech_path": os.path.abspath(audio_path)
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    # Check the response status
                    if response.status == 200:
                        # Use await to wait for the asynchronous JSON response
                        json_response = await response.json()
                        logger.info(f"EasyAIVtuberSent successfully, returned: {json_response['status']}")

                        return True
                    else:
                        logger.error(f"EasyAIVtuberSend failed, status code: {response.status}")
                        return False

        except Exception as e:
            logger.error(traceback.format_exc())
            return False

    # Call metahuman_stream APIapi
    async def metahuman_stream_api(self, message=""):
        try:
            from urllib.parse import urljoin

            url = urljoin(self.config.get('metahuman_stream', 'api_ip_port'), "/human")

            data = {
                "type": 'echo',
                "text": message
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    # Check the response status
                    if response.status == 200:
                        logger.info("metahumanSent successfully")
                        return True
                    else:
                        logger.error(f"metahumanSend failed, status code: {response.status}")
                        return False

        except Exception as e:
            logger.error(traceback.format_exc())
            return False
    
    # Call digital_human_video_player APIapi
    async def digital_human_video_player_api(self, audio_path=""):
        try:
            from urllib.parse import urljoin

            url = urljoin(self.config.get('digital_human_video_player', 'api_ip_port'), "/show")
            
            data = {
                "type": self.config.get('digital_human_video_player', 'type'),
                "audio_path": os.path.abspath(audio_path),
                "video_path": "",
                "insert_index": -1
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    # Check the response status
                    if response.status == 200:
                        # Use await to wait for the asynchronous JSON response
                        json_response = await response.json()
                        logger.info(f"digital_human_video_playerSent successfully, returned: {json_response['message']}")

                        return True
                    else:
                        logger.error(f"digital_human_video_playerSend failed, status code: {response.status}")
                        return False

        except Exception as e:
            logger.error(traceback.format_exc())
            return False

    # Call live2d_TTS_LLM_GPT_SoVITS_Vtuber APIapi
    async def live2d_TTS_LLM_GPT_SoVITS_Vtuber_api(self, audio_path=""):
        try:
            from urllib.parse import urljoin

            url = urljoin(self.config.get('live2d_TTS_LLM_GPT_SoVITS_Vtuber', 'api_ip_port'), "/ws")
            resp_json = self.common.get_filename_from_path(audio_path)
            if resp_json["code"] == 200:
                audio_url = urljoin(f"http://{self.config.get('webui', 'ip')}:{self.config.get('webui', 'port')}", f"/out/{resp_json['data']}")
            else:
                logger.error(f"live2d_TTS_LLM_GPT_SoVITS_VtuberFailed to get audio, returned: {resp_json['error']}")
                return False
            
            data = {
                "action": "talk",
                "data": {
                    "audio_path": audio_url
                }
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    # Check the response status
                    if response.status == 200:
                        # Use await to wait for the asynchronous JSON response
                        json_response = await response.json()
                        logger.info(f"live2d_TTS_LLM_GPT_SoVITS_VtuberSent successfully, returned: {json_response['message']}")

                        return True
                    else:
                        logger.error(f"live2d_TTS_LLM_GPT_SoVITS_VtuberSend failed, status code: {response.status}")
                        return False

        except Exception as e:
            logger.error(traceback.format_exc())
            return False

    # Data is queued by priority and inserted into the audio-to-synthesize queue
    def data_priority_insert(self, type:str="Pending synthesis messages", data_json:dict=None):
        """
        Data is queued by priority and inserted into the audio-to-synthesize queue

        typeCurrently there are
            reread_top_priority Highest priority - repeat
            talk Chat (voice input)
            comment Danmaku
            local_qa_audio Local Q&A audio
            song Song
            reread Repeat
            key_mapping Key mapping
            integral Points
            read_comment Read danmaku
            gift Gift
            entrance User entered
            follow User followed
            schedule Scheduled task
            idle_time_task Idle task
            abnormal_alarm Exception alert
            image_recognition_schedule Image recognition scheduled task
            trends_copywriting Dynamic copywriting
            assistant_anchor_text Assistant-text
            assistant_anchor_audio Assistant-audio
        """
        logger.debug(f"message_queue: {Audio.message_queue}")
        logger.debug(f"data_json: {data_json}")

        # Define the mapping from type to priority; the same priority maps to the same value, larger value means higher priority
        priority_mapping = self.config.get("filter", "priority_mapping")
        
        def get_priority_level(data_json):
            """According to the data_json 'type' Key returns the priority; for an undefined type or missing 'type' Key will return None"""
            # Check whether data_json contains 'type' Key and its value is in priority_mapping
            audio_type = data_json.get("type")
            return priority_mapping.get(audio_type, None)

        # Find the insert position
        new_data_priority = get_priority_level(data_json)

        if type == "Pending synthesis messages":
            logger.info(f"{type} Priority: {new_data_priority} Content: [{data_json['content']}]")

            # If the new data has no 'type' Key or its type is not in priority_mapping, insert directly at the end
            if new_data_priority is None:
                insert_position = len(Audio.message_queue)
            else:
                insert_position = 0  # Insert at the beginning of the list by default
                # Starting from the last element of the list, iterate backward to the first element
                for i in range(len(Audio.message_queue) - 1, -1, -1):
                    priority_level = get_priority_level(Audio.message_queue[i])
                    if priority_level is not None:
                        item_priority = int(priority_level)
                        # Make sure elements of undefined type are excluded from the comparison
                        if item_priority is not None and item_priority >= new_data_priority:
                            # If an element is found whose priority is less than or equal to the new data, insert the new data after this element
                            insert_position = i + 1
                            break
            
            logger.debug(f"insert_position={insert_position}")

            # Check whether the data queue is too long; if the insert position index is greater than the maximum, the priority is lower than the existing data in the queue, so the data is discarded
            if insert_position >= int(self.config.get("filter", "message_queue_max_len")):
                logger.info(f"message_queue Full, data discarded: [{data_json['content']}]")
                return {"code": 1, "msg": f"message_queue is full, data dropped: [{data_json['content']}]"}

            # Acquire the thread lock to avoid simultaneous operations
            with Audio.message_queue_lock:
                # Insert the new data at the computed position
                Audio.message_queue.insert(insert_position, data_json)
                # The producer uses notify() to tell the consumer there is a new message in the list
                Audio.message_queue_not_empty.notify()

            return {"code": 200, "msg": f"Data inserted at position {insert_position}"}
        else:
            logger.info(f"{type} Priority: {new_data_priority} Audio={data_json['voice_path']}")

            # If the new data has no 'type' Key or its type is not in priority_mapping, insert directly at the end
            if new_data_priority is None:
                insert_position = len(Audio.voice_tmp_path_queue)
            else:
                insert_position = 0  # Insert at the beginning of the list by default
                # Starting from the last element of the list, iterate backward to the first element
                for i in range(len(Audio.voice_tmp_path_queue) - 1, -1, -1):
                    priority_level = get_priority_level(Audio.voice_tmp_path_queue[i])
                    if priority_level is not None:
                        item_priority = int(priority_level)
                        # Make sure elements of undefined type are excluded from the comparison
                        if item_priority is not None and item_priority >= new_data_priority:
                            # If an element is found whose priority is less than or equal to the new data, insert the new data after this element
                            insert_position = i + 1
                            break
            
            logger.debug(f"insert_position={insert_position}")

            # Check whether the data queue is too long; if the insert position index is greater than the maximum, the priority is lower than the existing data in the queue, so the data is discarded
            if insert_position >= int(self.config.get("filter", "voice_tmp_path_queue_max_len")):
                logger.info(f"voice_tmp_path_queue Full, audio discarded: [{data_json['voice_path']}]")
                return {"code": 1, "msg": f"voice_tmp_path_queue is full, audio dropped: [{data_json['voice_path']}]"}

            # Acquire the thread lock to avoid simultaneous operations
            with Audio.voice_tmp_path_queue_lock:
                # Insert the new data at the computed position
                Audio.voice_tmp_path_queue.insert(insert_position, data_json)

                # The number of audio clips waiting to play exceeds the first-play threshold and it is the first play: 
                if len(Audio.voice_tmp_path_queue) >= int(self.config.get("filter", "voice_tmp_path_queue_min_start_play")) and \
                    Audio.voice_tmp_path_queue_not_empty_flag is False:
                    Audio.voice_tmp_path_queue_not_empty_flag = True
                    # The producer uses notify() to tell the consumer there is a new message in the list
                    Audio.voice_tmp_path_queue_not_empty.notify()
                # If it is not the first trigger and there is data, trigger the consumer to play
                elif Audio.voice_tmp_path_queue_not_empty_flag:
                    # The producer uses notify() to tell the consumer there is a new message in the list
                    Audio.voice_tmp_path_queue_not_empty.notify()

            return {"code": 200, "msg": f"Audio inserted at position {insert_position}"}

    # Audio synthesis (edge-tts / vits_fast, etc.) and playback
    def audio_synthesis(self, message):
        try:
            logger.debug(message)

            # TTSDo not synthesize audio when the type is none
            if self.config.get("audio_synthesis_type") == "none":
                return

            # Convert digits in the username string to Chinese numerals
            if self.config.get("filter", "username_convert_digits_to_chinese"):
                if message["username"] is not None:
                    message["username"] = self.common.convert_digits_to_chinese(message["username"])

            # Check whether it is song request mode
            if message['type'] == "song":
                # Assemble the JSON data and put it into the queue
                data_json = {
                    "type": message['type'],
                    "tts_type": "none",
                    "voice_path": message['content'],
                    "content": message["content"]
                }

                if "insert_index" in data_json:
                    data_json["insert_index"] = message["insert_index"]

                # Whether audio playback is enabled 
                if self.config.get("play_audio", "enable"):
                    self.data_priority_insert("Pending synthesis messages", data_json)
                return
            # Exception alert
            elif message['type'] == "abnormal_alarm":
                # Assemble the JSON data and put it into the queue
                data_json = {
                    "type": message['type'],
                    "tts_type": "none",
                    "voice_path": message['content'],
                    "content": message["content"]
                }

                if "insert_index" in data_json:
                    data_json["insert_index"] = message["insert_index"]

                # Whether audio playback is enabled 
                if self.config.get("play_audio", "enable"):
                    self.data_priority_insert("Pending synthesis messages", data_json)
                return
            # Whether it is local Q&A audio
            elif message['type'] == "local_qa_audio":
                # Assemble the JSON data and put it into the queue
                data_json = {
                    "type": message['type'],
                    "tts_type": "none",
                    "voice_path": message['file_path'],
                    "content": message["content"]
                }

                if "insert_index" in data_json:
                    data_json["insert_index"] = message["insert_index"]

                # Whether audio playback is enabled
                if self.config.get("play_audio", "enable"):
                    self.data_priority_insert("Pending synthesis messages", data_json)
                return
            # Whether it is assistant-local Q&A audio
            elif message['type'] == "assistant_anchor_audio":
                # Assemble the JSON data and put it into the queue
                data_json = {
                    "type": message['type'],
                    "tts_type": "none",
                    "voice_path": message['file_path'],
                    "content": message["content"]
                }

                if "insert_index" in data_json:
                    data_json["insert_index"] = message["insert_index"]

                # Whether audio playback is enabled
                if self.config.get("play_audio", "enable"):
                    self.data_priority_insert("Pending synthesis messages", data_json)
                return

            # Idle task
            elif message['type'] == "idle_time_task":
                if message['content_type'] in ["comment", "reread"]:
                    pass
                elif message['content_type'] == "local_audio":
                    # Assemble the JSON data and put it into the queue
                    data_json = {
                        "type": message['type'],
                        "tts_type": "none",
                        "voice_path": message['file_path'],
                        "content": message["content"]
                    }

                    if "insert_index" in data_json:
                        data_json["insert_index"] = message["insert_index"]
                    
                    self.data_priority_insert("Pending synthesis messages", data_json)

                    return
            # Key mapping local audio
            elif message['type'] == "key_mapping" and "file_path" in message:
                # Assemble the JSON data and put it into the queue
                data_json = {
                    "type": message['type'],
                    "tts_type": "none",
                    "voice_path": message['file_path'],
                    "content": message["content"]
                }

                if "insert_index" in data_json:
                    data_json["insert_index"] = message["insert_index"]

                # Whether audio playback is enabled
                if self.config.get("play_audio", "enable"):
                    self.data_priority_insert("Pending synthesis messages", data_json)
                return

            # Whether to split sentences
            if self.config.get("play_audio", "text_split_enable"):
                sentences = self.common.split_sentences(message['content'])
                for s in sentences:
                    message_copy = deepcopy(message)  # Create a copy of message
                    message_copy["content"] = s  # Modify the copy of the content
                    logger.debug(f"s={s}")
                    if not self.common.is_all_space_and_punct(s):
                        self.data_priority_insert("Pending synthesis messages", message_copy)  # Put the copy into the queue
            else:
                self.data_priority_insert("Pending synthesis messages", message)
            

            # Play in a separate thread
            # threading.Thread(target=self.my_play_voice, args=(type, data, config, content,)).start()
        except Exception as e:
            logger.error(traceback.format_exc())
            return


    # Audio voice change so-vits-svc + ddsp
    async def voice_change(self, voice_tmp_path):
        """Audio voice change so-vits-svc + ddsp

        Args:
            voice_tmp_path (str): Path of the audio to change voice

        Returns:
            str: Audio path after voice change
        """
        # Convert to an absolute path
        voice_tmp_path = os.path.abspath(voice_tmp_path)

        # Whether to use ddsp-svc for voice change
        if True == self.config.get("ddsp_svc", "enable"):
            voice_tmp_path = await self.ddsp_svc_api(audio_path=voice_tmp_path)
            if voice_tmp_path:
                logger.info(f"ddsp-svcSynthesis succeeded, output to={voice_tmp_path}")
            else:
                logger.error(f"ddsp-svcSynthesis failed, please check the config")
                self.abnormal_alarm_handle("svc")
                return None

        # Convert to an absolute path
        voice_tmp_path = os.path.abspath(voice_tmp_path)

        # Whether to use so-vits-svc for voice change
        if True == self.config.get("so_vits_svc", "enable"):
            voice_tmp_path = await self.so_vits_svc_api(audio_path=voice_tmp_path)
            if voice_tmp_path:
                logger.info(f"so_vits_svcSynthesis succeeded, output to={voice_tmp_path}")
            else:
                logger.error(f"so_vits_svcSynthesis failed, please check the config")
                self.abnormal_alarm_handle("svc")
                
                return None
        
        return voice_tmp_path
    

    # Based on the local config, use TTS to synthesize audio and return the related data
    async def tts_handle(self, message):
        """Based on the local config, use TTS to synthesize audio and return the related data

        Args:
            message (dict): jsonData, including tts config and tts type

            For example: 
            {
                'type': 'reread', 
                'tts_type': 'gpt_sovits', 
                'data': {'type': 'api', 'ws_ip_port': 'ws://localhost:9872/queue/join', 'api_ip_port': 'http://127.0.0.1:9880', 'ref_audio_path': 'F:\\\\GPT-SoVITS\\\\raws\\\\ikaros\\\\21.wav', 'prompt_text': 'Master, are you working hard? No, it is nothing', 'prompt_language': 'Japanese', 'language': 'Auto detect', 'cut': 'Split when reaching four sentences', 'gpt_model_path': 'F:\\GPT-SoVITS\\GPT_weights\\ikaros-e15.ckpt', 'sovits_model_path': 'F:\\GPT-SoVITS\\SoVITS_weights\\ikaros_e8_s280.pth', 'webtts': {'api_ip_port': 'http://127.0.0.1:8080', 'spk': 'sanyueqi', 'lang': 'zh', 'speed': '1.0', 'emotion': 'Normal'}}, 
                'config': {
                    'before_must_str': [], 'after_must_str': [], 'before_filter_str': ['#'], 'after_filter_str': ['#'], 
                    'badwords': {'enable': True, 'discard': False, 'path': 'data/badwords.txt', 'bad_pinyin_path': 'data/Banned pinyin.txt', 'replace': '*'}, 
                    'emoji': False, 'max_len': 80, 'max_char_len': 200, 
                    'comment_forget_duration': 1.0, 'comment_forget_reserve_num': 1, 'gift_forget_duration': 5.0, 'gift_forget_reserve_num': 1, 'entrance_forget_duration': 5.0, 'entrance_forget_reserve_num': 2, 'follow_forget_duration': 3.0, 'follow_forget_reserve_num': 1, 'talk_forget_duration': 0.1, 'talk_forget_reserve_num': 1, 'schedule_forget_duration': 0.1, 'schedule_forget_reserve_num': 1, 'idle_time_task_forget_duration': 0.1, 'idle_time_task_forget_reserve_num': 1, 'image_recognition_schedule_forget_duration': 0.1, 'image_recognition_schedule_forget_reserve_num': 1}, 
                'username': 'Master', 
                'content': 'Hello'
            }

        Returns:
            dict: jsonData, including tts config, tts type, synthesis result and other info
        """

        try:
            if message["tts_type"] == "vits":
                # Language detection
                language = self.common.lang_check(message["content"])

                logger.debug(f"message['content']={message['content']}")

                # Custom language name (must match the request parsing)
                language_name_dict = {"en": "English", "zh": "Chinese", "ja": "Japanese", "jp": "Japanese"}  

                if language in language_name_dict:
                    language = language_name_dict[language]
                else:
                    language = "Auto"  # default when the language code cannot be recognized

                # logger.info("language=" + language)

                data = {
                    "type": message["data"]["type"],
                    "api_ip_port": message["data"]["api_ip_port"],
                    "id": message["data"]["id"],
                    "format": message["data"]["format"],
                    "lang": language,
                    "length": message["data"]["length"],
                    "noise": message["data"]["noise"],
                    "noisew": message["data"]["noisew"],
                    "max": message["data"]["max"],
                    "sdp_radio": message["data"]["sdp_radio"],
                    "content": message["content"],
                    "gpt_sovits": message["data"]["gpt_sovits"],
                }

                # Call the API to synthesize speech
                voice_tmp_path = await self.my_tts.vits_api(data)
            
            elif message["tts_type"] == "bert_vits2":
                if message["data"]["language"] == "auto":
                    # Auto-detect language
                    language = self.common.lang_check(message["content"])

                    logger.debug(f'language={language}')

                    # Custom language name (must match the request parsing)
                    language_name_dict = {"en": "EN", "zh": "ZH", "ja": "JP"}  

                    if language in language_name_dict:
                        language = language_name_dict[language]
                    else:
                        language = "ZH"  # Default value when the language code cannot be identified
                else:
                    language = message["data"]["language"]

                data = {
                    "api_ip_port": message["data"]["api_ip_port"],
                    "type": message["data"]["type"],
                    "model_id": message["data"]["model_id"],
                    "speaker_name": message["data"]["speaker_name"],
                    "speaker_id": message["data"]["speaker_id"],
                    "language": language,
                    "length": message["data"]["length"],
                    "noise": message["data"]["noise"],
                    "noisew": message["data"]["noisew"],
                    "sdp_radio": message["data"]["sdp_radio"],
                    "auto_translate": message["data"]["auto_translate"],
                    "auto_split": message["data"]["auto_split"],
                    "emotion": message["data"]["emotion"],
                    "style_text": message["data"]["style_text"],
                    "style_weight": message["data"]["style_weight"],
                    "刘悦-中文特化API": message["data"]["刘悦-中文特化API"],
                    "content": message["content"]
                }


                # Call the API to synthesize speech
                voice_tmp_path = await self.my_tts.bert_vits2_api(data)
            
            elif message["tts_type"] == "vits_fast":
                if message["data"]["language"] == "Auto detect":
                    # Auto-detect language
                    language = self.common.lang_check(message["content"])

                    logger.debug(f'language={language}')

                    # Custom language name (must match the request parsing)
                    language_name_dict = {"en": "English", "zh": "简体中文", "ja": "日本語"}  

                    if language in language_name_dict:
                        language = language_name_dict[language]
                    else:
                        language = "简体中文"  # Default value when the language code cannot be identified
                else:
                    language = message["data"]["language"]

                # logger.info("language=" + language)

                data = {
                    "api_ip_port": message["data"]["api_ip_port"],
                    "character": message["data"]["character"],
                    "speed": message["data"]["speed"],
                    "language": language,
                    "content": message["content"]
                }

                # Call the API to synthesize speech
                voice_tmp_path = self.my_tts.vits_fast_api(data)
                # logger.info(data_json)
            elif message["tts_type"] == "edge-tts":
                data = {
                    "content": message["content"],
                    "edge-tts": message["data"]
                }

                # Call the API to synthesize speech
                voice_tmp_path = await self.my_tts.edge_tts_api(data)
            elif message["tts_type"] == "vieneu":
                data = {
                    "content": message["content"],
                    "vieneu": message["data"],
                    "edge-tts": self.config.get("edge-tts")
                }

                # Free local VieNeu-TTS; falls back to edge-tts if its server is down
                voice_tmp_path = await self.my_tts.vieneu_tts_api(data)
            elif message["tts_type"] == "elevenlabs":
                # If a key is configured, set it0.0
                if message["data"]["api_key"] != "":
                    set_api_key(message["data"]["api_key"])

                audio = generate(
                    text=message["content"],
                    voice=message["data"]["voice"],
                    model=message["data"]["model"]
                )

                play(audio)
                logger.info(f"elevenlabsSynthesis content: [{message['content']}]")

                return
            
            elif message["tts_type"] == "openai_tts":
                data = {
                    "type": message["data"]["type"],
                    "api_ip_port": message["data"]["api_ip_port"],
                    "model": message["data"]["model"],
                    "voice": message["data"]["voice"],
                    "api_key": message["data"]["api_key"],
                    "content": message["content"]
                }

                # Call the API to synthesize speech
                voice_tmp_path = self.my_tts.openai_tts_api(data)
            
            elif message["tts_type"] == "gradio_tts":
                data = {
                    "request_parameters": message["data"]["request_parameters"],
                    "content": message["content"]
                }

                voice_tmp_path = self.my_tts.gradio_tts_api(data)  
            elif message["tts_type"] == "gpt_sovits":
                if message["data"]["language"] == "Auto detect":
                    # Auto-detect language
                    language = self.common.lang_check(message["content"])

                    logger.debug(f'language={language}')

                    # Custom language name (must match the request parsing)
                    language_name_dict = {"en": "英文", "zh": "中文", "ja": "日文"}  

                    if language in language_name_dict:
                        language = language_name_dict[language]
                    else:
                        language = "中文"  # Default value when the language code cannot be identified
                else:
                    language = message["data"]["language"]

                if message["data"]["api_0322"]["text_lang"] == "Auto detect":
                    # Auto-detect language
                    language = self.common.lang_check(message["content"])

                    logger.debug(f'language={language}')

                    # Custom language name (must match the request parsing)
                    language_name_dict = {"en": "英文", "zh": "中文", "ja": "日文"}  

                    if language in language_name_dict:
                        message["data"]["api_0322"]["text_lang"] = language_name_dict[language]
                    else:
                        message["data"]["api_0322"]["text_lang"] = "中文"  # Default value when the language code cannot be identified

                if message["data"]["api_0706"]["text_language"] == "Auto detect":
                    message["data"]["api_0706"]["text_language"] = "auto"

                data = {
                    "type": message["data"]["type"],
                    "gradio_ip_port": message["data"]["gradio_ip_port"],
                    "api_ip_port": message["data"]["api_ip_port"],
                    "ref_audio_path": message["data"]["ref_audio_path"],
                    "prompt_text": message["data"]["prompt_text"],
                    "prompt_language": message["data"]["prompt_language"],
                    "language": language,
                    "cut": message["data"]["cut"],
                    "api_0322": message["data"]["api_0322"],
                    "api_0706": message["data"]["api_0706"],
                    "v2_api_0821": message["data"]["v2_api_0821"],
                    "webtts": message["data"]["webtts"],
                    "content": message["content"]
                }

                voice_tmp_path = await self.my_tts.gpt_sovits_api(data)  
            
            elif message["tts_type"] == "azure_tts":
                data = {
                    "subscription_key": message["data"]["subscription_key"],
                    "region": message["data"]["region"],
                    "voice_name": message["data"]["voice_name"],
                    "content": message["content"]
                }

                voice_tmp_path = self.my_tts.azure_tts_api(data) 
            
            elif message["tts_type"] == "cosyvoice":
                logger.debug(message)
                data = {
                    "type": message["data"]["type"],
                    "gradio_ip_port": message["data"]["gradio_ip_port"],
                    "api_ip_port": message["data"]["api_ip_port"],
                    "gradio_0707": message["data"]["gradio_0707"],
                    "api_0819": message["data"]["api_0819"],
                    "content": message["content"],
                }

                voice_tmp_path = await self.my_tts.cosyvoice_api(data)  
            elif message["tts_type"] == "f5_tts":
                logger.debug(message)
                data = {
                    "type": message["data"]["type"],
                    "gradio_ip_port": message["data"]["gradio_ip_port"],
                    "ref_audio_orig": message["data"]["ref_audio_orig"],
                    "ref_text": message["data"]["ref_text"],
                    "model": message["data"]["model"],
                    "remove_silence": message["data"]["remove_silence"],
                    "cross_fade_duration": message["data"]["cross_fade_duration"],
                    "speed": message["data"]["speed"],
                    "content": message["content"],
                }

                voice_tmp_path = await self.my_tts.f5_tts_api(data)  
            elif message["tts_type"] == "multitts":
                data = {
                    "content": message["content"],
                    "multitts": message["data"]
                }

                voice_tmp_path = await self.my_tts.multitts_api(data)  
            elif message["tts_type"] == "melotts":
                data = {
                    "content": message["content"],
                    "melotts": message["data"]
                }

                voice_tmp_path = await self.my_tts.melotts_api(data)  
            elif message["tts_type"] == "index_tts":
                data = {
                    "content": message["content"],
                    "index_tts": message["data"],
                }

                voice_tmp_path = await self.my_tts.index_tts_api(data)
            elif message["tts_type"] == "none":
                # Audio.voice_tmp_path_queue.put(message)
                voice_tmp_path = None

            message["result"] = {
                "code": 200,
                "msg": "Synthesis succeeded",
                "audio_path": voice_tmp_path
            }
        except Exception as e:
            logger.error(traceback.format_exc())
            message["result"] = {
                "code": -1,
                "msg": f"Synthesis failed, {e}",
                "audio_path": None
            }

        return message

    # Send audio playback info to the HTTP server inside main
    async def send_audio_play_info_to_callback(self, data: dict=None):
        """Send audio playback info to the HTTP server inside main

        Args:
            data (dict): Audio playback info
        """
        try:
            if False == self.config.get("play_audio", "info_to_callback"):
                return None

            if data is None:
                data = {
                    "type": "audio_playback_completed",
                    "data": {
                        # Number of audio clips waiting to play
                        "wait_play_audio_num": len(Audio.voice_tmp_path_queue),
                        # Number of messages waiting for audio synthesis
                        "wait_synthesis_msg_num": len(Audio.message_queue),
                    }
                }

            logger.debug(f"data={data}")

            main_api_ip = "127.0.0.1" if self.config.get("api_ip") == "0.0.0.0" else self.config.get("api_ip")
            resp = await self.common.send_async_request(f'http://{main_api_ip}:{self.config.get("api_port")}/callback', "POST", data)

            return resp
        except Exception as e:
            logger.error(traceback.format_exc())
            return None


    # Synthesize audio and insert it into the to-play queue
    def _notify_overlay(self, text, path):
        """Tell the product_tour overlay (:8091) that this voice clip is starting NOW."""
        def run():
            import json as _json, urllib.request as _ur
            try:
                try:
                    dur = Audio.mixer_normal.Sound(path).get_length()
                except Exception:
                    dur = len(text) / 13.0
                _ur.urlopen(_ur.Request("http://127.0.0.1:8091/speak",
                            data=_json.dumps({"content": text, "duration": dur}).encode("utf-8"),
                            headers={"Content-Type": "application/json"}, method="POST"), timeout=1)
            except Exception:
                pass
        threading.Thread(target=run, daemon=True).start()

    async def my_play_voice(self, message):
        """Synthesize audio and insert it into the to-play queue

        Args:
            message (dict): JSON string of the content to synthesize

        Returns:
            bool: Synthesis status
        """
        logger.debug(message)

        try:
            # If the tts type is none, which for now means playing audio directly, pass it to the path queue
            if message["tts_type"] == "none":
                self.data_priority_insert("Pending audio list", message)
                return
        except Exception as e:
            logger.error(traceback.format_exc())
            return

        try:
            logger.debug(f"Raw data before audio synthesis: {message['content']}")
            message["content"] = self.common.remove_extra_words(message["content"], message["config"]["max_len"], message["config"]["max_char_len"])
            # logger.info("Trimmed synthesis text:" + text)

            message["content"] = message["content"].replace('\n', '。')

            # Empty data, nothing to do
            if message["content"] == "":
                return
        except Exception as e:
            logger.error(traceback.format_exc())
            return
        

        # Check the message type, then change voice and wrap the data into the queue, reducing redundancy
        async def voice_change_and_put_to_queue(message, voice_tmp_path):
            # Assemble the JSON data and put it into the queue
            data_json = {
                "type": message['type'],
                "voice_path": voice_tmp_path,
                "content": message["content"]
            }

            if "insert_index" in message:
                data_json["insert_index"] = message["insert_index"]

            # Distinguish whether the message type is reply xxx and voice change is off
            if message["type"] == "reply":
                # Whether audio playback is enabled; if not, no file path is passed to the playback queue
                if self.config.get("play_audio", "enable"):
                    self.data_priority_insert("Pending audio list", data_json)
                    return True
            # Distinguish whether the message type is read danmaku and voice change is off
            elif message["type"] == "read_comment" and not self.config.get("read_comment", "voice_change"):
                # Whether audio playback is enabled; if not, no file path is passed to the playback queue
                if self.config.get("play_audio", "enable"):
                    self.data_priority_insert("Pending audio list", data_json)
                    return True

            voice_tmp_path = await self.voice_change(voice_tmp_path)
            
            # Update the audio path
            data_json["voice_path"] = voice_tmp_path

            # Whether audio playback is enabled; if not, no file path is passed to the playback queue
            if self.config.get("play_audio", "enable"):
                self.data_priority_insert("Pending audio list", data_json)

            return True


        resp_json = await self.tts_handle(message)
        if resp_json["result"]["code"] == 200:
            voice_tmp_path = resp_json["result"]["audio_path"]
        else:
            voice_tmp_path = None
        
        if voice_tmp_path is None:
            logger.error(f"{message['tts_type']}Synthesis failed, please check whether the server is started and working, and check config, network and other issues. If everything checks out, it may be a compatibility problem caused by an API change; you can submit an issue to the official repository, link: https://github.com/Ikaros-521/AI-Vtuber/issues\nIf it is a GSV 400 error, please confirm the reference audio and reference text are correct, or try replacing the reference audio")
            self.abnormal_alarm_handle("tts")
            
            return False
        
        logger.info(f"[{message['tts_type']}]Synthesis succeeded, content: [{message['content']}], audio stored in {voice_tmp_path}")
                 
        await voice_change_and_put_to_queue(message, voice_tmp_path)  

        return True

    # Audio speed change
    def audio_speed_change(self, audio_path, speed_factor=1.0, pitch_factor=1.0):
        """Audio speed change

        Args:
            audio_path (str): Audio path
            speed (int, optional): Partial speed ratio. Default 1.
            type (int, optional): Pitch shift ratio, 1 means no change. Default 1.

        Returns:
            str: Audio path after speed change
        """
        logger.debug(f"audio_path={audio_path}, speed_factor={speed_factor}, pitch_factor={pitch_factor}")

        # Open the audio file with pydub
        audio = AudioSegment.from_file(audio_path)

        # Speed change
        if speed_factor > 1.0:
            audio_changed = audio.speedup(playback_speed=speed_factor)
        elif speed_factor < 1.0:
            # To slow down, use set_frame_rate to adjust the frame rate
            orig_frame_rate = audio.frame_rate
            slow_frame_rate = int(orig_frame_rate * speed_factor)
            audio_changed = audio._spawn(audio.raw_data, overrides={"frame_rate": slow_frame_rate})
        else:
            audio_changed = audio

        # Pitch shift
        if pitch_factor != 1.0:
            semitones = 12 * (pitch_factor - 1)
            audio_changed = audio_changed._spawn(audio_changed.raw_data, overrides={
                "frame_rate": int(audio_changed.frame_rate * (2.0 ** (semitones / 12.0)))
            }).set_frame_rate(audio_changed.frame_rate)

        # Speed change
        # audio_changed = audio.speedup(playback_speed=speed_factor)

        # # Pitch shift
        # if pitch_factor != 1.0:
        #     semitones = 12 * (pitch_factor - 1)
        #     audio_changed = audio_changed._spawn(audio_changed.raw_data, overrides={
        #         "frame_rate": int(audio_changed.frame_rate * (2.0 ** (semitones / 12.0)))
        #     }).set_frame_rate(audio_changed.frame_rate)

        # Export to a temporary file
        audio_out_path = self.config.get("play_audio", "out_path")
        if not os.path.isabs(audio_out_path):
            if not audio_out_path.startswith('./'):
                audio_out_path = './' + audio_out_path
        file_name = f"temp_{self.common.get_bj_time(4)}.wav"
        temp_path = self.common.get_new_audio_path(audio_out_path, file_name)

        # Export as a new audio file
        audio_changed.export(temp_path, format="wav")

        # Convert to an absolute path
        temp_path = os.path.abspath(temp_path)

        return temp_path


    # Only play normal audio   
    async def only_play_audio(self):
        try:
            captions_config = self.config.get("captions")

            try:
                if self.config.get("play_audio", "player") in ["pygame"]:
                    Audio.mixer_normal.init()
            except Exception as e:
                logger.error(traceback.format_exc())
                logger.error("pygame mixer_normalInitialization failed, normal audio will not play properly, please check that the sound card is working!")

            while True:
                try:
                    # Acquire the thread lock to avoid simultaneous operations
                    with Audio.voice_tmp_path_queue_lock:
                        while not Audio.voice_tmp_path_queue:
                            # After the consumer finishes consuming a message, if the list is empty, it calls wait() to block itself until a new message arrives
                            Audio.voice_tmp_path_queue_not_empty.wait()  # Block until the list is non-empty
                        data_json = Audio.voice_tmp_path_queue.pop(0)
                    
                    logger.debug(f"Normal audio playback queue, about to play audio data_json={data_json}")

                    voice_tmp_path = data_json["voice_path"]

                    # If the copywriting flag is 2, it is playing and needs to be paused
                    if Audio.copywriting_play_flag == 2:
                        logger.debug("Pause copywriting playback, wait one switch interval")
                        # Copywriting paused
                        self.pause_copywriting_play()
                        Audio.copywriting_play_flag = 1
                        # Wait for one switch interval
                        await asyncio.sleep(float(self.config.get("copywriting", "switching_interval")))
                        logger.debug(f"Switch interval ended, preparing to play normal audio")

                    # Whether subtitle output is enabled
                    if captions_config["enable"]:
                        # Output the text content of the currently playing audio file to the subtitle file
                        self.common.write_content_to_file(captions_config["file_path"], data_json["content"], write_log=False)


                    # Check whether to send to the web subtitle printer
                    if self.config.get("web_captions_printer", "enable"):
                        await self.common.send_to_web_captions_printer(self.config.get("web_captions_printer", "api_ip_port"), data_json)

                    # Luoxi Live Danmaku Assistant
                    if self.config.get("luoxi_project", "Live_Comment_Assistant", "enable") and \
                        "On audio playback" in self.config.get("luoxi_project", "Live_Comment_Assistant", "trigger_position"):
                        from utils.luoxi_project.live_comment_assistant import send_msg_to_live_comment_assistant

                        # Convert the audio message type to the new type used for judgmenttype
                        type_mapping = {
                            "comment": "comment_reply",
                            "idle_time_task": "idle_time_task",
                            "entrance": "entrance_reply",
                            "follow": "follow_reply",
                            "gift": "gift_reply",
                            "reread": "reread",
                            "schedule": "schedule",
                        }  

                        if data_json["type"] in type_mapping:
                            tmp_type = type_mapping[data_json["type"]]
                            # The current message type is an enabled trigger type
                            if tmp_type in self.config.get("luoxi_project", "Live_Comment_Assistant", "type"):
                                await send_msg_to_live_comment_assistant(self.config.get("luoxi_project", "Live_Comment_Assistant"), data_json["content"])


                    normal_interval_min = self.config.get("play_audio", "normal_interval_min")
                    normal_interval_max = self.config.get("play_audio", "normal_interval_max")
                    normal_interval = self.common.get_random_value(normal_interval_min, normal_interval_max)

                    interval_num_min = float(self.config.get("play_audio", "interval_num_min"))
                    interval_num_max = float(self.config.get("play_audio", "interval_num_max"))
                    interval_num = int(self.common.get_random_value(interval_num_min, interval_num_max))

                    for i in range(interval_num):
                        # It is not only the speaking interval, but also waiting for text capture to refresh data
                        await asyncio.sleep(normal_interval)

                    # Audio speed change
                    random_speed = 1
                    if self.config.get("audio_random_speed", "normal", "enable"):
                        random_speed = self.common.get_random_value(self.config.get("audio_random_speed", "normal", "speed_min"),
                                                                    self.config.get("audio_random_speed", "normal", "speed_max"))
                        voice_tmp_path = self.audio_speed_change(voice_tmp_path, random_speed)

                    # print(voice_tmp_path)

                    # Execute different logic depending on the connected virtual body type
                    if self.config.get("visual_body") == "xuniren":
                        await self.xuniren_api(voice_tmp_path)
                    elif self.config.get("visual_body") == "EasyAIVtuber":
                        await self.EasyAIVtuber_api(voice_tmp_path)
                    elif self.config.get("visual_body") == "digital_human_video_player":
                        await self.digital_human_video_player_api(voice_tmp_path)
                    elif self.config.get("visual_body") == "live2d_TTS_LLM_GPT_SoVITS_Vtuber":
                        await self.live2d_TTS_LLM_GPT_SoVITS_Vtuber_api(voice_tmp_path)
                    else:
                        # Distinguish by player type
                        if self.config.get("play_audio", "player") in ["audio_player", "audio_player_v2"]:
                            if "insert_index" in data_json:
                                data_json = {
                                    "type": data_json["type"],
                                    "voice_path": voice_tmp_path,
                                    "content": data_json["content"],
                                    "random_speed": {
                                        "enable": False,
                                        "max": 1.3,
                                        "min": 0.8
                                    },
                                    "speed": 1,
                                    "insert_index": data_json["insert_index"]
                                }
                            else:
                                data_json = {
                                    "type": data_json["type"],
                                    "voice_path": voice_tmp_path,
                                    "content": data_json["content"],
                                    "random_speed": {
                                        "enable": False,
                                        "max": 1.3,
                                        "min": 0.8
                                    },
                                    "speed": 1
                                }
                            Audio.audio_player.play(data_json)
                        else:
                            logger.debug(f"voice_tmp_path={voice_tmp_path}")
                            import pygame

                            try:
                                # Play audio with pygame
                                Audio.mixer_normal.music.load(voice_tmp_path)
                                self._notify_overlay(data_json.get("content", ""), voice_tmp_path)
                                Audio.mixer_normal.music.play()
                                while Audio.mixer_normal.music.get_busy():
                                    pygame.time.Clock().tick(10)
                                Audio.mixer_normal.music.stop()
                                
                                await self.send_audio_play_info_to_callback()
                            except pygame.error as e:
                                logger.error(traceback.format_exc())
                                # If a pygame.error exception occurs, catch and handle it
                                logger.error(f"Unable to load the audio file: {voice_tmp_path}. Please make sure the file format is correct and the file is not corrupted. Possible causes are a wrong TTS config or a problem with the TTS server; check the server side")

                    # Whether subtitle output is enabled
                    #if captions_config["enable"]:
                        # Clear the subtitle file
                        # self.common.write_content_to_file(captions_config["file_path"], "")

                    if Audio.copywriting_play_flag == 1:
                        # Delay before resuming copywriting playback
                        self.delayed_execution_unpause_copywriting_play()
                except Exception as e:
                    logger.error(traceback.format_exc())
            Audio.mixer_normal.quit()
        except Exception as e:
            logger.error(traceback.format_exc())


    # Stop the currently playing audio
    def stop_current_audio(self):
        if self.config.get("play_audio", "player") == "audio_player":
            Audio.audio_player.skip_current_stream()
        else:
            Audio.mixer_normal.music.fadeout(1000)

    """
                                                     ./@\]                    
                   ,@@@@\*                             \@@^ ,]]]              
                      [[[*                      /@@]@@@@@/[[\@@@@/            
                        ]]@@@@@@\              /@@^  @@@^]]`[[                
                ]]@@@@@@@[[*                   ,[`  /@@\@@@@@@@@@@@@@@^       
             [[[[[`   @@@/                 \@@@@[[[\@@^ =@@/                  
              .\@@\* *@@@`                           [\@@@@@@\`               
                 ,@@\=@@@                         ,]@@@/`  ,\@@@@*            
                   ,@@@@`                     ,[[[[`  =@@@   ]]/O             
                   /@@@@@`                    ]]]@@@@@@@@@/[[[[[`             
                ,@@@@[ \@@@\`                      ./@@@@@@@]                 
          ,]/@@@@/`      \@@@@@\]]               ,@@@/,@@^ \@@@\]             
                           ,@@@@@@@@/[*       ,/@@/*  /@@^   [@@@@@@@\*       
                                                      ,@@^                    
                                                              
    """
    # Delay before resuming copywriting playback
    def delayed_execution_unpause_copywriting_play(self):
        # If a timer is already running, cancel the previous timer
        if Audio.unpause_copywriting_play_timer is not None and Audio.unpause_copywriting_play_timer.is_alive():
            Audio.unpause_copywriting_play_timer.cancel()

        # Create a new timer and start it
        Audio.unpause_copywriting_play_timer = threading.Timer(float(self.config.get("copywriting", "switching_interval")), 
                                                               self.unpause_copywriting_play)
        Audio.unpause_copywriting_play_timer.start()


    # Only play copywriting, proper version
    def start_only_play_copywriting(self):
        logger.info(f"Copywriting playback thread is running...")
        asyncio.run(self.only_play_copywriting())


    # Only play copywriting   
    async def only_play_copywriting(self):
        
        try:
            try:
                if self.config.get("play_audio", "player") in ["pygame"]:
                    Audio.mixer_copywriting.init()
            except Exception as e:
                logger.error(traceback.format_exc())
                logger.error("pygame mixer_copywritingInitialization failed, copywriting audio will not play properly, please check that the sound card is working!")

            async def random_speed_and_play(audio_path):
                """Change the speed of the audio and play it, with built-in delay; this is just the extracted common part

                Args:
                    audio_path (str): Audio path
                """
                # Audio speed change
                random_speed = 1
                if self.config.get("audio_random_speed", "copywriting", "enable"):
                    random_speed = self.common.get_random_value(self.config.get("audio_random_speed", "copywriting", "speed_min"),
                                                                self.config.get("audio_random_speed", "copywriting", "speed_max"))
                    audio_path = self.audio_speed_change(audio_path, random_speed)

                logger.info(f"Audio after speed change output to {audio_path}")

                # Execute different logic depending on the connected virtual body type
                if self.config.get("visual_body") == "xuniren":
                    await self.xuniren_api(audio_path)
                else:
                    if self.config.get("play_audio", "player") in ["audio_player", "audio_player_v2"]:
                            data_json = {
                                "type": "copywriting",
                                "voice_path": audio_path,
                                "content": audio_path,
                                "random_speed": {
                                    "enable": False,
                                    "max": 1.3,
                                    "min": 0.8
                                },
                                "speed": 1
                            }
                            Audio.audio_player.play(data_json)
                    else:
                        import pygame

                        try:
                            # Play audio with pygame
                            Audio.mixer_copywriting.music.load(audio_path)
                            Audio.mixer_copywriting.music.play()
                            while Audio.mixer_copywriting.music.get_busy():
                                pygame.time.Clock().tick(10)
                            Audio.mixer_copywriting.music.stop()

                            await self.send_audio_play_info_to_callback()
                        except pygame.error as e:
                            logger.error(traceback.format_exc())
                            # If a pygame.error exception occurs, catch and handle it
                            logger.error(f"Unable to load the audio file: {voice_tmp_path}. Please make sure the file format is correct and the file is not corrupted. Possible causes are a wrong TTS config or a problem with the TTS server; check the server side")


                # Add a delay, pause execution for n seconds
                await asyncio.sleep(float(self.config.get("copywriting", "audio_interval")))


            def reload_tmp_play_list(index, play_list_arr):
                """Reload the playlist

                Args:
                    index (int): Copywriting index
                """
                # Get the copywriting config
                copywriting_configs = self.config.get("copywriting", "config")
                tmp_play_list = copy.copy(copywriting_configs[index]["play_list"])
                play_list_arr[index] = tmp_play_list

                # Whether random list playback is enabled
                if self.config.get("copywriting", "random_play"):
                    for play_list in play_list_arr:
                        # Randomly shuffle the list contents
                        random.shuffle(play_list)


            try:
                # Get the copywriting config
                copywriting_configs = self.config.get("copywriting", "config")

                # Get the auto-play config
                if self.config.get("copywriting", "auto_play"):
                    self.unpause_copywriting_play()

                file_path_arr = []
                audio_path_arr = []
                play_list_arr = []
                continuous_play_num_arr = []
                max_play_time_arr = []
                # Record the index of the last played audio list
                last_index = -1

                # Reload all data
                def all_data_reload(file_path_arr, audio_path_arr, play_list_arr, continuous_play_num_arr, max_play_time_arr):      
                    logger.info("Reload all copywriting data")

                    file_path_arr = []
                    audio_path_arr = []
                    play_list_arr = []
                    continuous_play_num_arr = []
                    max_play_time_arr = []
                    
                    # Iterate over the copywriting config and load it into the array
                    for copywriting_config in copywriting_configs:
                        file_path_arr.append(copywriting_config["file_path"])
                        audio_path_arr.append(copywriting_config["audio_path"])
                        tmp_play_list = copy.copy(copywriting_config["play_list"])
                        play_list_arr.append(tmp_play_list)
                        continuous_play_num_arr.append(copywriting_config["continuous_play_num"])
                        max_play_time_arr.append(copywriting_config["max_play_time"])


                    # Whether random list playback is enabled
                    if self.config.get("copywriting", "random_play"):
                        for play_list in play_list_arr:
                            # Randomly shuffle the list contents
                            random.shuffle(play_list)

                    return file_path_arr, audio_path_arr, play_list_arr, continuous_play_num_arr, max_play_time_arr

                file_path_arr, audio_path_arr, play_list_arr, continuous_play_num_arr, max_play_time_arr = all_data_reload(file_path_arr, audio_path_arr, play_list_arr, continuous_play_num_arr, max_play_time_arr)

                while True:
                    # print(f"Audio.copywriting_play_flag={Audio.copywriting_play_flag}")

                    # Check the playback flag
                    if Audio.copywriting_play_flag in [0, 1, -1]:
                        await asyncio.sleep(float(self.config.get("copywriting", "audio_interval")))  # Add a delay to reduce the loop frequency
                        continue

                    # print(f"play_list_arr={play_list_arr}")

                    # Iterate over each item in play_list_arr play_list
                    for index, play_list in enumerate(play_list_arr):
                        # print(f"play_list_arr={play_list_arr}")

                        # Check the playback flag to prevent being unable to pause during playback
                        if Audio.copywriting_play_flag in [0, 1, -1]:
                            # print(f"Audio.copywriting_play_flag={Audio.copywriting_play_flag}")
                            file_path_arr, audio_path_arr, play_list_arr, continuous_play_num_arr, max_play_time_arr = all_data_reload(file_path_arr, audio_path_arr, play_list_arr, continuous_play_num_arr, max_play_time_arr)

                            break

                        # Check whether the current playlist index is less than the last index; if so, go to the next one, to resume the playback position from before the interruption
                        if index < last_index:
                            continue

                        start_time = float(self.common.get_bj_time(3))

                        # Loop according to the number of consecutively played copywritings
                        for i in range(0, continuous_play_num_arr[index]):
                            # print(f"continuous_play_num_arr[index]={continuous_play_num_arr[index]}")
                            # Check the playback flag to prevent being unable to pause during playback
                            if Audio.copywriting_play_flag in [0, 1, -1]:
                                file_path_arr, audio_path_arr, play_list_arr, continuous_play_num_arr, max_play_time_arr = all_data_reload(file_path_arr, audio_path_arr, play_list_arr, continuous_play_num_arr, max_play_time_arr)

                                break
                            
                            # Check whether the current time has exceeded the allowed playback time, and exit the loop if timed out
                            if (float(self.common.get_bj_time(3)) - start_time) > max_play_time_arr[index]:
                                break

                            # Check whether the current play_list has audio data
                            if len(play_list) > 0:
                                # Remove one audio path
                                voice_tmp_path = play_list.pop(0)
                                audio_path = os.path.join(audio_path_arr[index], voice_tmp_path)
                                audio_path = os.path.abspath(audio_path)
                                logger.info(f"About to play audio {audio_path}")

                                await random_speed_and_play(audio_path)
                            else:
                                # Reload the playlist
                                reload_tmp_play_list(index, play_list_arr)

                        # Placed at this level, the last playback index is recorded only after the audio of the playlist at this index has finished playing
                        last_index = index if index < (len(play_list_arr) - 1) else -1
            except Exception as e:
                logger.error(traceback.format_exc())
            
            if self.config.get("play_audio", "player") in ["pygame"]:
                Audio.mixer_copywriting.quit()
        except Exception as e:
            logger.error(traceback.format_exc())


    # Pause copywriting playback
    def pause_copywriting_play(self):
        logger.info("Pause copywriting playback")
        Audio.copywriting_play_flag = 0
        if self.config.get("play_audio", "player") == "audio_player":
            pass
            Audio.audio_player.pause_stream()
        # Since pausing in v2 does not switch the audio, pausing only the copywriting is meaningless
        elif self.config.get("play_audio", "player") == "audio_player_v2":
            pass
            # Audio.audio_player.pause_stream()
        else:
            Audio.mixer_copywriting.music.pause()

    
    # Resume the paused copywriting playback
    def unpause_copywriting_play(self):
        logger.info("Resume copywriting playback")
        Audio.copywriting_play_flag = 2
        # print(f"Audio.copywriting_play_flag={Audio.copywriting_play_flag}")
        if self.config.get("play_audio", "player") in ["audio_player", "audio_player_v2"]:
            pass
            Audio.audio_player.resume_stream()
        else:
            Audio.mixer_copywriting.music.unpause()

    
    # Stop copywriting playback
    def stop_copywriting_play(self):
        logger.info("Stop copywriting playback")
        Audio.copywriting_play_flag = 0
        if self.config.get("play_audio", "player") == "audio_player":
            Audio.audio_player.pause_stream()
        # Since pausing in v2 does not switch the audio, pausing only the copywriting is meaningless
        elif self.config.get("play_audio", "player") == "audio_player_v2":
            pass
            # Audio.audio_player.pause_stream()
        else:
            Audio.mixer_copywriting.music.stop()


    # Merge copywriting audio files
    def merge_audio_files(self, directory, base_filename, last_index, pause_duration=1, format="wav"):
        merged_audio = None

        for i in range(1, last_index+1):
            filename = f"{base_filename}-{i}.{format}"  # Assume the audio file is in wav format
            filepath = os.path.join(directory, filename)

            if os.path.isfile(filepath):
                audio_segment = AudioSegment.from_file(filepath)
                
                if pause_duration > 0 and merged_audio is not None:
                    pause = AudioSegment.silent(duration=pause_duration * 1000)  # Convert seconds to milliseconds
                    merged_audio += pause
                
                if merged_audio is None:
                    merged_audio = audio_segment
                else:
                    merged_audio += audio_segment

                os.remove(filepath)  # Delete the merged audio files

        if merged_audio is not None:
            merged_filename = f"{base_filename}.wav"  # Merged file name
            merged_filepath = os.path.join(directory, merged_filename)
            merged_audio.export(merged_filepath, format="wav")
            logger.info(f"Audio files merged successfully: {merged_filepath}")
        else:
            logger.error("No audio files to merge were found")


    # Synthesize audio using the local configuration, returns the audio path
    async def audio_synthesis_use_local_config(self, content, audio_synthesis_type="edge-tts"):
        """Synthesize audio using the local configuration, returns the audio path

        Args:
            content (str): Text content to synthesize
            audio_synthesis_type (str, optional): TTS type used. Defaults to "edge-tts".

        Returns:
            str: Path of the synthesized audio
        """
        # Reload the config
        self.reload_config(self.config_path)

        vits = self.config.get("vits")
        vits_fast = self.config.get("vits_fast")
        openai_tts = self.config.get("openai_tts")
    
        if audio_synthesis_type == "vits":
            # Language detection
            language = self.common.lang_check(content)

            # logger.info("language=" + language)

            data = {
                "type": vits["type"],
                "api_ip_port": vits["api_ip_port"],
                "id": vits["id"],
                "format": vits["format"],
                "lang": language,
                "length": vits["length"],
                "noise": vits["noise"],
                "noisew": vits["noisew"],
                "max": vits["max"],
                "sdp_radio": vits["sdp_radio"],
                "content": content,
                "gpt_sovits": vits["gpt_sovits"],
            }

            # Call the API to synthesize speech
            voice_tmp_path = await self.my_tts.vits_api(data)
                

        elif audio_synthesis_type == "bert_vits2":
        
            if self.config.get("bert_vits2", "language") == "auto":
                # Auto-detect language
                language = self.common.lang_check(content)

                logger.debug(f'language={language}')

                # Custom language name (must match the request parsing)
                language_name_dict = {"en": "EN", "zh": "ZH", "ja": "JP"}  

                if language in language_name_dict:
                    language = language_name_dict[language]
                else:
                    language = "ZH"  # Default value when the language code cannot be identified
            else:
                language = self.config.get("bert_vits2", "language")
                
            data = {
                "api_ip_port": self.config.get("bert_vits2", "api_ip_port"),
                "type": self.config.get("bert_vits2", "type"),
                "model_id": self.config.get("bert_vits2", "model_id"),
                "speaker_name": self.config.get("bert_vits2", "speaker_name"),
                "speaker_id": self.config.get("bert_vits2", "speaker_id"),
                "language": language,
                "length": self.config.get("bert_vits2", "length"),
                "noise": self.config.get("bert_vits2", "noise"),
                "noisew": self.config.get("bert_vits2", "noisew"),
                "sdp_radio": self.config.get("bert_vits2", "sdp_radio"),
                "auto_translate": self.config.get("bert_vits2", "auto_translate"),
                "auto_split": self.config.get("bert_vits2", "auto_split"),
                "emotion": self.config.get("bert_vits2", "emotion"),
                "style_text": self.config.get("bert_vits2", "style_text"),
                "style_weight": self.config.get("bert_vits2", "style_weight"),
                "刘悦-中文特化API": self.config.get("bert_vits2", "刘悦-中文特化API"),
                "content": content
            }

            logger.info(f"data={data}")

            # Call the API to synthesize speech
            voice_tmp_path = await self.my_tts.bert_vits2_api(data)
        elif audio_synthesis_type == "vits_fast":
            if vits_fast["language"] == "Auto detect":
                # Auto-detect language
                language = self.common.lang_check(content)

                logger.debug(f'language={language}')

                # Custom language name (must match the request parsing)
                language_name_dict = {"en": "English", "zh": "简体中文", "ja": "日本語"}  

                if language in language_name_dict:
                    language = language_name_dict[language]
                else:
                    language = "简体中文"  # Default value when the language code cannot be identified
            else:
                language = vits_fast["language"]

            # logger.info("language=" + language)

            data = {
                "api_ip_port": vits_fast["api_ip_port"],
                "character": vits_fast["character"],
                "speed": vits_fast["speed"],
                "language": language,
                "content": content
            }

            # Call the API to synthesize speech
            voice_tmp_path = self.my_tts.vits_fast_api(data)
        elif audio_synthesis_type == "edge-tts":
            data = {
                "content": content,
                "edge-tts": self.config.get("edge-tts")
            }

            # Call the API to synthesize speech
            voice_tmp_path = await self.my_tts.edge_tts_api(data)

        elif audio_synthesis_type == "vieneu":
            data = {
                "content": content,
                "vieneu": self.config.get("vieneu"),
                "edge-tts": self.config.get("edge-tts")
            }

            voice_tmp_path = await self.my_tts.vieneu_tts_api(data)

        elif audio_synthesis_type == "elevenlabs":
            return
        
            try:
                # If a key is configured, set it0.0
                if message["data"]["elevenlabs_api_key"] != "":
                    set_api_key(message["data"]["elevenlabs_api_key"])

                audio = generate(
                    text=message["content"],
                    voice=message["data"]["elevenlabs_voice"],
                    model=message["data"]["elevenlabs_model"]
                )

                # play(audio)
            except Exception as e:
                logger.error(traceback.format_exc())
                return

        elif audio_synthesis_type == "openai_tts":
            data = {
                "type": openai_tts["type"],
                "api_ip_port": openai_tts["api_ip_port"],
                "model": openai_tts["model"],
                "voice": openai_tts["voice"],
                "api_key": openai_tts["api_key"],
                "content": content
            }

            # Call the API to synthesize speech
            voice_tmp_path = self.my_tts.openai_tts_api(data)
            
        
        elif audio_synthesis_type == "gradio_tts":
            data = {
                "request_parameters": self.config.get("gradio_tts", "request_parameters"),
                "content": content
            }
            # Call the API to synthesize speech
            voice_tmp_path = self.my_tts.gradio_tts_api(data)
        elif audio_synthesis_type == "gpt_sovits":
            if self.config.get("gpt_sovits", "language") == "Auto detect":
                # Auto-detect language
                language = self.common.lang_check(content)

                logger.debug(f'language={language}')

                # Custom language name (must match the request parsing)
                language_name_dict = {"en": "英文", "zh": "中文", "ja": "日文"}  

                if language in language_name_dict:
                    language = language_name_dict[language]
                else:
                    language = "中文"  # Default value when the language code cannot be identified
            else:
                language = self.config.get("gpt_sovits", "language")

            # Passing too much is a bit redundant
            data = {
                "type": self.config.get("gpt_sovits", "type"),
                "gradio_ip_port": self.config.get("gpt_sovits", "gradio_ip_port"),
                "ws_ip_port": self.config.get("gpt_sovits", "ws_ip_port"),
                "api_ip_port": self.config.get("gpt_sovits", "api_ip_port"),
                "ref_audio_path": self.config.get("gpt_sovits", "ref_audio_path"),
                "prompt_text": self.config.get("gpt_sovits", "prompt_text"),
                "prompt_language": self.config.get("gpt_sovits", "prompt_language"),
                "language": language,
                "cut": self.config.get("gpt_sovits", "cut"),
                "api_0322": self.config.get("gpt_sovits", "api_0322"),
                "api_0706": self.config.get("gpt_sovits", "api_0706"),
                "v2_api_0821": self.config.get("gpt_sovits", "v2_api_0821"),
                "webtts": self.config.get("gpt_sovits", "webtts"),
                "content": content
            }
                    
            # Call the API to synthesize speech
            voice_tmp_path = await self.my_tts.gpt_sovits_api(data)
        
        

        elif audio_synthesis_type == "azure_tts":
            data = {
                "subscription_key": self.config.get("azure_tts", "subscription_key"),
                "region": self.config.get("azure_tts", "region"),
                "voice_name": self.config.get("azure_tts", "voice_name"),
                "content": content
            }

            logger.debug(f"data={data}")

            voice_tmp_path = self.my_tts.azure_tts_api(data) 
        
        elif audio_synthesis_type == "cosyvoice":
            data = {
                "type": self.config.get("cosyvoice", "type"),
                "gradio_ip_port": self.config.get("cosyvoice", "gradio_ip_port"),
                "api_ip_port": self.config.get("cosyvoice", "api_ip_port"),
                "gradio_0707": self.config.get("cosyvoice", "gradio_0707"),
                "api_0819": self.config.get("cosyvoice", "api_0819"),
                "content": content
            }
            # Call the API to synthesize speech
            voice_tmp_path = await self.my_tts.cosyvoice_api(data)
        elif audio_synthesis_type == "f5_tts":
            data = {
                "type": self.config.get("f5_tts", "type"),
                "gradio_ip_port": self.config.get("f5_tts", "gradio_ip_port"),
                "ref_audio_orig": self.config.get("f5_tts", "ref_audio_orig"),
                "ref_text": self.config.get("f5_tts", "ref_text"),
                "model": self.config.get("f5_tts", "model"),
                "remove_silence": self.config.get("f5_tts", "remove_silence"),
                "cross_fade_duration": self.config.get("f5_tts", "cross_fade_duration"),
                "speed": self.config.get("f5_tts", "speed"),
                "content": content
            }
            # Call the API to synthesize speech
            voice_tmp_path = await self.my_tts.f5_tts_api(data)
        elif audio_synthesis_type == "multitts":
            data = {
                "content": content,
                "multitts": self.config.get(audio_synthesis_type),
            }
            voice_tmp_path = await self.my_tts.multitts_api(data)
        elif audio_synthesis_type == "melotts":
            data = {
                "content": content,
                "melotts": self.config.get(audio_synthesis_type),
            }
            voice_tmp_path = await self.my_tts.melotts_api(data)
        elif audio_synthesis_type == "index_tts":
            data = {
                "content": content,
                "index_tts": self.config.get(audio_synthesis_type),
            }
            voice_tmp_path = await self.my_tts.index_tts_api(data)

        return voice_tmp_path


    # Only synthesize copywriting audio
    async def copywriting_synthesis_audio(self, file_path, out_audio_path="out/", audio_synthesis_type="edge-tts"):
        """Copywriting audio synthesis

        Args:
            file_path (str): Copywriting text file path
            out_audio_path (str, optional): Folder path for audio output. Defaults to "out/".
            audio_synthesis_type (str, optional): Speech synthesis type. Defaults to "edge-tts".

        Raises:
            Exception: _description_
            Exception: _description_

        Returns:
            str: Path of the synthesized audio
        """
        try:
            max_len = self.config.get("filter", "max_len")
            max_char_len = self.config.get("filter", "max_char_len")
            file_path = os.path.join(file_path)

            audio_out_path = self.config.get("play_audio", "out_path")

            if not os.path.isabs(audio_out_path):
                if audio_out_path.startswith('./'):
                    audio_out_path = audio_out_path[2:]

                audio_out_path = os.path.join(os.getcwd(), audio_out_path)
                # Make sure the path ends with a slash
                if not audio_out_path.endswith(os.path.sep):
                    audio_out_path += os.path.sep


            logger.info(f"Copywriting about to be synthesized: {file_path}")
            
            # Extract the file name from the file path
            file_name = self.common.extract_filename(file_path)
            # Get the file content
            content = self.common.read_file_return_content(file_path)

            logger.debug(f"Raw data before audio synthesis: {content}")
            content = self.common.remove_extra_words(content, max_len, max_char_len)
            # logger.info("Trimmed synthesis text:" + text)

            content = content.replace('\n', '。')

            # Change voice and move the audio file, reducing redundancy
            async def voice_change_and_put_to_queue(voice_tmp_path):
                voice_tmp_path = await self.voice_change(voice_tmp_path)

                if voice_tmp_path:
                    # Move the audio to the temporary audio path and rename it
                    out_file_path = audio_out_path # os.path.join(os.getcwd(), audio_out_path)
                    logger.info(f"Move the temporary audio to {out_file_path}")
                    self.common.move_file(voice_tmp_path, out_file_path, file_name + "-" + str(file_index))
                
                return voice_tmp_path

            # File name auto-increment value, used for ordering when merging everything later
            file_index = 0

            # Whether to split sentences
            if self.config.get("play_audio", "text_split_enable"):
                sentences = self.common.split_sentences(content)
            else:
                sentences = [content]

            logger.info(f"sentences={sentences}")
            
            # Iterate and synthesize the copywriting audio one by one
            for content in sentences:
                # Use a regular expression to replace leading punctuation
                # ^ Marks the start of the string, [^\w\s] matches any non-alphanumeric or non-whitespace character
                content = re.sub(r'^[^\w\s]+', '', content)

                # Set the retry count
                retry_count = 3  
                while retry_count > 0:
                    file_index = file_index + 1

                    try:
                        voice_tmp_path = await self.audio_synthesis_use_local_config(content, audio_synthesis_type)
                        
                        if voice_tmp_path is None:
                            raise Exception(f"{audio_synthesis_type}Synthesis failed")
                        
                        logger.info(f"{audio_synthesis_type}Synthesis succeeded, content: [{content}], output to={voice_tmp_path}") 

                        # Change voice and move the audio file, reducing redundancy
                        tmp_path = await voice_change_and_put_to_queue(voice_tmp_path)
                        if tmp_path is None:
                            raise Exception(f"{audio_synthesis_type}Synthesis failed")

                        break
                    
                    except Exception as e:
                        logger.error(f"Attempt failed, remaining retries: {retry_count - 1}")
                        logger.error(traceback.format_exc())
                        retry_count -= 1  # Reduce the retry count
                        if retry_count <= 0:
                            logger.error(f"Retries exhausted, {audio_synthesis_type} synthesis finally failed, please check config, network and other issues")
                            self.abnormal_alarm_handle("tts")
                            return

            # Merge the audio and output to the copywriting audio path
            out_file_path = os.path.join(os.getcwd(), audio_out_path)
            self.merge_audio_files(out_file_path, file_name, file_index)

            file_path = os.path.join(os.getcwd(), audio_out_path, file_name + ".wav")
            logger.info(f"Audio after synthesis is located at {file_path}")
            # Move the audio to the specified copywriting audio path out_audio_path
            out_file_path = os.path.join(os.getcwd(), out_audio_path)
            logger.info(f"Move the audio to {out_file_path}")
            self.common.move_file(file_path, out_file_path)
            file_path = os.path.join(out_audio_path, file_name + ".wav")

            return file_path
        except Exception as e:
            logger.error(traceback.format_exc())
            return None
        

    """
    Other
    """
    
    """
    Exception alert
    """
    def abnormal_alarm_handle(self, type):
        """Exception alert

        Args:
            type (str): Alert type

        Returns:
            bool: True/False
        """

        try:
            Audio.abnormal_alarm_data[type]["error_count"] += 1

            if not self.config.get("abnormal_alarm", type, "enable"):
                return True

            logger.debug(f"abnormal_alarm_handle type={type}, error_count={Audio.abnormal_alarm_data[type]['error_count']}")

            if self.config.get("abnormal_alarm", type, "type") == "local_audio":
                # Whether the error count is greater than the auto-restart error count
                if Audio.abnormal_alarm_data[type]["error_count"] >= self.config.get("abnormal_alarm", type, "auto_restart_error_num"):
                    logger.warning(f"[Exception alert-{type}] The error count exceeded the auto-restart error count, about to restart automatically")
                    data = {
                        "type": "restart",
                        "api_type": "api",
                        "data": {
                            "config_path": "config.json"
                        }
                    }

                    webui_ip = "127.0.0.1" if self.config.get("webui", "ip") == "0.0.0.0" else self.config.get("webui", "ip")
                    self.common.send_request(f'http://{webui_ip}:{self.config.get("webui", "port")}/sys_cmd', "POST", data)
                    
                # Whether the error count is less than the alert-start error count; if so, do not trigger an alert
                if Audio.abnormal_alarm_data[type]["error_count"] < self.config.get("abnormal_alarm", type, "start_alarm_error_num"):
                    return
                
                path_list = self.common.get_all_file_paths(self.config.get("abnormal_alarm", type, "local_audio_path"))

                # Randomly pick one element from the list
                audio_path = random.choice(path_list)

                data_json = {
                    "type": "abnormal_alarm",
                    "tts_type": self.config.get("audio_synthesis_type"),
                    "data": self.config.get(self.config.get("audio_synthesis_type")),
                    "config": self.config.get("filter"),
                    "username": "System",
                    "content": os.path.join(self.config.get("abnormal_alarm", type, "local_audio_path"), self.common.extract_filename(audio_path, True))
                }

                logger.warning(f"[Exception alert-{type}] {self.common.extract_filename(audio_path, False)}")

                self.audio_synthesis(data_json)

        except Exception as e:
            logger.error(traceback.format_exc())

            return False

        return True
