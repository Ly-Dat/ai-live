import os
import threading
import schedule
import random
import asyncio, aiohttp
import traceback
import copy
import json, re

from functools import partial

from typing import *

# Key listener voice chat section
import keyboard
import pyaudio
import wave
import numpy as np
import speech_recognition as sr
from aip import AipSpeech
import signal
import time

import http.server
import socketserver

from utils.my_log import logger
from utils.common import Common
from utils.config import Config
from utils.my_handle import My_handle
import utils.my_global as my_global

"""
	___ _                       
	|_ _| | ____ _ _ __ ___  ___ 
	 | || |/ / _` | '__/ _ \/ __|
	 | ||   < (_| | | | (_) \__ \
	|___|_|\_\__,_|_|  \___/|___/

"""

config = None
common = None
my_handle = None


# Config file path
config_path = "config.json"


# webServer thread
async def web_server_thread(web_server_port):
    Handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", web_server_port), Handler) as httpd:
        logger.info(f"WebRunning on port: {web_server_port}")
        logger.info(
            f"You can directly visit the Live2D page, http://127.0.0.1:{web_server_port}/Live2D/"
        )
        httpd.serve_forever()


"""
                       _oo0oo_
                      o8888888o
                      88" . "88
                      (| -_- |)
                      0\  =  /0
                    ___/`---'\___
                  .' \\|     |// '.
                 / \\|||  :  |||// \
                / _||||| -:- |||||- \
               |   | \\\  - /// |   |
               | \_|  ''\---/''  |_/ |
               \  .-\__  '-'  ___/-. /
             ___'. .'  /--.--\  `. .'___
          ."" '<  `.___\_<|>_/___.' >' "".
         | | :  `- \`.;`\ _ /`;.`/ - ` : | |
         \  \ `_.   \_ __\ /__ _/   .-` /  /
     =====`-.____`.___ \_____/___.-`___.-'=====
                       `=---='


     ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

         Buddha bless       never crash     neverBUG
"""


# Ignition, takeoff
def start_server():
    global \
        config, \
        common, \
        my_handle, \
        config_path
    global do_listen_and_comment_thread, stop_do_listen_and_comment_thread_event
    global faster_whisper_model, sense_voice_model, is_recording, is_talk_awake

    # Key listener related
    do_listen_and_comment_thread = None
    stop_do_listen_and_comment_thread_event = threading.Event()
    # Cooldown time 0.5 seconds
    cooldown = 0.5
    last_pressed = 0
    # Recording in progress flag
    is_recording = False
    # Whether chat is awake
    is_talk_awake = False

    # Number of audio clips waiting to play (when using an audio player or projects like metahuman-stream that do not play audio through AI Vtuber, this variable records whether any audio is still unplayed)
    my_global.wait_play_audio_num = 0
    my_global.wait_synthesis_msg_num = 0

    # Get the httpx library logger
    # httpx_logger = logging.getLogger("httpx")
    # Set the httpx logger level to WARNING
    # httpx_logger.setLevel(logging.WARNING)

    # Latest live room data
    my_global.last_liveroom_data = {
        "OnlineUserCount": 0,
        "TotalUserCount": 0,
        "TotalUserCountStr": "0",
        "OnlineUserCountStr": "0",
        "MsgId": 0,
        "User": None,
        "Content": "Current viewers 0, total viewers 0",
        "RoomId": 0,
    }
    # List of the latest users who entered
    my_global.last_username_list = [""]

    my_handle = My_handle(config_path)
    if my_handle is None:
        logger.error("Program initialization failed!")
        os._exit(0)

    # Live2DThread
    try:
        if config.get("live2d", "enable"):
            web_server_port = int(config.get("live2d", "port"))
            threading.Thread(
                target=lambda: asyncio.run(web_server_thread(web_server_port))
            ).start()
    except Exception as e:
        logger.error(traceback.format_exc())
        os._exit(0)

    if platform != "wxlive":
        """

                  /@@@@@@@@          @@@@@@@@@@@@@@@].      =@@@@@@@       
                 =@@@@@@@@@^         @@@@@@@@@@@@@@@@@@`    =@@@@@@@       
                ,@@@@@@@@@@@`        @@@@@@@@@@@@@@@@@@@^   =@@@@@@@       
               .@@@@@@\@@@@@@.       @@@@@@@^   .\@@@@@@\   =@@@@@@@       
               /@@@@@/ \@@@@@\       @@@@@@@^    =@@@@@@@   =@@@@@@@       
              =@@@@@@. .@@@@@@^      @@@@@@@\]]]@@@@@@@@^   =@@@@@@@       
             ,@@@@@@^   =@@@@@@`     @@@@@@@@@@@@@@@@@@/    =@@@@@@@       
            .@@@@@@@@@@@@@@@@@@@.    @@@@@@@@@@@@@@@@/`     =@@@@@@@       
            /@@@@@@@@@@@@@@@@@@@\    @@@@@@@^               =@@@@@@@       
           =@@@@@@@@@@@@@@@@@@@@@^   @@@@@@@^               =@@@@@@@       
          ,@@@@@@@.       ,@@@@@@@`  @@@@@@@^               =@@@@@@@       
          @@@@@@@^         =@@@@@@@. @@@@@@@^               =@@@@@@@   

        """
        
        # HTTP APIThread
        def http_api_thread():
            import uvicorn
            from fastapi import FastAPI
            from fastapi.middleware.cors import CORSMiddleware
            from utils.models import (
                SendMessage,
                LLMMessage,
                CallbackMessage,
                CommonResult,
            )

            # Define the FastAPI app
            app = FastAPI()

            # Allow cross-origin requests
            app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )

            # Define the POST request path and handler function
            @app.post("/send")
            async def send(msg: SendMessage):
                global my_handle, config

                try:
                    tmp_json = msg.dict()
                    logger.info(f"Internal HTTP API send endpoint received data: {tmp_json}")
                    data_json = tmp_json["data"]
                    if "type" not in data_json:
                        data_json["type"] = tmp_json["type"]

                    if data_json["type"] in ["reread", "reread_top_priority"]:
                        my_handle.reread_handle(data_json, type=data_json["type"])
                    elif data_json["type"] == "comment":
                        my_handle.process_data(data_json, "comment")
                    elif data_json["type"] == "tuning":
                        my_handle.tuning_handle(data_json)
                    elif data_json["type"] == "gift":
                        my_handle.gift_handle(data_json)
                    elif data_json["type"] == "entrance":
                        my_handle.entrance_handle(data_json)
                    elif data_json["type"] == "product":
                        my_handle.product_handle(data_json)
                    elif data_json["type"] == "follow":
                        my_handle.follow_handle(data_json)

                    return CommonResult(code=200, message="Success")
                except Exception as e:
                    logger.error(f"Failed to send data!{e}")
                    return CommonResult(code=-1, message=f"Failed to send data!{e}")

            @app.post("/llm")
            async def llm(msg: LLMMessage):
                global my_handle, config

                try:
                    data_json = msg.dict()
                    logger.info(f"APIData received: {data_json}")

                    resp_content = my_handle.llm_handle(
                        data_json["type"], data_json, webui_show=False
                    )

                    return CommonResult(
                        code=200, message="Success", data={"content": resp_content}
                    )
                except Exception as e:
                    logger.error(f"LLM call failed!{e}")
                    return CommonResult(code=-1, message=f"LLM call failed!{e}")

            from starlette.requests import Request

            @app.post('/tts')
            async def tts(request: Request):
                try:
                    data_json = await request.json()
                    logger.info(f"APIData received: {data_json}")

                    resp_json = await My_handle.audio.tts_handle(data_json)

                    return {"code": 200, "message": "Success", "data": resp_json}
                except Exception as e:
                    logger.error(traceback.format_exc())
                    return CommonResult(code=-1, message=f"Failed!{e}")
                
            @app.post("/callback")
            async def callback(msg: CallbackMessage):
                global my_handle, config

                try:
                    data_json = msg.dict()

                    # Special callback handling
                    if data_json["type"] == "audio_playback_completed":
                        my_global.wait_play_audio_num = int(data_json["data"]["wait_play_audio_num"])
                        my_global.wait_synthesis_msg_num = int(data_json["data"]["wait_synthesis_msg_num"])
                        logger.info(f"Internal HTTP API callback endpoint, audio playback finished callback, number of audio clips waiting to play: {my_global.wait_play_audio_num}, number of messages waiting to be synthesized: {my_global.wait_synthesis_msg_num}")
                    else:
                        logger.info(f"Internal HTTP API callback endpoint received data: {data_json}")

                    # Audio playback finished
                    if data_json["type"] in ["audio_playback_completed"]:
                        my_global.wait_play_audio_num = int(data_json["data"]["wait_play_audio_num"])

                        # If the number of audio clips waiting to play is greater than10
                        if data_json["data"]["wait_play_audio_num"] > int(
                            config.get(
                                "idle_time_task", "wait_play_audio_num_threshold"
                            )
                        ):
                            logger.info(
                                f'The number of audio clips waiting to play is greater than the limit; the idle timing of the idle task is handled by {my_global.global_idle_time} -> {int(config.get("idle_time_task", "idle_time_reduce_to"))}seconds'
                            )
                            # Reset the idle timer of the idle task
                            my_global.global_idle_time = int(
                                config.get("idle_time_task", "idle_time_reduce_to")
                            )

                    return CommonResult(code=200, message="callbackProcessing succeeded!")
                except Exception as e:
                    logger.error(f"callbackProcessing failed!{e}")
                    return CommonResult(code=-1, message=f"callbackProcessing failed!{e}")

            # Get system info endpoint
            @app.get("/get_sys_info")
            async def get_sys_info():
                global my_handle, config

                try:
                    data = {
                        "audio": my_handle.get_audio_info(),
                        "metahuman-stream": {
                            "wait_play_audio_num": my_global.wait_play_audio_num,
                            "wait_synthesis_msg_num": my_global.wait_synthesis_msg_num,
                        }
                    }

                    return CommonResult(code=200, data=data, message="get_sys_infoProcessing succeeded!")
                except Exception as e:
                    logger.error(f"get_sys_infoProcessing failed!{e}")
                    return CommonResult(code=-1, message=f"get_sys_infoProcessing failed!{e}")

            

            logger.info("HTTP APIThread started!")

            # Expose static files in the local directory (such as CSS, JavaScript, images) to the web server so users can access them via specific URLs.
            if config.get("webui", "local_dir_to_endpoint", "enable"):
                for tmp in config.get("webui", "local_dir_to_endpoint", "config"):
                    from fastapi.staticfiles import StaticFiles
                    app.mount(tmp['url_path'], StaticFiles(directory=tmp['local_dir']), name=tmp['local_dir'])
                    
            uvicorn.run(app, host="0.0.0.0", port=config.get("api_port"))
            #uvicorn.run(app, host="0.0.0.0", port=config.get("api_port"), ssl_certfile="F:\\FunASR_WS\\cert.pem", ssl_keyfile="F:\\FunASR_WS\\key.pem")

        # HTTP APIThread and start it
        inside_http_api_thread = threading.Thread(target=http_api_thread)
        inside_http_api_thread.start()

    

    """
    Key listener section
    """

    # Recording feature (recordings that are too short will cause errors when sent to OpenAI speech-to-text, so pay attention)
    def record_audio():
        pressdown_num = 0
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 44100
        WAVE_OUTPUT_FILENAME = "out/record.wav"
        p = pyaudio.PyAudio()
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK,
        )
        frames = []
        logger.info("Recording...")
        flag = 0
        while 1:
            while keyboard.is_pressed("RIGHT_SHIFT"):
                flag = 1
                data = stream.read(CHUNK)
                frames.append(data)
                pressdown_num = pressdown_num + 1
            if flag:
                break
        logger.info("Stopped recording.")
        stream.stop_stream()
        stream.close()
        p.terminate()
        wf = wave.open(WAVE_OUTPUT_FILENAME, "wb")
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))
        wf.close()
        if pressdown_num >= 5:  # Crude handling approach
            return 1
        else:
            logger.info("Silly fish, silly fish, so short so short (recording too short, press right shift to record again)")
            return 0

    # THRESHOLD Set the volume threshold, default 800.0, adjust as needed; silence_threshold sets the silence threshold, adjust as needed
    def audio_listen(volume_threshold=800.0, silence_threshold=15):
        audio = pyaudio.PyAudio()

        # Set audio parameters
        FORMAT = pyaudio.paInt16
        CHANNELS = config.get("talk", "CHANNELS")
        RATE = config.get("talk", "RATE")
        CHUNK = 1024

        stream = audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK,
            input_device_index=int(config.get("talk", "device_index")),
        )

        frames = []  # Store the recorded audio frames

        is_speaking = False  # Whether speaking
        silent_count = 0  # Silence count
        speaking_flag = False  # Recording flag, not important

        logger.info("[About to start recording……]")

        while True:
            # Do not record while playing
            if config.get("talk", "no_recording_during_playback"):
                # There is audio waiting to be synthesized, or synthesized audio not yet played, or playing, or data being processed
                if (
                    my_handle.is_audio_queue_empty() != 15
                    or my_handle.is_handle_empty() == 1
                    or my_global.wait_play_audio_num > 0
                ):
                    time.sleep(
                        float(
                            config.get(
                                "talk", "no_recording_during_playback_sleep_interval"
                            )
                        )
                    )
                    continue

            # Read audio data
            data = stream.read(CHUNK)
            audio_data = np.frombuffer(data, dtype=np.short)
            max_dB = np.max(audio_data)
            # logger.info(max_dB)
            if max_dB > volume_threshold:
                is_speaking = True
                silent_count = 0
            elif is_speaking is True:
                silent_count += 1

            if is_speaking is True:
                frames.append(data)
                if speaking_flag is False:
                    logger.info("[Recording in progress……]")
                    speaking_flag = True

            if silent_count >= silence_threshold:
                break

        logger.info("[Voice input finished]")

        # Save the audio as a WAV file
        """with wave.open(WAVE_OUTPUT_FILENAME, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(pyaudio.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))"""
        return frames

    # Handle chat logic; takes the text content after ASR
    def talk_handle(content: str):
        global is_talk_awake

        def clear_queue_and_stop_audio_play(message_queue: bool=True, voice_tmp_path_queue: bool=True, stop_audio_play: bool=True):
            """
            Clear the queue or stop audio playback
            """
            if message_queue:
                ret = my_handle.clear_queue("message_queue")
                if ret:
                    logger.info("Successfully cleared the queue of messages waiting to be synthesized!")
                else:
                    logger.error("Failed to clear the queue of messages waiting to be synthesized!")
            if voice_tmp_path_queue:
                ret = my_handle.clear_queue("voice_tmp_path_queue")
                if ret:
                    logger.info("Successfully cleared the queue of audio waiting to play!")
                else:
                    logger.error("Failed to clear the queue of audio waiting to play!")
            if stop_audio_play:
                ret = my_handle.stop_audio("pygame", True, True)

        try:
            # Check and switch the chat wake state
            def check_talk_awake(content: str):
                """Check and switch the chat wake state

                Args:
                    content (str): Chat content

                Returns:
                    dict:
                        ret Whether trigger is needed
                        is_talk_awake Current wake state
                        first Whether this is the first wake or sleep trigger, used for the special prompt on the first switch
                """
                global is_talk_awake

                # Determine whether the wake word feature is enabled
                if config.get("talk", "wakeup_sleep", "enable"):
                    if config.get("talk", "wakeup_sleep", "mode") == "Persistent wake-up":
                        # Determine whether it is currently in the awake state
                        if is_talk_awake is False:
                            # Determine whether the text contains a wake word
                            trigger_word = common.find_substring_in_list(
                                content, config.get("talk", "wakeup_sleep", "wakeup_word")
                            )
                            if trigger_word:
                                is_talk_awake = True
                                logger.info("[Chat wake succeeded]")
                                return {
                                    "ret": 0,
                                    "is_talk_awake": is_talk_awake,
                                    "first": True,
                                    "trigger_word": trigger_word,
                                }
                            return {
                                "ret": -1,
                                "is_talk_awake": is_talk_awake,
                                "first": False,
                            }
                        else:
                            # Determine whether the text contains a sleep word
                            trigger_word = common.find_substring_in_list(
                                content, config.get("talk", "wakeup_sleep", "sleep_word")
                            )
                            if trigger_word:
                                is_talk_awake = False
                                logger.info("[Chat sleep succeeded]")
                                return {
                                    "ret": 0,
                                    "is_talk_awake": is_talk_awake,
                                    "first": True,
                                    "trigger_word": trigger_word,
                                }
                            return {
                                "ret": 0,
                                "is_talk_awake": is_talk_awake,
                                "first": False,
                            }
                    elif config.get("talk", "wakeup_sleep", "mode") == "Single wake-up":
                        # No need to check whether currently awake, since the state is cleared by default
                        # Determine whether the text contains a wake word
                        trigger_word = common.find_substring_in_list(
                            content, config.get("talk", "wakeup_sleep", "wakeup_word")
                        )
                        if trigger_word:
                            is_talk_awake = True
                            logger.info("[Chat wake succeeded]")
                            return {
                                "ret": 0,
                                "is_talk_awake": is_talk_awake,
                                # No first-wake prompt in single wake mode
                                "first": False,
                                "trigger_word": trigger_word,
                            }
                        return {
                            "ret": -1,
                            "is_talk_awake": is_talk_awake,
                            "first": False,
                        }


                return {"ret": 0, "is_talk_awake": True, "trigger_word": "", "first": False}

            # Output the recognition result
            logger.info("Recognition result: " + content)

            # Empty content filter
            if content == "":
                return

            username = config.get("talk", "username")

            data = {"platform": "Local chat", "username": username, "content": content}
            
            # Check and switch the chat wake state
            check_resp = check_talk_awake(content)
            if check_resp["ret"] == 0:
                # In the awake state
                if check_resp["is_talk_awake"]:
                    # With long-term wake and not the first trigger, the following content will not carry the trigger word, and even if it does it should not be replaced
                    if config.get("talk", "wakeup_sleep", "mode") == "Persistent wake-up" and not check_resp["first"]:
                        pass
                    else:
                        # Replace the trigger word with empty
                        content = content.replace(check_resp["trigger_word"], "").strip()

                    # A wake word may be spoken alone, so on first wake the wake word gets filtered out and content becomes empty, so the wake prompt would not play; this needs handling
                    if content == "" and not check_resp["first"]:
                        return
                    
                    # Assign todata
                    data["content"] = content
                    
                    # First trigger mode switch, play the wake copywriting
                    if check_resp["first"]:
                        # Get copywriting randomly TODO: if this feature tests successfully, all similar features will use this function to simplify code
                        resp_json = common.get_random_str_in_list_and_format(
                            ori_list=config.get(
                                "talk", "wakeup_sleep", "wakeup_copywriting"
                            )
                        )
                        if resp_json["ret"] == 0:
                            data["content"] = resp_json["content"]
                            data["insert_index"] = -1
                            my_handle.reread_handle(data)
                    else:
                        # If enabled"Interrupt the conversation"Feature
                        if config.get("talk", "interrupt_talk", "enable"):
                            # Determine whether the text contains an interrupt word
                            interrupt_word = common.find_substring_in_list(
                                data["content"], config.get("talk", "interrupt_talk", "keywords")
                            )
                            if interrupt_word:
                                logger.info(f"[Chat interrupt] Interrupt word hit: {interrupt_word}")
                                # Get the data types to clear from the config
                                clean_type = config.get("talk", "interrupt_talk", "clean_type")
                                # Whether each data type is cleared
                                message_queue = "message_queue" in clean_type
                                voice_tmp_path_queue = "voice_tmp_path_queue" in clean_type
                                stop_audio_play = "stop_audio_play" in clean_type
                                
                                clear_queue_and_stop_audio_play(message_queue, voice_tmp_path_queue, stop_audio_play)
                                return False

                        # Pass to my_handle for subsequent processing
                        my_handle.process_data(data, "talk")

                        # In single wake mode, close after waking
                        if config.get("talk", "wakeup_sleep", "mode") == "Single wake-up":
                            is_talk_awake = False
                # In the sleep state
                else:
                    # First time entering sleep, play the sleep copywriting
                    if check_resp["first"]:
                        resp_json = common.get_random_str_in_list_and_format(
                            ori_list=config.get(
                                "talk", "wakeup_sleep", "sleep_copywriting"
                            )
                        )
                        if resp_json["ret"] == 0:
                            data["content"] = resp_json["content"]
                            data["insert_index"] = -1
                            my_handle.reread_handle(data)
        except Exception as e:
            logger.error(traceback.format_exc())

    # Perform recording, recognition and submission
    def do_listen_and_comment(status=True):
        global \
            stop_do_listen_and_comment_thread_event, \
            faster_whisper_model, \
            sense_voice_model, \
            is_recording, \
            is_talk_awake

        try:
            is_recording = True

            config = Config(config_path)
            # Whether key listener and direct conversation are enabled; if not, no need to run
            if not config.get("talk", "key_listener_enable") and not config.get("talk", "direct_run_talk"):
                is_recording = False
                return

            # For faster_whisper, load the model once and share it to reduce overhead
            if "faster_whisper" == config.get("talk", "type"):
                from faster_whisper import WhisperModel

                if faster_whisper_model is None:
                    logger.info("faster_whisper Model loading, please wait...")
                    # Run on GPU with FP16
                    faster_whisper_model = WhisperModel(
                        model_size_or_path=config.get(
                            "talk", "faster_whisper", "model_size"
                        ),
                        device=config.get("talk", "faster_whisper", "device"),
                        compute_type=config.get(
                            "talk", "faster_whisper", "compute_type"
                        ),
                        download_root=config.get(
                            "talk", "faster_whisper", "download_root"
                        ),
                    )
                    logger.info("faster_whisper Model loaded, you can start speaking now meow~")
            elif "sensevoice" == config.get("talk", "type"):
                from funasr import AutoModel

                logger.info("sensevoice Model loading, please wait...")
                asr_model_path = config.get("talk", "sensevoice", "asr_model_path")
                vad_model_path = config.get("talk", "sensevoice", "vad_model_path")
                if sense_voice_model is None:
                    sense_voice_model = AutoModel(
                        model=asr_model_path,
                        vad_model=vad_model_path,
                        vad_kwargs={
                            "max_single_segment_time": int(
                                config.get(
                                    "talk", "sensevoice", "vad_max_single_segment_time"
                                )
                            )
                        },
                        trust_remote_code=True,
                        device=config.get("talk", "sensevoice", "device"),
                        remote_code="./sensevoice/model.py",
                    )

                    logger.info("sensevoice Model loaded, you can start speaking now meow~")

            while True:
                try:
                    # Check whether a stop event was received
                    if stop_do_listen_and_comment_thread_event.is_set():
                        logger.info("Stop recording~")
                        is_recording = False
                        break

                    config = Config(config_path)

                    # Execute according to the connected speech recognition type
                    if config.get("talk", "type") in [
                        "baidu",
                        "faster_whisper",
                        "sensevoice",
                    ]:
                        # Set audio parameters
                        FORMAT = pyaudio.paInt16
                        CHANNELS = config.get("talk", "CHANNELS")
                        RATE = config.get("talk", "RATE")

                        audio_out_path = config.get("play_audio", "out_path")

                        if not os.path.isabs(audio_out_path):
                            if not audio_out_path.startswith("./"):
                                audio_out_path = "./" + audio_out_path
                        file_name = "asr_" + common.get_bj_time(4) + ".wav"
                        WAVE_OUTPUT_FILENAME = common.get_new_audio_path(
                            audio_out_path, file_name
                        )
                        # WAVE_OUTPUT_FILENAME = './out/asr_' + common.get_bj_time(4) + '.wav'

                        frames = audio_listen(
                            config.get("talk", "volume_threshold"),
                            config.get("talk", "silence_threshold"),
                        )

                        # Save the audio as a WAV file
                        with wave.open(WAVE_OUTPUT_FILENAME, "wb") as wf:
                            wf.setnchannels(CHANNELS)
                            wf.setsampwidth(pyaudio.get_sample_size(FORMAT))
                            wf.setframerate(RATE)
                            wf.writeframes(b"".join(frames))

                        if config.get("talk", "type") == "baidu":
                            # Read the audio file
                            with open(WAVE_OUTPUT_FILENAME, "rb") as fp:
                                audio = fp.read()

                            # Initialize the AipSpeech object
                            baidu_client = AipSpeech(
                                config.get("talk", "baidu", "app_id"),
                                config.get("talk", "baidu", "api_key"),
                                config.get("talk", "baidu", "secret_key"),
                            )

                            # Recognize the audio file
                            res = baidu_client.asr(
                                audio,
                                "wav",
                                16000,
                                {
                                    "dev_pid": 1536,
                                },
                            )
                            if res["err_no"] == 0:
                                content = res["result"][0]

                                talk_handle(content)
                            else:
                                logger.error(f"Baidu API error: {res}")
                        elif config.get("talk", "type") == "faster_whisper":
                            logger.debug("faster_whisperModel loading...")

                            language = config.get("talk", "faster_whisper", "language")
                            if language == "Auto detect":
                                language = None

                            segments, info = faster_whisper_model.transcribe(
                                WAVE_OUTPUT_FILENAME,
                                language=language,
                                beam_size=config.get(
                                    "talk", "faster_whisper", "beam_size"
                                ),
                            )

                            logger.debug(
                                "Recognition language: '%s', probability: %f"
                                % (info.language, info.language_probability)
                            )

                            content = ""
                            for segment in segments:
                                logger.info(
                                    "[%.2fs -> %.2fs] %s"
                                    % (segment.start, segment.end, segment.text)
                                )
                                content += segment.text + "。"

                            if content == "":
                                # Restore the recording flag
                                is_recording = False
                                return

                            talk_handle(content)
                        elif config.get("talk", "type") == "sensevoice":
                            res = sense_voice_model.generate(
                                input=WAVE_OUTPUT_FILENAME,
                                cache={},
                                language=config.get("talk", "sensevoice", "language"),
                                text_norm=config.get("talk", "sensevoice", "text_norm"),
                                batch_size_s=int(
                                    config.get("talk", "sensevoice", "batch_size_s")
                                ),
                                batch_size=int(
                                    config.get("talk", "sensevoice", "batch_size")
                                ),
                            )

                            def remove_angle_brackets_content(input_string: str):
                                # Use a regular expression to match and delete content between <>
                                return re.sub(r"<.*?>", "", input_string)

                            content = remove_angle_brackets_content(res[0]["text"])

                            talk_handle(content)
                    elif "google" == config.get("talk", "type"):
                        # Create a Recognizer object
                        r = sr.Recognizer()

                        try:
                            # Open the microphone to record
                            with sr.Microphone() as source:
                                logger.info("Recording...")
                                # Get audio data from the microphone
                                audio = r.listen(source)
                                logger.info("Recorded successfully")

                                # Perform Google real-time speech recognition en-US zh-CN ja-JP
                                content = r.recognize_google(
                                    audio,
                                    language=config.get("talk", "google", "tgt_lang"),
                                )

                                talk_handle(content)
                        except sr.UnknownValueError:
                            logger.warning("Unable to recognize the input speech")
                        except sr.RequestError as e:
                            logger.error("Request error: " + str(e))

                    is_recording = False

                    if not status:
                        return
                except Exception as e:
                    logger.error(traceback.format_exc())
                    is_recording = False
                    return
        except Exception as e:
            logger.error(traceback.format_exc())
            is_recording = False
            return

    def on_key_press(event):
        global \
            do_listen_and_comment_thread, \
            stop_do_listen_and_comment_thread_event, \
            is_recording

        # Whether key listener is enabled; if not, no need to run
        if not config.get("talk", "key_listener_enable"):
            return

        # if event.name in ['z', 'Z', 'c', 'C'] and keyboard.is_pressed('ctrl'):
        # logger.info("Exit the program")

        # os._exit(0)

        # KeyCD
        current_time = time.time()
        if current_time - last_pressed < cooldown:
            return

        """
        Judgment for the trigger key section
        """
        trigger_key_lower = None
        stop_trigger_key_lower = None

        # trigger_keyIt is a letter, all lowercase
        if trigger_key.isalpha():
            trigger_key_lower = trigger_key.lower()

        # stop_trigger_keyIt is a letter, all lowercase
        if stop_trigger_key.isalpha():
            stop_trigger_key_lower = stop_trigger_key.lower()

        if trigger_key_lower:
            if event.name == trigger_key or event.name == trigger_key_lower:
                logger.info(f"Detected key press {event.name}, recording is about to start~")
            elif event.name == stop_trigger_key or event.name == stop_trigger_key_lower:
                logger.info(f"Detected key press {event.name}, recording is about to stop~")
                stop_do_listen_and_comment_thread_event.set()
                return
            else:
                return
        else:
            if event.name == trigger_key:
                logger.info(f"Detected key press {event.name}, recording is about to start~")
            elif event.name == stop_trigger_key:
                logger.info(f"Detected key press {event.name}, recording is about to stop~")
                stop_do_listen_and_comment_thread_event.set()
                return
            else:
                return

        if not is_recording:
            # Whether continuous conversation mode is enabled
            if config.get("talk", "continuous_talk"):
                stop_do_listen_and_comment_thread_event.clear()
                do_listen_and_comment_thread = threading.Thread(
                    target=do_listen_and_comment, args=(True,)
                )
                do_listen_and_comment_thread.start()
            else:
                stop_do_listen_and_comment_thread_event.clear()
                do_listen_and_comment_thread = threading.Thread(
                    target=do_listen_and_comment, args=(False,)
                )
                do_listen_and_comment_thread.start()
        else:
            logger.warning("Recording in progress... please do not click record repeatedly")

    # Key listener
    def key_listener():
        # Register the callback function for the key press event
        keyboard.on_press(on_key_press)

        try:
            # Enter listening state, waiting for a key press
            keyboard.wait()
        except KeyboardInterrupt:
            os._exit(0)

    # Run voice conversation directly
    def direct_run_talk():
        global \
            do_listen_and_comment_thread, \
            stop_do_listen_and_comment_thread_event, \
            is_recording

        if not is_recording:
            # Whether continuous conversation mode is enabled
            if config.get("talk", "continuous_talk"):
                stop_do_listen_and_comment_thread_event.clear()
                do_listen_and_comment_thread = threading.Thread(
                    target=do_listen_and_comment, args=(True,)
                )
                do_listen_and_comment_thread.start()
            else:
                stop_do_listen_and_comment_thread_event.clear()
                do_listen_and_comment_thread = threading.Thread(
                    target=do_listen_and_comment, args=(False,)
                )
                do_listen_and_comment_thread.start()

    # Read the trigger key string config from the config file
    trigger_key = config.get("talk", "trigger_key")
    stop_trigger_key = config.get("talk", "stop_trigger_key")

    # Whether key listener is enabled
    if config.get("talk", "key_listener_enable"):
        logger.info(
            f"Press the {trigger_key} key on the keyboard to record, meow~ Since other tasks still need to start, if the key does not respond please wait a while (if using local ASR, wait for the model to finish loading before using)"
        )

    # Whether direct conversation is enabled; if so, speech recognition starts directly on first run without manually clicking the start key. Use together with continuous conversation and wake words on systems where keys cannot trigger
    if config.get("talk", "direct_run_talk"):
        logger.info("Direct conversation mode: on first run speech recognition starts directly without manually clicking the start key (if using local ASR, wait for the model to finish loading before using)")
        direct_run_talk()

    # Create and start the key listener thread; in chat mode it is kept just to keep the program blocking
    thread = threading.Thread(target=key_listener)
    thread.start()

    # Scheduled task
    def schedule_task(index):
        global config, common, my_handle

        logger.debug("Scheduled task running...")
        hour, min = common.get_bj_time(6)

        if 0 <= hour and hour < 6:
            time = f"Early morning, {hour}:{min:02d}"
        elif 6 <= hour and hour < 9:
            time = f"Morning, {hour}:{min:02d}"
        elif 9 <= hour and hour < 12:
            time = f"Morning, {hour}:{min:02d}"
        elif hour == 12:
            time = f"Noon, {hour}:{min:02d}"
        elif 13 <= hour and hour < 18:
            time = f"Afternoon, {hour}:{min:02d}"
        elif 18 <= hour and hour < 20:
            time = f"Evening, {hour}:{min:02d}"
        elif 20 <= hour and hour < 24:
            time = f"Night, {hour}:{min:02d}"

        # Randomly get a value from the list by the corresponding index
        if len(config.get("schedule")[index]["copy"]) <= 0:
            return None

        random_copy = random.choice(config.get("schedule")[index]["copy"])

        # Assume there are multiple unknown variables; users can define dynamic variables here
        variables = {
            "time": time,
            "user_num": "N",
            "last_username": my_global.last_username_list[-1],
        }

        # Special handling for platforms with user data
        if platform in ["dy", "tiktok"]:
            variables["user_num"] = my_global.last_liveroom_data["OnlineUserCount"]

        # Use a dictionary for string replacement
        if any(var in random_copy for var in variables):
            content = random_copy.format(
                **{var: value for var, value in variables.items() if var in random_copy}
            )
        else:
            content = random_copy

        content = common.brackets_text_randomize(content)

        data = {"platform": platform, "username": "Scheduled task", "content": content}

        logger.info(f"Scheduled task: {content}")

        my_handle.process_data(data, "schedule")

        # schedule.clear(index)

    # Start scheduled task
    def run_schedule():
        global config

        try:
            for index, task in enumerate(config.get("schedule")):
                if task["enable"]:
                    # logger.info(task)
                    min_seconds = int(task["time_min"])
                    max_seconds = int(task["time_max"])

                    def schedule_random_task(index, min_seconds, max_seconds):
                        schedule.clear(index)
                        # Randomly pick the next task run time between min_seconds and max_seconds
                        next_time = random.randint(min_seconds, max_seconds)
                        # logger.info(f"Next task {index} scheduled in {next_time} seconds at {time.ctime()}")

                        schedule_task(index)

                        schedule.every(next_time).seconds.do(
                            schedule_random_task, index, min_seconds, max_seconds
                        ).tag(index)

                    schedule_random_task(index, min_seconds, max_seconds)
        except Exception as e:
            logger.error(traceback.format_exc())

        while True:
            schedule.run_pending()
            # time.sleep(1)  # Control the interval of each loop to avoid using too much CPU

    # Create the scheduled task sub-thread and start it; when the platform is dy, the scheduled task is started by default just to block
    if any(item["enable"] for item in config.get("schedule")) or platform == "dy":
        # Create the scheduled task sub-thread and start it
        schedule_thread = threading.Thread(target=run_schedule)
        schedule_thread.start()

    # Start dynamic copywriting
    async def run_trends_copywriting():
        global config

        try:
            if not config.get("trends_copywriting", "enable"):
                return

            logger.info("Dynamic copywriting task thread is running...")

            while True:
                # Copywriting file path list
                copywriting_file_path_list = []

                # Get the dynamic copywriting list
                for copywriting in config.get("trends_copywriting", "copywriting"):
                    # Get the absolute paths of all files in the folder, including file extensions
                    for tmp in common.get_all_file_paths(copywriting["folder_path"]):
                        copywriting_file_path_list.append(tmp)

                    # Whether random playback is enabled
                    if config.get("trends_copywriting", "random_play"):
                        random.shuffle(copywriting_file_path_list)

                    logger.debug(
                        f"copywriting_file_path_list={copywriting_file_path_list}"
                    )

                    # Iterate over the copywriting file path list
                    for copywriting_file_path in copywriting_file_path_list:
                        # Get the copywriting file content
                        copywriting_file_content = common.read_file_return_content(
                            copywriting_file_path
                        )
                        # Whether to use a prompt to convert the copywriting content
                        if copywriting["prompt_change_enable"]:
                            data_json = {
                                "username": "trends_copywriting",
                                "content": copywriting["prompt_change_content"]
                                + copywriting_file_content,
                            }

                            # Call the function to do LLM processing, generate the reply and synthesize audio; needs careful thought to implement
                            data_json["content"] = my_handle.llm_handle(
                                config.get("trends_copywriting", "llm_type"), data_json
                            )
                        else:
                            copywriting_file_content = common.brackets_text_randomize(
                                copywriting_file_content
                            )

                            data_json = {
                                "username": "trends_copywriting",
                                "content": copywriting_file_content,
                            }

                        logger.debug(
                            f'copywriting_file_content={copywriting_file_content},content={data_json["content"]}'
                        )

                        # Empty data check
                        if (
                            data_json["content"] is not None
                            and data_json["content"] != ""
                        ):
                            # Send to direct repeat for processing
                            my_handle.reread_handle(
                                data_json, filter=True, type="trends_copywriting"
                            )

                            await asyncio.sleep(
                                config.get("trends_copywriting", "play_interval")
                            )
        except Exception as e:
            logger.error(traceback.format_exc())

    if config.get("trends_copywriting", "enable"):
        # Create the dynamic copywriting sub-thread and start it
        threading.Thread(target=lambda: asyncio.run(run_trends_copywriting())).start()

    # Idle task
    async def idle_time_task():
        global config, common

        try:
            if not config.get("idle_time_task", "enable"):
                return

            logger.info("Idle task thread is running...")

            # Record the last triggered task type
            last_mode = 0
            copywriting_copy_list = None
            comment_copy_list = None
            local_audio_path_list = None

            overflow_time_min = int(config.get("idle_time_task", "idle_time_min"))
            overflow_time_max = int(config.get("idle_time_task", "idle_time_max"))
            overflow_time = random.randint(overflow_time_min, overflow_time_max)

            logger.info(f"The next idle task will run in {overflow_time} seconds")

            def load_data_list(type):
                if type == "copywriting":
                    tmp = config.get("idle_time_task", "copywriting", "copy")
                elif type == "comment":
                    tmp = config.get("idle_time_task", "comment", "copy")
                elif type == "local_audio":
                    tmp = config.get("idle_time_task", "local_audio", "path")

                logger.debug(f"type={type}, tmp={tmp}")
                tmp2 = copy.copy(tmp)
                return tmp2

            # Load data intolist
            copywriting_copy_list = load_data_list("copywriting")
            comment_copy_list = load_data_list("comment")
            local_audio_path_list = load_data_list("local_audio")

            logger.debug(f"copywriting_copy_list={copywriting_copy_list}")
            logger.debug(f"comment_copy_list={comment_copy_list}")
            logger.debug(f"local_audio_path_list={local_audio_path_list}")

            def do_task(
                last_mode,
                copywriting_copy_list,
                comment_copy_list,
                local_audio_path_list,
            ):
                # Reset the idle count
                my_global.global_idle_time = 0

                # Idle task processing
                if config.get("idle_time_task", "copywriting", "enable"):
                    if last_mode == 0:
                        # Whether random trigger is enabled
                        if config.get("idle_time_task", "copywriting", "random"):
                            logger.debug("Switch to copywriting trigger mode")
                            if copywriting_copy_list != []:
                                # Randomly shuffle the elements in the list
                                random.shuffle(copywriting_copy_list)
                                copywriting_copy = copywriting_copy_list.pop(0)
                            else:
                                # Refresh the list data
                                copywriting_copy_list = load_data_list("copywriting")
                                # Randomly shuffle the elements in the list
                                random.shuffle(copywriting_copy_list)
                                if copywriting_copy_list != []:
                                    copywriting_copy = copywriting_copy_list.pop(0)
                                else:
                                    return (
                                        last_mode,
                                        copywriting_copy_list,
                                        comment_copy_list,
                                        local_audio_path_list,
                                    )
                        else:
                            logger.debug(copywriting_copy_list)
                            if copywriting_copy_list != []:
                                copywriting_copy = copywriting_copy_list.pop(0)
                            else:
                                # Refresh the list data
                                copywriting_copy_list = load_data_list("copywriting")
                                if copywriting_copy_list != []:
                                    copywriting_copy = copywriting_copy_list.pop(0)
                                else:
                                    return (
                                        last_mode,
                                        copywriting_copy_list,
                                        comment_copy_list,
                                        local_audio_path_list,
                                    )

                        hour, min = common.get_bj_time(6)

                        if 0 <= hour and hour < 6:
                            time = f"Early morning, {hour}:{min:02d}"
                        elif 6 <= hour and hour < 9:
                            time = f"Morning, {hour}:{min:02d}"
                        elif 9 <= hour and hour < 12:
                            time = f"Morning, {hour}:{min:02d}"
                        elif hour == 12:
                            time = f"Noon, {hour}:{min:02d}"
                        elif 13 <= hour and hour < 18:
                            time = f"Afternoon, {hour}:{min:02d}"
                        elif 18 <= hour and hour < 20:
                            time = f"Evening, {hour}:{min:02d}"
                        elif 20 <= hour and hour < 24:
                            time = f"Night, {hour}:{min:02d}"

                        # Dynamic variable replacement
                        # Assume there are multiple unknown variables; users can define dynamic variables here
                        variables = {
                            "time": time,
                            "user_num": "N",
                            "last_username": my_global.last_username_list[-1],
                        }

                        # Special handling for platforms with user data
                        if platform in ["dy", "tiktok"]:
                            variables["user_num"] = my_global.last_liveroom_data[
                                "OnlineUserCount"
                            ]

                        # Use a dictionary for string replacement
                        if any(var in copywriting_copy for var in variables):
                            copywriting_copy = copywriting_copy.format(
                                **{
                                    var: value
                                    for var, value in variables.items()
                                    if var in copywriting_copy
                                }
                            )

                        # [1|2]Bracket syntax randomly picks a value and returns the string after the value is substituted
                        copywriting_copy = common.brackets_text_randomize(
                            copywriting_copy
                        )

                        # Send to the handler function
                        data = {
                            "platform": platform,
                            "username": "Idle task - script mode",
                            "type": "reread",
                            "content": copywriting_copy,
                        }

                        my_handle.process_data(data, "idle_time_task")

                        # Mode switch
                        last_mode = 1

                        overflow_time = random.randint(
                            overflow_time_min, overflow_time_max
                        )
                        logger.info(f"The next idle task will run in {overflow_time} seconds")

                        return (
                            last_mode,
                            copywriting_copy_list,
                            comment_copy_list,
                            local_audio_path_list,
                        )
                else:
                    last_mode = 1

                if config.get("idle_time_task", "comment", "enable"):
                    if last_mode == 1:
                        # Whether random trigger is enabled
                        if config.get("idle_time_task", "comment", "random"):
                            logger.debug("Switch to danmaku-triggered LLM mode")
                            if comment_copy_list != []:
                                # Randomly shuffle the elements in the list
                                random.shuffle(comment_copy_list)
                                comment_copy = comment_copy_list.pop(0)
                            else:
                                # Refresh the list data
                                comment_copy_list = load_data_list("comment")
                                # Randomly shuffle the elements in the list
                                random.shuffle(comment_copy_list)
                                comment_copy = comment_copy_list.pop(0)
                        else:
                            if comment_copy_list != []:
                                comment_copy = comment_copy_list.pop(0)
                            else:
                                # Refresh the list data
                                comment_copy_list = load_data_list("comment")
                                comment_copy = comment_copy_list.pop(0)

                        hour, min = common.get_bj_time(6)

                        if 0 <= hour and hour < 6:
                            time = f"Early morning, {hour}:{min:02d}"
                        elif 6 <= hour and hour < 9:
                            time = f"Morning, {hour}:{min:02d}"
                        elif 9 <= hour and hour < 12:
                            time = f"Morning, {hour}:{min:02d}"
                        elif hour == 12:
                            time = f"Noon, {hour}:{min:02d}"
                        elif 13 <= hour and hour < 18:
                            time = f"Afternoon, {hour}:{min:02d}"
                        elif 18 <= hour and hour < 20:
                            time = f"Evening, {hour}:{min:02d}"
                        elif 20 <= hour and hour < 24:
                            time = f"Night, {hour}:{min:02d}"

                        # Dynamic variable replacement
                        # Assume there are multiple unknown variables; users can define dynamic variables here
                        variables = {
                            "time": time,
                            "user_num": "N",
                            "last_username": my_global.last_username_list[-1],
                        }

                        # Special handling for platforms with user data
                        if platform in ["dy", "tiktok"]:
                            variables["user_num"] = my_global.last_liveroom_data[
                                "OnlineUserCount"
                            ]

                        # Use a dictionary for string replacement
                        if any(var in comment_copy for var in variables):
                            comment_copy = comment_copy.format(
                                **{
                                    var: value
                                    for var, value in variables.items()
                                    if var in comment_copy
                                }
                            )

                        # [1|2]Bracket syntax randomly picks a value and returns the string after the value is substituted
                        comment_copy = common.brackets_text_randomize(comment_copy)

                        # Send to the handler function
                        data = {
                            "platform": platform,
                            "username": "Idle task - comment-triggered LLM mode",
                            "type": "comment",
                            "content": comment_copy,
                        }

                        my_handle.process_data(data, "idle_time_task")

                        # Mode switch
                        last_mode = 2

                        overflow_time = random.randint(
                            overflow_time_min, overflow_time_max
                        )
                        logger.info(f"The next idle task will run in {overflow_time} seconds")

                        return (
                            last_mode,
                            copywriting_copy_list,
                            comment_copy_list,
                            local_audio_path_list,
                        )
                else:
                    last_mode = 2

                if config.get("idle_time_task", "local_audio", "enable"):
                    if last_mode == 2:
                        logger.debug("Switch to local audio mode")

                        # Whether random trigger is enabled
                        if config.get("idle_time_task", "local_audio", "random"):
                            if local_audio_path_list != []:
                                # Randomly shuffle the elements in the list
                                random.shuffle(local_audio_path_list)
                                local_audio_path = local_audio_path_list.pop(0)
                            else:
                                # Refresh the list data
                                local_audio_path_list = load_data_list("local_audio")
                                # Randomly shuffle the elements in the list
                                random.shuffle(local_audio_path_list)
                                local_audio_path = local_audio_path_list.pop(0)
                        else:
                            if local_audio_path_list != []:
                                local_audio_path = local_audio_path_list.pop(0)
                            else:
                                # Refresh the list data
                                local_audio_path_list = load_data_list("local_audio")
                                local_audio_path = local_audio_path_list.pop(0)

                        # [1|2]Bracket syntax randomly picks a value and returns the string after the value is substituted
                        local_audio_path = common.brackets_text_randomize(
                            local_audio_path
                        )

                        logger.debug(f"local_audio_path={local_audio_path}")

                        # Send to the handler function
                        data = {
                            "platform": platform,
                            "username": "Idle task - local audio mode",
                            "type": "local_audio",
                            "content": common.extract_filename(local_audio_path, False),
                            "file_path": local_audio_path,
                        }

                        my_handle.process_data(data, "idle_time_task")

                        # Mode switch
                        last_mode = 0

                        overflow_time = random.randint(
                            overflow_time_min, overflow_time_max
                        )
                        logger.info(f"The next idle task will run in {overflow_time} seconds")

                        return (
                            last_mode,
                            copywriting_copy_list,
                            comment_copy_list,
                            local_audio_path_list,
                        )
                else:
                    last_mode = 0

                return (
                    last_mode,
                    copywriting_copy_list,
                    comment_copy_list,
                    local_audio_path_list,
                )

            while True:
                # If the idle time range is 0, sleep 100ms just for show
                if overflow_time_min > 0 and overflow_time_max > 0:
                    # Count idle time with a sleep every second
                    await asyncio.sleep(1)
                else:
                    await asyncio.sleep(0.1)
                my_global.global_idle_time = my_global.global_idle_time + 1

                if config.get("idle_time_task", "type") == "Idle: no room messages":
                    # The idle count reached the specified value, process the idle task
                    if my_global.global_idle_time >= overflow_time:
                        (
                            last_mode,
                            copywriting_copy_list,
                            comment_copy_list,
                            local_audio_path_list,
                        ) = do_task(
                            last_mode,
                            copywriting_copy_list,
                            comment_copy_list,
                            local_audio_path_list,
                        )
                elif config.get("idle_time_task", "type") == "Idle: message queue":
                    if my_handle.is_queue_less_or_greater_than(
                        type="message_queue",
                        less=int(
                            config.get("idle_time_task", "min_msg_queue_len_to_trigger")
                        ),
                    ):
                        (
                            last_mode,
                            copywriting_copy_list,
                            comment_copy_list,
                            local_audio_path_list,
                        ) = do_task(
                            last_mode,
                            copywriting_copy_list,
                            comment_copy_list,
                            local_audio_path_list,
                        )
                elif config.get("idle_time_task", "type") == "Idle: audio queue":
                    logger.debug(f"Number of audio clips waiting to play: {my_global.wait_play_audio_num}")
                    # Special handling: metahuman_stream platform, determinewait_play_audio_num
                    if config.get("visual_body") == "metahuman_stream":
                        if my_global.wait_play_audio_num < config.get("idle_time_task", "min_audio_queue_len_to_trigger"):
                            (
                                last_mode,
                                copywriting_copy_list,
                                comment_copy_list,
                                local_audio_path_list,
                            ) = do_task(
                                last_mode,
                                copywriting_copy_list,
                                comment_copy_list,
                                local_audio_path_list,
                            )
                    else:
                        if my_handle.is_queue_less_or_greater_than(
                            type="voice_tmp_path_queue",
                            less=int(
                                config.get(
                                    "idle_time_task", "min_audio_queue_len_to_trigger"
                                )
                            ),
                        ):
                            (
                                last_mode,
                                copywriting_copy_list,
                                comment_copy_list,
                                local_audio_path_list,
                            ) = do_task(
                                last_mode,
                                copywriting_copy_list,
                                comment_copy_list,
                                local_audio_path_list,
                            )

        except Exception as e:
            logger.error(traceback.format_exc())

    if config.get("idle_time_task", "enable"):
        # Create the idle task sub-thread and start it
        threading.Thread(target=lambda: asyncio.run(idle_time_task())).start()

    

    # Image recognition scheduled task
    def image_recognition_schedule_task(type: str):
        global config, common, my_handle

        logger.debug(f"Image recognition-{type} scheduled task running...")

        data = {"platform": platform, "username": None, "content": "", "type": type}

        logger.info(f"Image recognition-{type} scheduled task triggered")

        my_handle.process_data(data, "image_recognition_schedule")

    # Start image recognition scheduled task
    def run_image_recognition_schedule(interval: int, type: str):
        global config

        try:
            schedule.every(interval).seconds.do(
                partial(image_recognition_schedule_task, type)
            )
        except Exception as e:
            logger.error(traceback.format_exc())

        while True:
            schedule.run_pending()
            # time.sleep(1)  # Control the interval of each loop to avoid using too much CPU

    if config.get("image_recognition", "loop_screenshot_enable"):
        # Create the scheduled task sub-thread and start it
        image_recognition_schedule_thread = threading.Thread(
            target=lambda: run_image_recognition_schedule(
                config.get("image_recognition", "loop_screenshot_delay"), "Window screenshot"
            )
        )
        image_recognition_schedule_thread.start()

    if config.get("image_recognition", "loop_cam_screenshot_enable"):
        # Create the scheduled task sub-thread and start it
        image_recognition_cam_schedule_thread = threading.Thread(
            target=lambda: run_image_recognition_schedule(
                config.get("image_recognition", "loop_cam_screenshot_delay"),
                "Camera screenshot",
            )
        )
        image_recognition_cam_schedule_thread.start()

    # Special handling for the LiveTalking (metahuman-stream) integration
    if config.get("visual_body") == "metahuman_stream":
        def metahuman_stream_is_speaking():

            try:
                from urllib.parse import urljoin
                url = urljoin(
                    config.get("metahuman_stream", "api_ip_port"), "is_speaking"
                )
                resp_json = common.send_request(url, 'POST', {"sessionid": 0}, timeout=5)
                if resp_json and resp_json["code"] == 0:
                    if resp_json["data"]:
                        logger.debug("LiveTalkingAudio is playing")
                        my_global.wait_play_audio_num = 1
                    else:
                        logger.debug("LiveTalkingNo audio is playing")
                        my_global.wait_play_audio_num = 0
                        
            except Exception as e:
                logger.error(traceback.format_exc())
                logger.error("Request to the LiveTalking is_speaking endpoint failed")

        # Create a thread that periodically requests the LiveTalking is_speaking endpoint to determine whether audio is playing
        def run_metahuman_stream_is_speaking_schedule():
            interval = 3
            try:
                schedule.every(interval).seconds.do(
                    partial(metahuman_stream_is_speaking)
                )
            except Exception as e:
                logger.error(traceback.format_exc())

            while True:
                schedule.run_pending()    

        run_metahuman_stream_is_speaking_schedule_thread = threading.Thread(
            target=lambda: run_metahuman_stream_is_speaking_schedule()
        )
        run_metahuman_stream_is_speaking_schedule_thread.start()
    
    logger.info(f"Current platform: {platform}")

    # Flash-sale announcements (data/flash_sale.json is written by the web UI)
    threading.Thread(target=my_handle.flash_sale_loop, daemon=True).start()

    if platform == "tiktok":
        from utils.platforms.tiktok import start_listen

        start_listen(config, common, my_handle, platform)
    elif platform == "twitch":
        from utils.platforms.twitch import start_listen

        start_listen(config, common, my_handle, platform)
    elif platform == "youtube":
        from utils.platforms.youtube import start_listen

        start_listen(config, common, my_handle, platform)
    elif platform in ("talk",):
        thread.join()
    else:
        logger.error(f"Unsupported platform: {platform}. Supported: talk, tiktok, youtube, twitch")



# Exit the program
def exit_handler(signum, frame):
    logger.info("Signal received:", signum)


if __name__ == "__main__":
    common = Common()
    config = Config(config_path)
    # Log file path
    log_path = "./log/log-" + common.get_bj_time(1) + ".txt"
    # Configure_logger(log_path)

    platform = config.get("platform")


    # Key listener related
    do_listen_and_comment_thread = None
    stop_do_listen_and_comment_thread_event = None
    # Store the loaded model object
    faster_whisper_model = None
    sense_voice_model = None
    # Recording in progress flag
    is_recording = False
    # Whether chat is awake
    is_talk_awake = False


    # Special signal handling
    signal.signal(signal.SIGINT, exit_handler)
    signal.signal(signal.SIGTERM, exit_handler)

    start_server()
