import os, sys, threading, json, random, time
import difflib
from datetime import datetime
import traceback
import importlib
import asyncio

import copy
import re
from functools import partial


from .config import Config
from .common import Common
from .audio import Audio
from .gpt_model.gpt import GPT_MODEL
from .my_log import logger
from .db import SQLiteDB
from .my_translate import My_Translate

from .luoxi_project.live_comment_assistant import send_msg_to_live_comment_assistant
from . import tiktok_safety, product_catalog, live_analytics, flash_sale, engage, coverage, lang_guard, answer_cache


"""
	___ _                       
	|_ _| | ____ _ _ __ ___  ___ 
	 | || |/ / _` | '__/ _ \/ __|
	 | ||   < (_| | | | (_) \__ \
	|___|_|\_\__,_|_|  \___/|___/

"""
class SingletonMeta(type):
    _instances = {}
    _lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        with cls._lock:
            if cls not in cls._instances:
                cls._instances[cls] = super(SingletonMeta, cls).__call__(*args, **kwargs)
            return cls._instances[cls]


class My_handle(metaclass=SingletonMeta):
    common = None
    config = None
    audio = None
    my_translate = None
    
    # Whether data is being processed
    is_handleing = 0

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

    # Live message storage (entrance, gift, danmaku), used for deduplication within the specified time
    live_data = {
        "comment": [],
        "gift": [],
        "entrance": [],
    }

    # Per-task running data cache, currently used to limit periodic triggering of tasks
    task_data = {
        "read_comment": {
            "data": [],
            "time": 0
        },
        "local_qa": {
            "data": [],
            "time": 0
        },
        "thanks": {
            "gift": {
                "data": [],
                "time": 0
            },
            "entrance": {
                "data": [],
                "time": 0
            },
            "follow": {
                "data": [],
                "time": 0
            },
        }
    }

    # Temporary storage of copywriting data for the thanks section
    thanks_entrance_copy = []
    thanks_gift_copy = []
    thanks_follow_copy = []

    def __init__(self, config_path):
        logger.info("InitializeMy_handle...")

        try:
            if My_handle.common is None:
                My_handle.common = Common()
            if My_handle.config is None:
                My_handle.config = Config(config_path)
            if My_handle.audio is None:
                My_handle.audio = Audio(config_path)
            if My_handle.my_translate is None:
                My_handle.my_translate = My_Translate(config_path)

            self.proxy = None
            # self.proxy = {
            #     "http": "http://127.0.0.1:10809",
            #     "https": "http://127.0.0.1:10809"
            # }
            
            # Implementation related to the data discard part
            self.data_lock = threading.Lock()
            self.timers = {}

            self.db = None

            # Set the initial session value
            self.session_config = None
            self.sessions = {}
            self.current_key_index = 0

            # Song request module
            self.choose_song_song_lists = None

            """
            After adding a new LLM, define the variables here first; they are used below
            """
            self.chatgpt = None
            self.chat_with_file = None
            self.text_generation_webui = None
            self.sparkdesk = None
            self.langchain_chatchat = None
            self.zhipu = None
            self.bard_api = None
            self.tongyi = None
            self.tongyixingchen = None
            self.my_wenxinworkshop = None
            self.gemini = None
            self.koboldcpp = None
            self.anythingllm = None
            self.gpt4free = None
            self.custom_llm = None
            self.llm_tpu = None
            self.dify = None
            self.volcengine = None

            self.image_recognition_model = None

            self.chat_type_list = ["chatgpt", "chat_with_file", "text_generation_webui", \
                    "sparkdesk",  "langchain_chatchat", "zhipu", "bard", "tongyi", \
                    "tongyixingchen", "my_wenxinworkshop", "gemini", "koboldcpp", "anythingllm", "gpt4free", \
                    "custom_llm", "llm_tpu", "dify", "volcengine"]

            # Config loading
            self.config_load()

            logger.info(f"Config data loaded successfully.")

            # Start the timer
            self.start_timers()
        except Exception as e:
            logger.error(traceback.format_exc())     

    # Clear the waiting-to-synthesize message queue | to-play audio queue
    def clear_queue(self, type: str="message_queue"):
        """Clear the waiting-to-synthesize message queue | to-play audio queue

        Args:
            type (str, optional): Queue type. Defaults to "message_queue".

        Returns:
            bool: Clear the result
        """
        try:
            return My_handle.audio.clear_queue(type)
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(f"Failed to clear the {type} queue: {e}")
            return False
        
    # Stop audio playback
    def stop_audio(self, type: str="pygame", mixer_normal: bool=True, mixer_copywriting: bool=True):
        try:
            return My_handle.audio.stop_audio(type, mixer_normal, mixer_copywriting)
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(f"Failed to stop audio playback: {e}")
            return False

    # Periodic trigger data handling, executed once per second for timing
    def periodic_trigger_data_handle(self):
        def get_last_n_items(data_list: list, num: int):
            # Return the last n elements; if there are fewer than n, return the actual number of elements
            return data_list[-num:] if num > 0 else []
        
        
        if My_handle.config.get("read_comment", "periodic_trigger", "enable"):
            type = "read_comment"
            # Timing+1
            My_handle.task_data[type]["time"] += 1
            
            periodic_time_min = int(My_handle.config.get(type, "periodic_trigger", "periodic_time_min"))
            periodic_time_max = int(My_handle.config.get(type, "periodic_trigger", "periodic_time_max"))
            # Generate the trigger period value
            periodic_time = random.randint(periodic_time_min, periodic_time_max)
            logger.debug(f"type={type}, periodic_time={periodic_time}, My_handle.task_data={My_handle.task_data}")

            # Whether the timed duration exceeds the configured trigger period
            if My_handle.task_data[type]["time"] >= periodic_time:
                # Reset timer
                My_handle.task_data[type]["time"] = 0

                trigger_num_min = int(My_handle.config.get(type, "periodic_trigger", "trigger_num_min"))
                trigger_num_max = int(My_handle.config.get(type, "periodic_trigger", "trigger_num_max"))
                # Generate the trigger count
                trigger_num = random.randint(trigger_num_min, trigger_num_max)
                # Get data
                data_list = get_last_n_items(My_handle.task_data[type]["data"], trigger_num)
                logger.debug(f"type={type}, trigger_num={trigger_num}")

                if data_list != []:
                    # Iterate over the data to send it back to the webui and synthesize and play audio
                    for data in data_list:
                        self.audio_synthesis_handle(data)

                # Clear data
                My_handle.task_data[type]["data"] = []
        

        if My_handle.config.get("local_qa", "periodic_trigger", "enable"):
            type = "local_qa"
            # Timing+1
            My_handle.task_data[type]["time"] += 1
            
            periodic_time_min = int(My_handle.config.get(type, "periodic_trigger", "periodic_time_min"))
            periodic_time_max = int(My_handle.config.get(type, "periodic_trigger", "periodic_time_max"))
            # Generate the trigger period value
            periodic_time = random.randint(periodic_time_min, periodic_time_max)
            logger.debug(f"type={type}, periodic_time={periodic_time}, My_handle.task_data={My_handle.task_data}")

            # Whether the timed duration exceeds the configured trigger period
            if My_handle.task_data[type]["time"] >= periodic_time:
                # Reset timer
                My_handle.task_data[type]["time"] = 0

                trigger_num_min = int(My_handle.config.get(type, "periodic_trigger", "trigger_num_min"))
                trigger_num_max = int(My_handle.config.get(type, "periodic_trigger", "trigger_num_max"))
                # Generate the trigger count
                trigger_num = random.randint(trigger_num_min, trigger_num_max)
                # Get data
                data_list = get_last_n_items(My_handle.task_data[type]["data"], trigger_num)
                logger.debug(f"type={type}, trigger_num={trigger_num}")

                if data_list != []:
                    # Iterate over the data to send it back to the webui and synthesize and play audio
                    for data in data_list:
                        if data["type"] == "local_qa_audio":
                            self.webui_show_chat_log_callback("Local Q&A - Audio", data, data["file_path"])
                        else:
                            self.webui_show_chat_log_callback("Local Q&A - Text", data, data["content"])

                        self.audio_synthesis_handle(data)

                # Clear data
                My_handle.task_data[type]["data"] = []
        
        if My_handle.config.get("thanks", "gift", "periodic_trigger", "enable"):
            type = "thanks"
            type2 = "gift"

            # Timing+1
            My_handle.task_data[type][type2]["time"] += 1

            periodic_time_min = int(My_handle.config.get(type, type2, "periodic_trigger", "periodic_time_min"))
            periodic_time_max = int(My_handle.config.get(type, type2, "periodic_trigger", "periodic_time_max"))
            # Generate the trigger period value
            periodic_time = random.randint(periodic_time_min, periodic_time_max)
            logger.debug(f"type={type}, periodic_time={periodic_time}, My_handle.task_data={My_handle.task_data}")

            # Whether the timed duration exceeds the configured trigger period
            if My_handle.task_data[type][type2]["time"] >= periodic_time:
                # Reset timer
                My_handle.task_data[type][type2]["time"] = 0

                trigger_num_min = int(My_handle.config.get(type, type2, "periodic_trigger", "trigger_num_min"))
                trigger_num_max = int(My_handle.config.get(type, type2, "periodic_trigger", "trigger_num_max"))
                # Generate the trigger count
                trigger_num = random.randint(trigger_num_min, trigger_num_max)
                # Get data
                data_list = get_last_n_items(My_handle.task_data[type][type2]["data"], trigger_num)
                logger.debug(f"type={type}, trigger_num={trigger_num}")

                if data_list != []:
                    # Iterate over the data to send it back to the webui and synthesize and play audio
                    for data in data_list:
                        self.audio_synthesis_handle(data)

                # Clear data
                My_handle.task_data[type][type2]["data"] = []
        
        if My_handle.config.get("thanks", "entrance", "periodic_trigger", "enable"):
            type = "thanks"
            type2 = "entrance"

            # Timing+1
            My_handle.task_data[type][type2]["time"] += 1

            periodic_time_min = int(My_handle.config.get(type, type2, "periodic_trigger", "periodic_time_min"))
            periodic_time_max = int(My_handle.config.get(type, type2, "periodic_trigger", "periodic_time_max"))
            # Generate the trigger period value
            periodic_time = random.randint(periodic_time_min, periodic_time_max)
            logger.debug(f"type={type}, periodic_time={periodic_time}, My_handle.task_data={My_handle.task_data}")

            # Whether the timed duration exceeds the configured trigger period
            if My_handle.task_data[type][type2]["time"] >= periodic_time:
                # Reset timer
                My_handle.task_data[type][type2]["time"] = 0

                trigger_num_min = int(My_handle.config.get(type, type2, "periodic_trigger", "trigger_num_min"))
                trigger_num_max = int(My_handle.config.get(type, type2, "periodic_trigger", "trigger_num_max"))
                # Generate the trigger count
                trigger_num = random.randint(trigger_num_min, trigger_num_max)
                # Get data
                data_list = get_last_n_items(My_handle.task_data[type][type2]["data"], trigger_num)
                logger.debug(f"type={type}, trigger_num={trigger_num}")

                if data_list != []:
                    # Iterate over the data to send it back to the webui and synthesize and play audio
                    for data in data_list:
                        self.audio_synthesis_handle(data)

                # Clear data
                My_handle.task_data[type][type2]["data"] = []

        if My_handle.config.get("thanks", "follow", "periodic_trigger", "enable"):
            type = "thanks"
            type2 = "follow"

            # Timing+1
            My_handle.task_data[type][type2]["time"] += 1

            periodic_time_min = int(My_handle.config.get(type, type2, "periodic_trigger", "periodic_time_min"))
            periodic_time_max = int(My_handle.config.get(type, type2, "periodic_trigger", "periodic_time_max"))
            # Generate the trigger period value
            periodic_time = random.randint(periodic_time_min, periodic_time_max)
            logger.debug(f"type={type}, periodic_time={periodic_time}, My_handle.task_data={My_handle.task_data}")

            # Whether the timed duration exceeds the configured trigger period
            if My_handle.task_data[type][type2]["time"] >= periodic_time:
                # Reset timer
                My_handle.task_data[type][type2]["time"] = 0

                trigger_num_min = int(My_handle.config.get(type, type2, "periodic_trigger", "trigger_num_min"))
                trigger_num_max = int(My_handle.config.get(type, type2, "periodic_trigger", "trigger_num_max"))
                # Generate the trigger count
                trigger_num = random.randint(trigger_num_min, trigger_num_max)
                # Get data
                data_list = get_last_n_items(My_handle.task_data[type][type2]["data"], trigger_num)
                logger.debug(f"type={type}, trigger_num={trigger_num}")

                if data_list != []:
                    # Iterate over the data to send it back to the webui and synthesize and play audio
                    for data in data_list:
                        self.audio_synthesis_handle(data)

                # Clear data
                My_handle.task_data[type][type2]["data"] = []


        self.periodic_trigger_timer = threading.Timer(1, partial(self.periodic_trigger_data_handle))
        self.periodic_trigger_timer.start()

    # Clear the live_data live stream data
    def clear_live_data(self, type: str=""):
        if type != "" and type is not None:
            My_handle.live_data[type] = []

        if type == "comment":
            self.comment_check_timer = threading.Timer(int(My_handle.config.get("filter", "limited_time_deduplication", "comment")), partial(self.clear_live_data, "comment"))
            self.comment_check_timer.start()
        elif type == "gift":
            self.gift_check_timer = threading.Timer(int(My_handle.config.get("filter", "limited_time_deduplication", "gift")), partial(self.clear_live_data, "gift"))
            self.gift_check_timer.start()
        elif type == "entrance":
            self.entrance_check_timer = threading.Timer(int(My_handle.config.get("filter", "limited_time_deduplication", "entrance")), partial(self.clear_live_data, "entrance"))
            self.entrance_check_timer.start()

    # Start the timer
    def start_timers(self):
        
        if My_handle.config.get("filter", "limited_time_deduplication", "enable"):

            # Set a timer that runs every n seconds
            self.comment_check_timer = threading.Timer(int(My_handle.config.get("filter", "limited_time_deduplication", "comment")), partial(self.clear_live_data, "comment"))
            self.comment_check_timer.start()

            self.gift_check_timer = threading.Timer(int(My_handle.config.get("filter", "limited_time_deduplication", "gift")), partial(self.clear_live_data, "gift"))
            self.gift_check_timer.start()

            self.entrance_check_timer = threading.Timer(int(My_handle.config.get("filter", "limited_time_deduplication", "entrance")), partial(self.clear_live_data, "entrance"))
            self.entrance_check_timer.start()

            logger.info("Start the live data deduplication timer for the specified time period")

        self.periodic_trigger_timer = threading.Timer(1, partial(self.periodic_trigger_data_handle))
        self.periodic_trigger_timer.start()
        logger.info("Start the periodic trigger timer")


    # Whether it is in the data processing state
    def is_handle_empty(self):
        return My_handle.is_handleing


    # Audio queue and playback status
    def is_audio_queue_empty(self):
        return My_handle.audio.is_audio_queue_empty()

    # Check whether the number of the waiting-to-synthesize message queue | to-play audio queue is less or greater than some value, and returnTrue
    def is_queue_less_or_greater_than(self, type: str="message_queue", less: int=None, greater: int=None):
        """Check whether the count of the waiting-for-synthesis message queue or the audio-to-play queue is less than or greater than a certain value

        Args:
            type (str, optional): _description_. Defaults to "message_queue" | voice_tmp_path_queue.
            less (int, optional): _description_. Defaults to None.
            greater (int, optional): _description_. Defaults to None.

        Returns:
            bool: Whether it is less than or greater than a certain value
        """
        return My_handle.audio.is_queue_less_or_greater_than(type, less, greater)

    # Get audio class info
    def get_audio_info(self):
        return My_handle.audio.get_audio_info()

    def get_chat_model(self, chat_type, config):
        if chat_type in ["chatterbot", "chat_with_file"]:
            # Special handling for these types
            pass
        else:
            GPT_MODEL.set_model_config(chat_type, config.get(chat_type))
        self.__dict__[chat_type] = GPT_MODEL.get(chat_type)

    def get_vision_model(self, chat_type, config):
        GPT_MODEL.set_vision_model_config(chat_type, config)
        self.image_recognition_model = GPT_MODEL.get(chat_type)

    def handle_chat_type(self):
        chat_type = My_handle.config.get("chat_type")
        self.get_chat_model(chat_type, My_handle.config)

        if chat_type == "chatterbot":
            from chatterbot import ChatBot
            self.chatterbot_config = My_handle.config.get("chatterbot")
            try:
                self.bot = ChatBot(
                    self.chatterbot_config["name"],
                    database_uri='sqlite:///' + self.chatterbot_config["db_path"]
                )
            except Exception as e:
                logger.info(e)
                exit(0)
        elif chat_type == "chat_with_file":
            from utils.chat_with_file.chat_with_file import Chat_with_file
            self.chat_with_file = Chat_with_file(My_handle.config.get("chat_with_file"))
        elif chat_type == "game":
            self.game = importlib.import_module("game." + My_handle.config.get("game", "module_name"))

    # Config loading
    def config_load(self):
        self.session_config = {'msg': [{"role": "system", "content": My_handle.config.get('chatgpt', 'preset')}]}

        # Set the GPT_Model global model list
        GPT_MODEL.set_model_config("openai", My_handle.config.get("openai"))
        GPT_MODEL.set_model_config("chatgpt", My_handle.config.get("chatgpt"))

        # Instantiate chat-related classes
        self.handle_chat_type()

        # Check whether it is enabledSD
        if My_handle.config.get("sd")["enable"]:
            from utils.sd import SD

            self.sd = SD(My_handle.config.get("sd"))
        # Special: when SD is not enabled, check whether the image mapping is enabled
        elif My_handle.config.get("key_mapping", "img_path_trigger_type") != "Disabled":
            # Reuse the SD virtual camera to display the image
            from utils.sd import SD

            self.sd = SD({"enable": False, "visual_camera": My_handle.config.get("sd", "visual_camera")})

        # Log file path
        self.log_file_path = "./log/log-" + My_handle.common.get_bj_time(1) + ".txt"
        if os.path.isfile(self.log_file_path):
            logger.info(f'{self.log_file_path} Log file already exists, skipping')
        else:
            with open(self.log_file_path, 'w') as f:
                f.write('')
                logger.info(f'{self.log_file_path} Log file created')

        # Generate the danmaku file
        self.comment_file_path = "./log/comment-" + My_handle.common.get_bj_time(1) + ".txt"
        if os.path.isfile(self.comment_file_path):
            logger.info(f'{self.comment_file_path} Danmaku file already exists, skipping')
        else:
            with open(self.comment_file_path, 'w') as f:
                f.write('')
                logger.info(f'{self.comment_file_path} Danmaku file created')

        """                                                                                                                
                                                                                                                                        
            .............  '>)xcn)I                                                                                 
            }}}}}}}}}}}}](v0kaaakad\..                                                                              
            ++++++~~++<_xpahhhZ0phah>                                                                               
            _________+(OhhkamuCbkkkh+                                                                               
            ?????????nbhkhkn|makkkhQ^                                                                               
            [[[[[[[}UhkbhZ]fbhkkkhb<                                                                                
            1{1{1{1ChkkaXicohkkkhk]                                                                                 
            ))))))JhkkhrICakkkkap-                                                                                  
            \\\\|ckkkat;0akkkka0>                                                                                   
            ttt/fpkka/;Oakhhaku"                                                                                    
            jjjjUmkau^QabwQX\< '!<++~>iI       .;>++++<>I'     :+}}{?;                                              
            xxxcpdkO"capmmZ/^ +Y-;,,;-Lf     ItX/+l:",;>1cx>  .`"x#d>`        .`.                                   
            uuvqwkh+1ahaaL_  'Zq;     ;~   '/bQ!         "uhc: . 1oZ'         "vj.     ^'                           
            ccc0kaz!kawX}'   .\hbv?:      .jop;           .C*L^  )oO`        .':I^. ."_L!^^.    ':;,'               
            XXXXph_cU_"        >rZhbC\!   "qaC...          faa~  )oO`        ;-jqj .l[mb1]_'  ^(|}\Ow{              
            XXXz00i+             '!1Ukkc, 'JoZ` .          uop;  )oO'          >ou   .Lp"  . ,0j^^>Yvi              
            XXXzLn. .        ^>      lC#(  lLot.          _kq- . 1o0'          >on   .Qp,    }*|><i^  .             
            YYYXQ|           ,O]^.   "XQI . `10c~^.    '!t0f:   .t*q;....'l1. ._#c.. .Qkl`I_"Iw0~"`,<|i.            
            (|((f1           ^t1]++-}(?`      '>}}}/rrx1]~^    ^?jvv/]--]{r) .i{x/+;  ]Xr1_;. :(vnrj\i.             
                '1..             .''.   .         .Itq*Z}`             ..                                           
                 +; .                                "}XmQf-i!;.                                                    
                  .                                     ';><iI"                                                     
                                                                                                                                        
                                                                                                                                                                                                                                                     
        """
        try:
            # Database
            self.db = SQLiteDB(My_handle.config.get("database", "path"))
            logger.info(f'Create the database:{My_handle.config.get("database", "path")}')

            # Create the danmaku table
            create_table_sql = '''
            CREATE TABLE IF NOT EXISTS danmu (
                username TEXT NOT NULL,
                content TEXT NOT NULL,
                ts DATETIME NOT NULL
            )
            '''
            self.db.execute(create_table_sql)
            logger.debug('Create the danmu (danmaku) table')

            create_table_sql = '''
            CREATE TABLE IF NOT EXISTS entrance (
                username TEXT NOT NULL,
                ts DATETIME NOT NULL
            )
            '''
            self.db.execute(create_table_sql)
            logger.debug('Create the entrance table')

            create_table_sql = '''
            CREATE TABLE IF NOT EXISTS gift (
                username TEXT NOT NULL,
                gift_name TEXT NOT NULL,
                gift_num INT NOT NULL,
                unit_price REAL NOT NULL,
                total_price REAL NOT NULL,
                ts DATETIME NOT NULL
            )
            '''
            self.db.execute(create_table_sql)
            logger.debug('Create the gift table')

            create_table_sql = '''
            CREATE TABLE IF NOT EXISTS integral (
                platform TEXT NOT NULL,
                username TEXT NOT NULL,
                uid TEXT NOT NULL,
                integral INT NOT NULL,
                view_num INT NOT NULL,
                sign_num INT NOT NULL,
                last_sign_ts DATETIME NOT NULL,
                total_price INT NOT NULL,
                last_ts DATETIME NOT NULL
            )
            '''
            self.db.execute(create_table_sql)
            logger.debug('Create the integral (points) table')
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(f'Database {My_handle.config.get("database", "path")} Creation failed, please check the logs to troubleshoot!!!')


    # Reloadconfig
    def reload_config(self, config_path):
        My_handle.config = Config(config_path)
        My_handle.audio.reload_config(config_path)
        My_handle.my_translate.reload_config(config_path)

        self.config_load()


    # Send back to the webui for chat content display
    def webui_show_chat_log_callback(self, data_type: str, data: dict, resp_content: str):
        """Send back to the webui for chat content display

        Args:
            data_type (str): Type of data content (mostly referring to the LLM)
            data (dict): DataJSON
            resp_content (str): Text of the displayed chat content
        """
        try:
            if My_handle.config.get("talk", "show_chat_log") == True: 
                if "ori_username" not in data:
                    data["ori_username"] = data["username"]
                if "ori_content" not in data:
                    data["ori_content"] = data["content"]
                    
                # Data returned to the webui
                return_webui_json = {
                    "type": "llm",
                    "data": {
                        "type": data_type,
                        "username": data["ori_username"], 
                        "content_type": "answer",
                        "content": f"Error: no response from {data_type}, check the logs" if resp_content is None else resp_content,
                        "timestamp": My_handle.common.get_bj_time(0)
                    }
                }

                webui_ip = "127.0.0.1" if My_handle.config.get("webui", "ip") == "0.0.0.0" else My_handle.config.get("webui", "ip")
                tmp_json = My_handle.common.send_request(f'http://{webui_ip}:{My_handle.config.get("webui", "port")}/callback', "POST", return_webui_json, timeout=30)
        except Exception as e:
            logger.error(traceback.format_exc())

    # Get the room number
    def get_room_id(self):
        return My_handle.config.get("room_display_id")


    # Audio synthesis handling
    def audio_synthesis_handle(self, data_json):
        """Audio synthesis handling

        Args:
            data_json (dict): Passed JSON data

            Core parameters:
            typeCurrently there are
                reread_top_priority Highest priority - repeat
                talk Chat (voice input)
                comment Danmaku
                local_qa_text Local Q&A text
                local_qa_audio Local Q&A audio
                song Song
                reread Repeat
                key_mapping Key mapping
                key_mapping_copywriting Key mapping - copywriting
                integral Points
                read_comment Read danmaku
                gift Gift
                entrance User entered
                follow User followed
                schedule Scheduled task
                idle_time_task Idle task
                abnormal_alarm Exception alert
                image_recognition_schedule Image recognition scheduled task

        """

        if "content" in data_json:
            if data_json['content']:
                # Replace \n in the text content with empty
                data_json['content'] = data_json['content'].replace('\n', '')

        # If the virtual body is Unity, send data to the relay station
        if My_handle.config.get("visual_body") == "unity":
            # Determine 'config' Whether it exists in the dict
            if 'config' in data_json:
                # Delete 'config' Corresponding key-value pair
                data_json.pop('config')

            data_json["password"] = My_handle.config.get("unity", "password")

            resp_json = My_handle.common.send_request(My_handle.config.get("unity", "api_ip_port"), "POST", data_json)
            if resp_json:
                if resp_json["code"] == 200:
                    logger.info("Successfully requested the unity relay station")
                else:
                    logger.info(f"Error requesting the unity relay station,{resp_json['message']}")
            else:
                logger.error("Failed to request the unity relay station")
        else:
            # Audio synthesis (edge-tts / vits_fast) and playback
            My_handle.audio.audio_synthesis(data_json)

            logger.debug(f'data_json={data_json}')

            # If the data type is not within the range that requires the assistant to trigger, return directly
            if data_json["type"] not in My_handle.config.get("assistant_anchor", "type"):
                return

            # 1, match the assistant local Q&A library; after it triggers, other later features are not executed
            if My_handle.config.get("assistant_anchor", "local_qa", "text", "enable"):
                # Run different Q&A matching algorithms depending on the type
                if My_handle.config.get("assistant_anchor", "local_qa", "text", "format") == "text":
                    tmp = self.find_answer(data_json["content"], My_handle.config.get("assistant_anchor", "local_qa", "text", "file_path"), My_handle.config.get("assistant_anchor", "local_qa", "text", "similarity"))
                else:
                    tmp = self.find_similar_answer(data_json["content"], My_handle.config.get("assistant_anchor", "local_qa", "text", "file_path"), My_handle.config.get("assistant_anchor", "local_qa", "text", "similarity"))

                if tmp is not None:
                    logger.info(f'Trigger assistant local Q&A library - text [{My_handle.config.get("assistant_anchor", "username")}]: {data_json["content"]}')
                    # Replace the parameters set in the Q&A library with the specified content; developers can customize the replacement content
                    # Assume there are multiple unknown variables; users can define dynamic variables here
                    variables = {
                        'cur_time': My_handle.common.get_bj_time(5),
                        'username': My_handle.config.get("assistant_anchor", "username")
                    }

                    # Use a dictionary for string replacement
                    if any(var in tmp for var in variables):
                        tmp = tmp.format(**{var: value for var, value in variables.items() if var in tmp})

                    # [1|2]Bracket syntax randomly picks a value and returns the string after the value is substituted
                    tmp = My_handle.common.brackets_text_randomize(tmp)
                    
                    logger.info(f"Assistant local Q&A library - text answer is: {tmp}")

                    resp_content = tmp
                    # Record the AI reply in the log file
                    self.write_to_comment_log(resp_content, {"username": My_handle.config.get("assistant_anchor", "username"), "content": data_json["content"]})
                    
                    message = {
                        "type": "assistant_anchor_text",
                        "tts_type": My_handle.config.get("assistant_anchor", "audio_synthesis_type"),
                        "data": My_handle.config.get(My_handle.config.get("assistant_anchor", "audio_synthesis_type")),
                        "config": My_handle.config.get("filter"),
                        "username": My_handle.config.get("assistant_anchor", "username"),
                        "content": resp_content
                    }

                    if "insert_index" in message:
                        message["insert_index"] = data_json["insert_index"]

                    
                    My_handle.audio.audio_synthesis(message)

                    return True
                
            # If the assistant feature is enabled, play the assistant audio based on the text of the content currently being played
            if My_handle.config.get("assistant_anchor", "enable"):
                # 2, match the local Q&A audio library; after it triggers, other later features are not executed
                if My_handle.config.get("assistant_anchor", "local_qa", "audio", "enable"):
                    # Output the danmaku message sent by the current user
                    # logger.info(f"[{username}]: {content}")
                    # Get all audio file names in the local Q&A audio library folder
                    local_qa_audio_filename_list = My_handle.audio.get_dir_audios_filename(My_handle.config.get("assistant_anchor", "local_qa", "audio", "file_path"), type=1)
                    local_qa_audio_list = My_handle.audio.get_dir_audios_filename(My_handle.config.get("assistant_anchor", "local_qa", "audio", "file_path"), type=0)

                    if My_handle.config.get("assistant_anchor", "local_qa", "audio", "type") == "Similarity match":
                        # Search in the local audio name list without the file extension
                        local_qv_audio_filename = My_handle.common.find_best_match(data_json["content"], local_qa_audio_filename_list, My_handle.config.get("assistant_anchor", "local_qa", "audio", "similarity"))
                    elif My_handle.config.get("assistant_anchor", "local_qa", "audio", "type") == "Contains":
                        # Search the local audio name list to see whether it is contained in the current input text
                        local_qv_audio_filename = My_handle.common.find_substring_in_list(data_json["content"], local_qa_audio_filename_list)

                    # print(f"local_qv_audio_filename={local_qv_audio_filename}")

                    # Found a matching result
                    if local_qv_audio_filename is not None:
                        logger.info(f'Trigger assistant local Q&A library - voice [{My_handle.config.get("assistant_anchor", "username")}]: {data_json["content"]}')
                        # Look the result up again in the original file name list and add the extension back. With the similarity set to 0, a result is always returned
                        local_qv_audio_filename = My_handle.common.find_best_match(local_qv_audio_filename, local_qa_audio_list, 0)

                        # Find the corresponding file
                        resp_content = My_handle.audio.search_files(My_handle.config.get("assistant_anchor", "local_qa", "audio", "file_path"), local_qv_audio_filename)
                        if resp_content != []:
                            logger.debug(f"Original relative path of the matched audio:{resp_content[0]}")

                            # Concatenate the audio file path
                            resp_content = f'{My_handle.config.get("assistant_anchor", "local_qa", "audio", "file_path")}/{resp_content[0]}'
                            logger.info(f"Matched audio path:{resp_content}")
                            message = {
                                "type": "assistant_anchor_audio",
                                "tts_type": My_handle.config.get("assistant_anchor", "audio_synthesis_type"),
                                "data": My_handle.config.get(My_handle.config.get("assistant_anchor", "audio_synthesis_type")),
                                "config": My_handle.config.get("filter"),
                                "username": My_handle.config.get("assistant_anchor", "username"),
                                "content": data_json["content"],
                                "file_path": resp_content
                            }

                            if "insert_index" in message:
                                message["insert_index"] = data_json["insert_index"]

                            My_handle.audio.audio_synthesis(message)

                            return True


    # Search for the answer to a question in the local Q&A library (the text data is in a single-line question-and-answer format)
    def find_answer(self, question, qa_file_path, similarity=1):
        """Search for the answer to a question in the local Q&A library (the text data is in a single-line question-and-answer format)

        Args:
            question (str): Question text
            qa_file_path (str): Path of the Q&A library
            similarity (float): Similarity

        Returns:
            str: Answer text or None
        """

        with open(qa_file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        q_list = [lines[i].strip() for i in range(0, len(lines), 2)]
        q_to_answer_index = {q: i + 1 for i, q in enumerate(q_list)}

        q = My_handle.common.find_best_match(question, q_list, similarity)
        # print(f"q={q}")

        if q is not None:
            answer_index = q_to_answer_index.get(q)
            # print(f"answer_index={answer_index}")
            if answer_index is not None and answer_index < len(lines):
                return lines[answer_index * 2 - 1].strip()

        return None


    # Local Q&A library text mode: find answers by similarity (the text data is in JSON format)
    def find_similar_answer(self, input_str, qa_file_path, min_similarity=0.8):
        """Local Q&A library text mode: find answers by similarity (the text data is in JSON format)

        Args:
            input_str (str): Input string to search for
            qa_file_path (str): Path of the Q&A library
            min_similarity (float, optional): Minimum matching similarity. Default 0.8.

        Returns:
            response (str): Matched result; return if there is no matchNone
        """
        def load_data_from_file(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    return data
            except json.JSONDecodeError:
                logger.error(traceback.format_exc())
                logger.error(f"Local Q&A library text mode, JSON file: {file_path}, failed to load, the file has a JSON format error, please fix it to match the format!")
                return None
            except FileNotFoundError:
                logger.error(traceback.format_exc())
                logger.error(f"Local Q&A library text mode, JSON file: {file_path} does not exist!")
                return None
            
        # Load data from a file
        data = load_data_from_file(qa_file_path)
        if data is None:
            return None

        # List of tuples storing similarity and answer
        similarity_responses = []
        
        # Iterate over each entry in the json to find keywords similar to the input string
        for entry in data:
            for keyword in entry.get("Keywords", []):
                similarity = difflib.SequenceMatcher(None, input_str, keyword).ratio()
                similarity_responses.append((similarity, entry.get("Answer", [])))
        
        # Filter out answers whose similarity is below the set threshold
        similarity_responses = [(similarity, response) for similarity, response in similarity_responses if similarity >= min_similarity]
        
        # If there is no qualifying answer, returnNone
        if not similarity_responses:
            return None
        
        # Sort by similarity in descending order
        similarity_responses.sort(reverse=True, key=lambda x: x[0])
        
        # Get the list of answers with the highest similarity
        top_response = similarity_responses[0][1]
        
        # Randomly select an answer
        response = random.choice(top_response)
        
        return response


    # Local Q&A library handling
    def local_qa_handle(self, data):
        """Local Q&A library handling

        Args:
            data (dict): Username danmaku data

        Returns:
            bool: Whether triggered and handled
        """
        username = data["username"]
        content = data["content"]

        # Merge consecutive * at the end of the string, mainly for cases where the username cannot be obtained
        username = My_handle.common.merge_consecutive_asterisks(username)

        # Maximum retained username length
        username = username[:self.config.get("local_qa", "text", "username_max_len")]

        # 1, match the local Q&A library; after it triggers, other later features are not executed
        if My_handle.config.get("local_qa", "text", "enable"):
            # Run different Q&A matching algorithms depending on the type
            if My_handle.config.get("local_qa", "text", "type") == "text":
                tmp = self.find_answer(content, My_handle.config.get("local_qa", "text", "file_path"), My_handle.config.get("local_qa", "text", "similarity"))
            else:
                tmp = self.find_similar_answer(content, My_handle.config.get("local_qa", "text", "file_path"), My_handle.config.get("local_qa", "text", "similarity"))

            if tmp is not None:
                logger.info(f"Trigger local Q&A library - text [{username}]: {content}")
                # Replace the parameters set in the Q&A library with the specified content; developers can customize the replacement content
                # Assume there are multiple unknown variables; users can define dynamic variables here
                variables = {
                    'cur_time': My_handle.common.get_bj_time(5),
                    'username': username
                }

                # Use a dictionary for string replacement
                if any(var in tmp for var in variables):
                    tmp = tmp.format(**{var: value for var, value in variables.items() if var in tmp})
                
                # [1|2]Bracket syntax randomly picks a value and returns the string after the value is substituted
                tmp = My_handle.common.brackets_text_randomize(tmp)

                logger.info(f"Local Q&A library - text answer is: {tmp}")

                """
                # Check whether the reply template is enabled
                if My_handle.config.get("reply_template", "enable"):
                    # Replace the reply content according to the template variable relationships
                    # Assume there are multiple unknown variables; users can define dynamic variables here
                    variables = {
                        'username': data["username"][:self.config.get("reply_template", "username_max_len")],
                        'data': tmp,
                        'cur_time': My_handle.common.get_bj_time(5),
                    }

                    reply_template_copywriting = My_handle.common.get_list_random_or_default(self.config.get("reply_template", "copywriting"), "{data}")
                    # Use a dictionary for string replacement
                    if any(var in reply_template_copywriting for var in variables):
                        tmp = reply_template_copywriting.format(**{var: value for var, value in variables.items() if var in reply_template_copywriting})

                logger.debug(f"After reply template conversion: {tmp}")
                """

                resp_content = tmp
                # Record the AI reply in the log file
                self.write_to_comment_log(resp_content, {"username": username, "content": content})
                
                message = {
                    "type": "comment",
                    "tts_type": My_handle.config.get("audio_synthesis_type"),
                    "data": My_handle.config.get(My_handle.config.get("audio_synthesis_type")),
                    "config": My_handle.config.get("filter"),
                    "username": username,
                    "content": resp_content
                }

                # Luoxi Live Danmaku Assistant
                if My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "enable") and \
                    "comment_reply" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "type") and \
                    "On message created" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "trigger_position"):
                    asyncio.run(send_msg_to_live_comment_assistant(My_handle.config.get("luoxi_project", "Live_Comment_Assistant"), resp_content))

                # Whether the periodic trigger feature is enabled; when enabled, data is cached and only triggered when the period arrives
                if My_handle.config.get("local_qa", "periodic_trigger", "enable"):
                    My_handle.task_data["local_qa"]["data"].append(message)
                else:
                    self.webui_show_chat_log_callback("Local Q&A - Text", data, resp_content)
                    
                    self.audio_synthesis_handle(message)

                return True

        # 2, match the local Q&A audio library; after it triggers, other later features are not executed
        if My_handle.config.get("local_qa")["audio"]["enable"]:
            # Output the danmaku message sent by the current user
            # logger.info(f"[{username}]: {content}")
            # Get all audio file names in the local Q&A audio library folder
            local_qa_audio_filename_list = My_handle.audio.get_dir_audios_filename(My_handle.config.get("local_qa", "audio", "file_path"), type=1)
            local_qa_audio_list = My_handle.audio.get_dir_audios_filename(My_handle.config.get("local_qa", "audio", "file_path"), type=0)

            # Search without the file extension
            local_qv_audio_filename = My_handle.common.find_best_match(content, local_qa_audio_filename_list, My_handle.config.get("local_qa", "audio", "similarity"))
            
            # print(f"local_qv_audio_filename={local_qv_audio_filename}")

            # Found a matching result
            if local_qv_audio_filename is not None:
                logger.info(f"Trigger local Q&A library - voice [{username}]: {content}")
                # Look the result up again in the original file name list and add the extension back
                local_qv_audio_filename = My_handle.common.find_best_match(local_qv_audio_filename, local_qa_audio_list, 0)

                # Find the corresponding file
                resp_content = My_handle.audio.search_files(My_handle.config.get("local_qa", "audio", "file_path"), local_qv_audio_filename)
                if resp_content != []:
                    logger.debug(f"Original relative path of the matched audio:{resp_content[0]}")

                    # Concatenate the audio file path
                    resp_content = f'{My_handle.config.get("local_qa", "audio", "file_path")}/{resp_content[0]}'
                    logger.info(f"Matched audio path:{resp_content}")
                    message = {
                        "type": "local_qa_audio",
                        "tts_type": My_handle.config.get("audio_synthesis_type"),
                        "data": My_handle.config.get(My_handle.config.get("audio_synthesis_type")),
                        "config": My_handle.config.get("filter"),
                        "username": username,
                        "content": content,
                        "file_path": resp_content
                    }

                    # Whether the periodic trigger feature is enabled; when enabled, data is cached and only triggered when the period arrives
                    if My_handle.config.get("local_qa", "periodic_trigger", "enable"):
                        My_handle.task_data["local_qa"]["data"].append(message)
                    else:
                        self.webui_show_chat_log_callback("Local Q&A - Audio", data, resp_content)

                        self.audio_synthesis_handle(message)

                    return True
            
        return False


    # Song request mode handling
    def choose_song_handle(self, data):
        """Song request mode handling

        Args:
            data (dict): Username danmaku data

        Returns:
            bool: Whether triggered and handled
        """
        username = data["username"]
        content = data["content"]

        

        # Merge consecutive * at the end of the string, mainly for cases where the username cannot be obtained
        username = My_handle.common.merge_consecutive_asterisks(username)

        if My_handle.config.get("choose_song")["enable"] == True:
            start_cmd = My_handle.common.starts_with_any(content, My_handle.config.get("choose_song", "start_cmd"))
            stop_cmd = My_handle.common.starts_with_any(content, My_handle.config.get("choose_song", "stop_cmd"))
            random_cmd = My_handle.common.starts_with_any(content, My_handle.config.get("choose_song", "random_cmd"))

            
            # Check whether the random song request command is correct
            if random_cmd:
                resp_content = My_handle.common.random_search_a_audio_file(My_handle.config.get("choose_song", "song_path"))
                if resp_content is None:
                    return True
                
                logger.info(f"Randomly selected audio path:{resp_content}")

                message = {
                    "type": "song",
                    "tts_type": My_handle.config.get("audio_synthesis_type"),
                    "data": My_handle.config.get(My_handle.config.get("audio_synthesis_type")),
                    "config": My_handle.config.get("filter"),
                    "username": username,
                    "content": resp_content
                }

                
                self.audio_synthesis_handle(message)

                self.webui_show_chat_log_callback("Song request", data, resp_content)

                return True
            # Check whether the song request command is correct
            elif start_cmd:
                logger.info(f"[{username}]: {content}")

                # Get all audio file names (without extensions) in the local audio folder
                choose_song_song_lists = My_handle.audio.get_dir_audios_filename(My_handle.config.get("choose_song", "song_path"), 1)

                # Remove the command prefix
                content = content[len(start_cmd):]

                # This means the user only sent the command without a song name, so the user does not know how to use it
                if content == "":
                    resp_content = f'Song request command error, the command is {My_handle.config.get("choose_song", "start_cmd")}+song name'
                    message = {
                        "type": "comment",
                        "tts_type": My_handle.config.get("audio_synthesis_type"),
                        "data": My_handle.config.get(My_handle.config.get("audio_synthesis_type")),
                        "config": My_handle.config.get("filter"),
                        "username": username,
                        "content": resp_content
                    }

                    self.audio_synthesis_handle(message)

                    self.webui_show_chat_log_callback("Song request", data, resp_content)

                    return True

                # Check whether this song exists
                song_filename = My_handle.common.find_best_match(content, choose_song_song_lists, similarity=My_handle.config.get("choose_song", "similarity"))
                if song_filename is None:
                    # resp_content = f"Sorry, I have not learned to sing it yet{content}"
                    # Synthesize using the configured match-failure reply copywriting
                    resp_content = My_handle.config.get("choose_song", "match_fail_copy").format(content=content)
                    logger.info(f"[AIReply to {username}]:{resp_content}")

                    message = {
                        "type": "comment",
                        "tts_type": My_handle.config.get("audio_synthesis_type"),
                        "data": My_handle.config.get(My_handle.config.get("audio_synthesis_type")),
                        "config": My_handle.config.get("filter"),
                        "username": username,
                        "content": resp_content
                    }

                    
                    self.audio_synthesis_handle(message)

                    self.webui_show_chat_log_callback("Song request", data, resp_content)

                    return True
                
                resp_content = My_handle.audio.search_files(My_handle.config.get('choose_song', 'song_path'), song_filename, True)
                if resp_content == []:
                    return True
                
                logger.debug(f"Original relative path of the matched audio:{resp_content[0]}")

                # Concatenate the audio file path
                resp_content = f"{My_handle.config.get('choose_song', 'song_path')}/{resp_content[0]}"
                resp_content = os.path.abspath(resp_content)
                logger.info(f"Song request succeeded! Matched audio path:{resp_content}")
                
                message = {
                    "type": "song",
                    "tts_type": My_handle.config.get("audio_synthesis_type"),
                    "data": My_handle.config.get(My_handle.config.get("audio_synthesis_type")),
                    "config": My_handle.config.get("filter"),
                    "username": username,
                    "content": resp_content
                }

                self.webui_show_chat_log_callback("Song request", data, resp_content)
                
                self.audio_synthesis_handle(message)

                return True
            # Check whether the cancel-song-request command is correct
            elif stop_cmd:
                My_handle.audio.stop_current_audio()

                return True
            

        return False


    """
    
         ]@@@@@               =@@       @@^              =@@@@@@].  .@@` ./@@@ ,@@@^                /@^                     
        @@^      @@*          =@@       @@^              =@@   ,@@\      =@@   @@^                                          
        \@@].  =@@@@@.=@@@@@` =@@@@@@@. @@^ ./@@@@\.     =@@    .@@^.@@.@@@@@@@@@@@.@@   @@^ /@@@@^ @@^ ./@@@@@]  @@/@@@@.  
          ,\@@\  @@*   .]]/@@ =@@.  =@\ @@^ @@\]]/@^     =@@     @@^.@@. =@@   @@^ .@@   @@^ @@\`   @@^ @@^   \@^ @@`  \@^  
             @@^ @@* ,@@` =@@ =@@   =@/ @@^ @@`          =@@   ./@/ .@@. =@@   @@^ .@@.  @@^   ,\@@ @@^ @@^   /@^ @@*  =@^  
       .@@@@@@/  \@@@.@@@@@@@ =@@@@@@/  @@^ .\@@@@@.     =@@@@@@/`  .@@. =@@   @@^  =@@@@@@^.@@@@@^ @@^ .\@@@@@`  @@*  =@^ 
    
    """

    # Drawing mode SD handling
    def sd_handle(self, data):
        """Drawing mode SD handling

        Args:
            data (dict): Username danmaku data

        Returns:
            bool: Whether triggered and handled
        """
        username = data["username"]
        content = data["content"]

        # Merge consecutive * at the end of the string, mainly for cases where the username cannot be obtained
        username = My_handle.common.merge_consecutive_asterisks(username)

        if content.startswith(My_handle.config.get("sd", "trigger")):
            # Banned content detection
            content = self.prohibitions_handle(content)
            if content is None:
                return
        
            if My_handle.config.get("sd", "enable") == False:
                logger.info("You have not enabled SD mode yet, so the drawing feature cannot be used")
                return True
            else:
                # Output the danmaku message sent by the current user
                logger.info(f"[{username}]: {content}")

                # Remove the command prefix from the text
                content = content[len(My_handle.config.get("sd", "trigger")):]

                if My_handle.config.get("sd", "translate_type") != "none":
                    # Determine the translation type and perform the translation
                    tmp = My_handle.my_translate.trans(content, My_handle.config.get("sd", "translate_type"))
                    if tmp:
                        content = tmp

                """
                Run different logic depending on the chat type
                """ 
                chat_type = My_handle.config.get("sd", "prompt_llm", "type")
                if chat_type in self.chat_type_list:
                    content = My_handle.config.get("sd", "prompt_llm", "before_prompt") + \
                        content + My_handle.config.get("after_prompt")
                    
                    data_json = {
                        "username": username,
                        "content": content,
                        "ori_username": data["username"],
                        "ori_content": data["content"]
                    }
                    resp_content = self.llm_handle(chat_type, data_json)
                    if resp_content is not None:
                        logger.info(f"[AIReply to {username}]:{resp_content}")
                    else:
                        resp_content = ""
                        logger.warning(f"Warning: {chat_type} has no return")
                elif chat_type == "none" or chat_type == "reread" or chat_type == "game":
                    resp_content = content
                else:
                    resp_content = content

                logger.info(f"Content passed to the SD API:{resp_content}")

                self.sd.process_input(resp_content)
                return True
            
        return False


    # Danmaku format check, special character replacement and specified language filtering
    def comment_check_and_replace(self, content):
        """Danmaku format check, special character replacement and specified language filtering

        Args:
            content (str): Danmaku content to be processed

        Returns:
            str: Danmaku content after processing/None
        """
        # Check whether the danmaku starts with xx; if so, returnNone
        if My_handle.config.get("filter", "before_filter_str") and any(
                content.startswith(prefix) for prefix in My_handle.config.get("filter", "before_filter_str")):
            return None

        # Check whether the danmaku ends with xx; if so, returnNone
        if My_handle.config.get("filter", "after_filter_str") and any(
                content.endswith(prefix) for prefix in My_handle.config.get("filter", "after_filter_str")):
            return None

        # Check whether the danmaku starts with xx; if not, returnNone
        if My_handle.config.get("filter", "before_must_str") and not any(
                content.startswith(prefix) for prefix in My_handle.config.get("filter", "before_must_str")):
            return None
        else:
            for prefix in My_handle.config.get("filter", "before_must_str"):
                if content.startswith(prefix):
                    content = content[len(prefix):]  # Delete the matching prefix
                    break

        # Check whether the danmaku ends with xx; if not, returnNone
        if My_handle.config.get("filter", "after_must_str") and not any(
                content.endswith(prefix) for prefix in My_handle.config.get("filter", "after_must_str")):
            return None
        else:
            for prefix in My_handle.config.get("filter", "after_must_str"):
                if content.endswith(prefix):
                    content = content[:-len(prefix)]  # Delete the matching suffix
                    break

        # All punctuation
        if My_handle.common.is_punctuation_string(content):
            return None

        # Convert newline to,
        content = content.replace('\n', ',')

        # Emote danmaku filtering
        if My_handle.config.get("filter", "emoji"):
            # For example, Bilibili emote danmaku are in the [emote name] format, filtered using a regular expression
            content = re.sub(r'\[.*?\]', '', content)
            logger.info(f"After emote danmaku filtering:{content}")

        # Language detection
        if My_handle.common.lang_check(content, My_handle.config.get("need_lang")) is None:
            logger.warning("Language detection failed, filtered")
            return None

        return content


    def get_tiktok_safety(self):
        """Lazily build the TikTok safety filter from config."""
        if getattr(self, "_tiktok_safety", None) is None:
            self._tiktok_safety = tiktok_safety.TikTokSafety(
                My_handle.config.get("filter", "tiktok_safety", "terms_path"),
                My_handle.config.get("filter", "badwords", "replace") or "*",
            )
        return self._tiktok_safety

    def get_analytics(self):
        """Lazily create the live analytics recorder (log/analytics/session-*.jsonl)."""
        if getattr(self, "_analytics", None) is None:
            try:
                enable = My_handle.config.get("analytics", "enable")
                enable = True if enable is None else bool(enable)
                d = My_handle.config.get("analytics", "dir") or "log/analytics"
            except Exception:
                enable, d = True, "log/analytics"
            self._analytics = live_analytics.LiveAnalytics(d, enable)
        return self._analytics

    def product_handle(self, data):
        """The seller pinned / popped up a product in the TikTok live room (pushed by tiktok_bridge.py).

        Keeps products.json in sync with the live cart and, optionally, pitches the product right away.

        Args:
            data (dict): product_id, title, price, image_url, open_url, live_product_number
        """
        try:
            catalog = self.get_product_catalog()
            if catalog is None:
                return
            product, is_new = catalog.upsert_pop(data, auto_add=bool(My_handle.config.get("products", "auto_add")))
            total = data.get("live_product_number")
            if total:
                logger.info(f"Live cart reports {total} products, catalog has {len(catalog.products)}")
            if product is None:
                return
            if is_new:
                logger.info(f"Added new product from the live room to the catalog: {product['name']}")
            self.get_analytics().record("product_pop", product_id=product["id"], new=bool(is_new))
            self.set_current_product(product)

            if not My_handle.config.get("products", "pitch_on_pop"):
                return
            # Debounce: TikTok re-sends the pop-up while a product stays pinned
            now = time.time()
            last = self.__dict__.setdefault("_last_product_pitch", {})
            if now - last.get(product["id"], 0) < float(My_handle.config.get("products", "pitch_on_pop_cooldown") or 120):
                return
            last[product["id"]] = now

            pitch = catalog.build_pitch(product, len(last))
            pitch = self.prohibitions_handle(pitch, scope="output")
            if pitch is None:
                logger.warning(f"Pinned-product pitch dropped by the safety filter: {product['name']}")
                return
            self.get_analytics().record("pitch", product_id=product["id"], source="pop")
            self.reread_handle({"username": "Streamer", "content": pitch}, type="reread")
        except Exception:
            logger.error(traceback.format_exc())

    def sales_handle(self, data):
        """Anonymous sold-counter updates from the live room: thank the room when real sales happened (opt-in)."""
        try:
            from . import sales
            cfg = sales.load_settings()
            if not cfg["enable"]:
                return
            watcher = self.__dict__.setdefault("_sales_watcher", sales.SalesWatcher())
            now = time.time()
            gained = None
            product_id = ""
            for tag in data.get("tags") or []:
                got = watcher.update(tag.get("product_id"), tag.get("desc"), tag.get("count"), now,
                                     step=cfg["step"], cooldown=cfg["cooldown"])
                if got:
                    gained, product_id = got, str(tag.get("product_id"))
                    break
            if not gained:
                return
            name = "sản phẩm này"
            catalog = self.get_product_catalog()
            if catalog is not None:
                product = next((p for p in catalog.products if str(p.get("id")) == product_id), None)
                if product:
                    name = product["name"]
                    self.set_current_product(product)
            text = random.choice(sales.TEMPLATES).format(product=name, n=gained)
            text = self.prohibitions_handle(text, scope="output")
            if text is None:
                return
            self.get_analytics().record("shoutout", kind="sales", n=int(gained))
            self.reread_handle({"username": "Streamer", "content": text}, type="reread")
        except Exception:
            logger.error(traceback.format_exc())

    def current_product_name(self):
        """Name of the product being shown right now (last pinned / pitched), for thank-you lines."""
        name = getattr(self, "_current_product", None)
        if name and time.time() - getattr(self, "_current_product_ts", 0) < 900:
            return name
        return "các sản phẩm trong giỏ hàng"

    def set_current_product(self, product):
        if product and product.get("name"):
            self._current_product = product["name"]
            self._current_product_ts = time.time()

    def thanks_fill(self, template, data):
        """Fill {username} / {product} in a thank-you template without failing on unknown placeholders."""
        return My_handle.common.dynamic_variable_replacement(
            template, {"username": data.get("username", ""), "product": self.current_product_name()})

    def flash_sale_tick(self):
        """Called every few seconds by a background thread: announce the flash sale when it is due."""
        try:
            path = My_handle.config.get("products", "flash_sale_path") or flash_sale.DEFAULT_PATH
            state = flash_sale.load_state(path)
            if not state or not state.get("active"):
                return
            catalog = self.get_product_catalog()
            if catalog is None:
                return
            product = next((p for p in catalog.products if p.get("id") == state.get("product_id")), None)
            text, new_state = flash_sale.next_announcement(state, product, catalog.templates)
            if new_state is not None and new_state != state:
                flash_sale.save_state(new_state, path)
            if not text:
                return
            self.set_current_product(product)
            text = self.prohibitions_handle(text, scope="output")
            if text is None:
                logger.warning("Flash-sale announcement dropped by the safety filter; edit the flash_* templates")
                return
            self.get_analytics().record("pitch", product_id=product["id"], source="flash_sale")
            self.reread_handle({"username": "Streamer", "content": text}, type="reread")
        except Exception:
            logger.error(traceback.format_exc())

    _engage_lock = threading.Lock()

    def _engage_path(self):
        from utils import setup_wizard
        return os.path.join(setup_wizard.ROOT, engage.DEFAULT_PATH)

    def engage_consume(self, username, content):
        """True when the comment was a giveaway entry or a poll vote (counted, nothing else to do with it)."""
        try:
            with My_handle._engage_lock:
                path = self._engage_path()
                st = engage.load_state(path)
                if not any(st.get(k) and st[k].get("active") for k in ("giveaway", "poll")):
                    return False
                hit = engage.consume(st, username, content)
                if hit:
                    engage.save_state(st, path)
                    self.get_analytics().record("comment", user=username, text=content, intent="engage")
                return bool(hit)
        except Exception:
            logger.error(traceback.format_exc())
            return False

    def reader_cmd_consume(self, username, content):
        """True when the comment was a reader command or vote (only while a reader runs with viewer commands switched on)."""
        try:
            from utils import setup_wizard, reader_cmds
            return reader_cmds.consume(os.path.join(setup_wizard.ROOT, reader_cmds.DEFAULT_PATH), username, content)
        except Exception:
            logger.error(traceback.format_exc())
            return False

    def engage_tick(self):
        """Every few seconds: speak the next giveaway / poll announcement when it is due."""
        try:
            with My_handle._engage_lock:
                path = self._engage_path()
                st = engage.load_state(path)
                if not any(st.get(k) and st[k].get("active") for k in ("giveaway", "poll")):
                    return
                catalog = self.get_product_catalog()
                text, st = engage.next_announcement(st, templates=catalog.templates if catalog is not None else None)
                if not text:
                    return
                engage.save_state(st, path)
            safe = self.prohibitions_handle(text, scope="output")
            if safe is None:
                logger.warning("Giveaway/poll announcement dropped by the safety filter (maybe a name or the prize text)")
                if st.get("giveaway") and st["giveaway"].get("winners"):
                    safe = "Quay số xong rồi, chúc mừng người may mắn, bạn xem tên trên màn hình live nha!"
                else:
                    return
            self.reread_handle({"username": "Streamer", "content": safe}, type="reread")
        except Exception:
            logger.error(traceback.format_exc())

    def engage_loop(self, interval=3):
        while True:
            self.engage_tick()
            time.sleep(interval)

    def flash_sale_loop(self, interval=5):
        while True:
            self.flash_sale_tick()
            time.sleep(interval)

    def spotlight_handle(self, product):
        """Auto-spotlight: when several viewers ask about the same product in a short window, pitch it again.

        Settings: products.spotlight {enable, min_questions, window_sec, cooldown_sec}. Shares the per-product
        cooldown with pitch-on-pin so the same item is never repeated back to back.
        """
        try:
            cfg = My_handle.config.get("products", "spotlight") or {}
            if not cfg.get("enable") or not product:
                return
            window = int(cfg.get("window_sec") or 300)
            asked = self.get_analytics().recent_sales_questions(product["id"], window)
            if asked < int(cfg.get("min_questions") or 3):
                return
            now = time.time()
            last = self.__dict__.setdefault("_last_product_pitch", {})
            if now - last.get(product["id"], 0) < float(cfg.get("cooldown_sec") or 600):
                return
            last[product["id"]] = now
            catalog = self.get_product_catalog()
            pitch = catalog.build_pitch(product, len(last))
            pitch = self.prohibitions_handle(pitch, scope="output")
            if pitch is None:
                return
            logger.info(f"Spotlight: {asked} questions about {product['name']} in {window}s, pitching it again")
            self.get_analytics().record("pitch", product_id=product["id"], source="spotlight")
            self.set_current_product(product)
            self.reread_handle({"username": "Streamer", "content": pitch}, type="reread")
        except Exception:
            logger.error(traceback.format_exc())

    def get_product_catalog(self):
        """Lazily load the product catalog; returns None when the feature is disabled or the file is missing."""
        if not My_handle.config.get("products", "enable"):
            return None
        if getattr(self, "_product_catalog", None) is None:
            try:
                self._product_catalog = product_catalog.ProductCatalog(
                    My_handle.config.get("products", "path"),
                    My_handle.config.get("products", "templates_path"),
                )
            except Exception as e:
                logger.error(f"Failed to load product catalog: {e}")
                return None
        return self._product_catalog

    # Banned content handling
    def prohibitions_handle(self, content, scope="input"):
        """Banned content handling

        Args:
            content (str): String content to be checked

        Returns:
            str: Yes: None; no, return:content
        """
        # Contains a link
        if My_handle.common.is_url_check(content):
            logger.warning(f"Link:{content}")
            return None

        # Never read out Chinese / Japanese / Korean (some local models drift into it)
        if scope == "output" and lang_guard.has_cjk(content):
            fixed = lang_guard.clean(content)
            logger.warning(f"Language guard removed CJK text from the reply: {content!r} -> {fixed!r}")
            if fixed is None:
                return None
            content = fixed

        # TikTok policy / Vietnamese-aware safety filter (scope: "input" = viewer text, "output" = what the AI says)
        if My_handle.config.get("filter", "tiktok_safety", "enable"):
            try:
                safety = self.get_tiktok_safety()
                hits = safety.check(content, scope)
                if hits:
                    self.get_analytics().record(
                        "blocked", scope=scope, categories=sorted({h.category for h in hits}),
                        action="drop" if any(h.action == "drop" for h in hits) else "mask")
                tmp = safety.sanitize(content, scope)
                if tmp is None:
                    logger.warning(f"TikTok safety filter dropped ({scope}): {content}")
                    return None
                content = tmp
            except Exception as e:
                logger.error(f"TikTok safety filter error: {e}")
        
        # Banned word detection
        if My_handle.config.get("filter", "badwords", "enable"):
            if My_handle.common.profanity_content(content):
                logger.warning(f"Banned word:{content}")
                return None
            
            bad_word = My_handle.common.check_sensitive_words2(My_handle.config.get("filter", "badwords", "path"), content)
            if bad_word is not None:
                logger.warning(f"Hit local banned word: {bad_word}")

                # Whether to discard
                if My_handle.config.get("filter", "badwords", "discard"):
                    return None
                
                # Perform banned word replacement
                content = content.replace(bad_word, My_handle.config.get("filter", "badwords", "replace"))

                logger.info(f"After banned word replacement:{content}")

                # Callback, filter and replace banned words multiple times
                return self.prohibitions_handle(content, scope)


            # Same-pinyin banned word filtering
            if My_handle.config.get("filter", "badwords", "bad_pinyin_path") != "":
                if My_handle.common.check_sensitive_words3(My_handle.config.get("filter", "badwords", "bad_pinyin_path"), content):
                    logger.warning(f"Homophone banned word:{content}")
                    return None

        return content


    # Repeat directly
    def reread_handle(self, data, filter=False, type="reread"):
        """Repeat handling

        Args:
            data (dict): Contains the username and danmaku content
            filter (bool): Whether to enable filtering of repeated content
            type (str): Type of repeat data (reread | trends_copywriting)

        Returns:
            _type_: Lonely
        """
        try:
            username = data["username"]
            content = data["content"]

            logger.info(f"Repeat content:{content}")

            if filter:
                # Banned content handling
                content = self.prohibitions_handle(content)
                if content is None:
                    return
                
                # Danmaku format check, special character replacement and specified language filtering
                content = self.comment_check_and_replace(content)
                if content is None:
                    return
                
                # Check whether the string is all punctuation; if so, filter it out
                if My_handle.common.is_punctuation_string(content):
                    logger.debug(f"User: {username}], sent a danmaku of only symbols, filtered")
                    return
            
            # Important data needed for audio synthesis
            message = {
                "type": type,
                "tts_type": My_handle.config.get("audio_synthesis_type"),
                "data": My_handle.config.get(My_handle.config.get("audio_synthesis_type")),
                "config": My_handle.config.get("filter"),
                "username": username,
                "content": content
            }

            # Optional per-line voice / speed (the novel reader uses a second voice for dialogue)
            if (data.get("voice") or data.get("rate")) and isinstance(message.get("data"), dict):
                override = dict(message["data"])
                if data.get("voice"):
                    override["voice"] = str(data["voice"])[:80]
                if data.get("rate") and message["tts_type"] == "edge-tts":
                    r = str(data["rate"])
                    if len(r) <= 6 and r[0] in "+-" and r[-1] == "%":
                        override["rate"] = r
                message["data"] = override

            # Audio insertion index (applies to audio_player_v2)
            if "insert_index" in data:
                message["insert_index"] = data["insert_index"]

            logger.debug(message)

            # Luoxi Live Danmaku Assistant
            if My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "enable") and \
                "reread" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "type") and \
                "On message created" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "trigger_position"):
                asyncio.run(send_msg_to_live_comment_assistant(My_handle.config.get("luoxi_project", "Live_Comment_Assistant"), content))

            self.audio_synthesis_handle(message)
        except Exception as e:
            logger.error(traceback.format_exc())

    # Tuning
    def tuning_handle(self, data_json):
        """Persona-tuning LLM handling

        Args:
            data_json (dict): Contains the username and danmaku content

        Returns:
            _type_: Lonely
        """
        try:
            logger.info(f"Tuning command:{data_json['content']}")

            """
            Run different logic depending on the chat type
            """ 
            chat_type = My_handle.config.get("chat_type")
            if chat_type in self.chat_type_list:
                data_json["ori_username"] = data_json["username"]
                data_json["ori_content"] = data_json["content"]
                resp_content = self.llm_handle(chat_type, data_json)
                if resp_content is not None:
                    logger.info(f"[AIReply{My_handle.config.get('talk', 'username')}]:{resp_content}")
                else:
                    logger.warning(f"Warning: {chat_type} has no return")
        except Exception as e:
            logger.error(traceback.format_exc())

    # Danmaku log recording
    def write_to_comment_log(self, resp_content: str, data: dict):
        try:
            # Record the AI reply in the log file
            with open(self.comment_file_path, "r+", encoding="utf-8") as f:
                tmp_content = f.read()
                # Move the pointer to the start of the file (so that when the log file is read during a live stream, the latest content is always shown at the top)
                f.seek(0, 0)
                # But this implementation feels a bit inefficient
                # Set the maximum characters per line, mainly to fix display overflow when danmaku is too long while connecting to live danmaku display
                max_length = 20
                resp_content_substrings = [resp_content[i:i + max_length] for i in range(0, len(resp_content), max_length)]
                resp_content_joined = '\n'.join(resp_content_substrings)

                # Write various logs according to the danmaku log type
                if My_handle.config.get("comment_log_type") == "Q&A":
                    f.write(f"[{data['username']} Question]:\n{data['content']}\n[AIReply{data['username']}]:{resp_content_joined}\n" + tmp_content)
                elif My_handle.config.get("comment_log_type") == "Question":
                    f.write(f"[{data['username']} Question]:\n{data['content']}\n" + tmp_content)
                elif My_handle.config.get("comment_log_type") == "Answer":
                    f.write(f"[AIReply{data['username']}]:\n{resp_content_joined}\n" + tmp_content)
        except Exception as e:
            logger.error(traceback.format_exc())

    """

                 .@@@@@@@@@@@                    .@@@@@@@@@@@                    .@@@@@@@@@@@@@@^         /@@@@@@@@@@@@@@              
                 .@@@@@@@@@@@                    .@@@@@@@@@@@                    .@@@@@@@@@@@@@@@        ,@@@@@@@@@@@@@@@              
                 .@@@@@@@@@@@                    .@@@@@@@@@@@                    .@@@@@@@@@@@@@@@^       /@@@@@@@@@@@@@@@              
                 .@@@@@@@@@@@                    .@@@@@@@@@@@                    .@@@@@@@@@@@@@@@@.     ,@@@@@@@@@@@@@@@@              
                 .@@@@@@@@@@@                    .@@@@@@@@@@@                    .@@@@@@@@@@@@@@@@^     /@@@@@@@@@@@@@@@@              
                 .@@@@@@@@@@@                    .@@@@@@@@@@@                    .@@@@@@@@@=@@@@@@@.   ,@@@@@@@^@@@@@@@@@              
                 .@@@@@@@@@@@                    .@@@@@@@@@@@                    .@@@@@@@@@.@@@@@@@^   @@@@@@@@.@@@@@@@@@              
                 .@@@@@@@@@@@                    .@@@@@@@@@@@                    .@@@@@@@@@ =@@@@@@@. =@@@@@@@^.@@@@@@@@@              
                 .@@@@@@@@@@@                    .@@@@@@@@@@@                    .@@@@@@@@@ .@@@@@@@^ @@@@@@@@ .@@@@@@@@@              
                 .@@@@@@@@@@@                    .@@@@@@@@@@@                    .@@@@@@@@@  =@@@@@@@=@@@@@@@^ .@@@@@@@@@              
                 .@@@@@@@@@@@                    .@@@@@@@@@@@                    .@@@@@@@@@  .@@@@@@@@@@@@@@@  .@@@@@@@@@              
                 .@@@@@@@@@@@                    .@@@@@@@@@@@                    .@@@@@@@@@   =@@@@@@@@@@@@@^  .@@@@@@@@@              
                 .@@@@@@@@@@@                    .@@@@@@@@@@@                    .@@@@@@@@@   .@@@@@@@@@@@@/   .@@@@@@@@@              
                 .@@@@@@@@@@@@@@@@@@@@@@@@@@@^   .@@@@@@@@@@@@@@@@@@@@@@@@@@@^   .@@@@@@@@@    =@@@@@@@@@@@`   .@@@@@@@@@              
                 .@@@@@@@@@@@@@@@@@@@@@@@@@@@^   .@@@@@@@@@@@@@@@@@@@@@@@@@@@^   .@@@@@@@@@    .@@@@@@@@@@/    .@@@@@@@@@              
                 .@@@@@@@@@@@@@@@@@@@@@@@@@@@^   .@@@@@@@@@@@@@@@@@@@@@@@@@@@^   .@@@@@@@@@     =@@@@@@@@@`    .@@@@@@@@@              
                 .@@@@@@@@@@@@@@@@@@@@@@@@@@@^   .@@@@@@@@@@@@@@@@@@@@@@@@@@@^   .@@@@@@@@@     .@@@@@@@@/     .@@@@@@@@@  

    """


    # LLMHandle
    def llm_handle(self, chat_type, data, type="chat", webui_show=True):
        """LLMUnified handling

        Args:
            chat_type (str): Chat type
            data (str): dict, including username and content
            type (str): Type of call (chat / vision)
            webui_show (bool): Whether to display on the webui

        Returns:
            str: LLMReturned result
        """
        try:
            # Check whether the danmaku starts with xx; if not, return None and do not triggerLLM
            if My_handle.config.get("filter", "before_must_str_for_llm") != []:
                if any(data["ori_content"].startswith(prefix) for prefix in My_handle.config.get("filter", "before_must_str_for_llm")):
                    pass
                else:
                    return None
            
            # Check whether the danmaku ends with xx; if not, returnNone
            if My_handle.config.get("filter", "after_must_str_for_llm") != []:
                if any(data["ori_content"].endswith(prefix) for prefix in My_handle.config.get("filter", "after_must_str_for_llm")):
                    pass
                else:
                    return None

            resp_content = None
            
            logger.debug(f"chat_type={chat_type}, data={data}")

            if type == "chat":
                # Use getattr to get the attribute dynamically
                if getattr(self, chat_type, None) is None:
                    self.get_chat_model(chat_type, My_handle.config)
                    # setattr(self, chat_type, GPT_MODEL.get(chat_type))
            
                # New LLMs need to be added here
                chat_model_methods = {
                    "chatgpt": lambda: self.chatgpt.get_gpt_resp(data["username"], data["content"]),
                    "chatterbot": lambda: self.bot.get_response(data["content"]).text,
                    "chat_with_file": lambda: self.chat_with_file.get_model_resp(data["content"]),
                    "text_generation_webui": lambda: self.text_generation_webui.get_resp(data["content"]),
                    "sparkdesk": lambda: self.sparkdesk.get_resp(data["content"]),
                    "langchain_chatchat": lambda: self.langchain_chatchat.get_resp(data["content"]),
                    "zhipu": lambda: self.zhipu.get_resp(data["content"]),
                    "bard": lambda: self.bard_api.get_resp(data["content"]),
                    "tongyi": lambda: self.tongyi.get_resp(data["content"]),
                    "tongyixingchen": lambda: self.tongyixingchen.get_resp(data["content"]),
                    "my_wenxinworkshop": lambda: self.my_wenxinworkshop.get_resp(data["content"]),
                    "gemini": lambda: self.gemini.get_resp(data["content"]),
                    "koboldcpp": lambda: self.koboldcpp.get_resp({"prompt": data["content"]}),
                    "anythingllm": lambda: self.anythingllm.get_resp({"prompt": data["content"]}),
                    "gpt4free": lambda: self.gpt4free.get_resp({"prompt": data["content"]}),
                    "custom_llm": lambda: self.custom_llm.get_resp({"prompt": data["content"]}),
                    "llm_tpu": lambda: self.llm_tpu.get_resp({"prompt": data["content"]}),
                    "dify": lambda: self.dify.get_resp({"prompt": data["content"]}),
                    "volcengine": lambda: self.volcengine.get_resp({"prompt": data["content"]}),
                    "reread": lambda: data["content"]
                }
            elif type == "vision":
                # Use getattr to get the attribute dynamically
                if getattr(self, chat_type, None) is None:
                    self.get_vision_model(chat_type, My_handle.config.get("image_recognition", chat_type))
                
                # New LLMs need to be added here
                chat_model_methods = {
                    "gemini": lambda: self.image_recognition_model.get_resp_with_img(data["content"], data["img_data"]),
                    "zhipu": lambda: self.image_recognition_model.get_resp_with_img(data["content"], data["img_data"]),
                }

            # Use a dict mapping to get the response content
            resp_content = chat_model_methods.get(chat_type, lambda: data["content"])()

            if resp_content is not None:
                resp_content = resp_content.strip()
                # Replace \n newline characters \n string with empty
                resp_content = re.sub(r'\\n|\n', '', resp_content)

                # Initialize the filter state
                filter_state = {
                    'is_filtering': False,
                    'current_tag': None,
                    'buffer': ''
                }
                # Filter <></> tag content, mainly for deepseek responses
                resp_content = My_handle.common.llm_resp_content_filter_tags(resp_content, filter_state)

                if lang_guard.needs_retry(resp_content) and type == "chat" and not data.get("_retried"):
                    logger.warning("Reply had no Vietnamese/English text; asking the model once more")
                    return self.llm_handle(chat_type, dict(data, content=data["content"] + lang_guard.RETRY_NOTE, _retried=True),
                                           type, webui_show)

                if lang_guard.has_cjk(resp_content):
                    fixed = lang_guard.clean(resp_content)
                    logger.warning(f"Language guard removed CJK text from the reply: {resp_content!r} -> {fixed!r}")
                    resp_content = fixed

            # Check whether the reply template is enabled
            if My_handle.config.get("reply_template", "enable"):
                # Replace the reply content according to the template variable relationships
                # Assume there are multiple unknown variables; users can define dynamic variables here
                variables = {
                    'username': data["username"][:self.config.get("reply_template", "username_max_len")],
                    'data': resp_content,
                    'cur_time': My_handle.common.get_bj_time(5),
                }

                reply_template_copywriting = My_handle.common.get_list_random_or_default(self.config.get("reply_template", "copywriting"), "{data}")
                # Use a dictionary for string replacement
                if any(var in reply_template_copywriting for var in variables):
                    resp_content = reply_template_copywriting.format(**{var: value for var, value in variables.items() if var in reply_template_copywriting})


            logger.debug(f"resp_content={resp_content}")

            # Return is empty, trigger an exception alert
            if resp_content is None:
                self.abnormal_alarm_handle("llm")
                logger.warning("LLMData was not returned correctly, please check whether the config, network, etc. are normal. If everything checks out, it may be a compatibility issue caused by an API change; you can go to the official repository and submit an issue, link:https://github.com/Ikaros-521/AI-Vtuber/issues")
            
            # Whether to enable webui echo
            if webui_show and resp_content:
                self.webui_show_chat_log_callback(chat_type, data, resp_content)

            return resp_content
        except Exception as e:
            logger.error(traceback.format_exc())

        return None

    # Streaming LLM handling + audio synthesis
    def llm_stream_handle_and_audio_synthesis(self, chat_type, data, type="chat", webui_show=True):
        """LLMUnified handling

        Args:
            chat_type (str): Chat type
            data (str): dict, including username and content
            type (str): Type of call (chat / vision)
            webui_show (bool): Whether to display on the webui

        Returns:
            str: LLMReturned result
        """
        try:
            # Check whether the danmaku starts with xx; if not, return None and do not triggerLLM
            if My_handle.config.get("filter", "before_must_str_for_llm") != []:
                if any(data["ori_content"].startswith(prefix) for prefix in My_handle.config.get("filter", "before_must_str_for_llm")):
                    pass
                else:
                    return None
            
            # Check whether the danmaku ends with xx; if not, returnNone
            if My_handle.config.get("filter", "after_must_str_for_llm") != []:
                if any(data["ori_content"].endswith(prefix) for prefix in My_handle.config.get("filter", "after_must_str_for_llm")):
                    pass
                else:
                    return None

            # The entire LLM response content finally returned
            resp_content = ""

            # Back up the content passed to the LLM, for context memory
            content_bak = data["content"]
            
            logger.debug(f"chat_type={chat_type}, data={data}")

            if type == "chat":
                # Use getattr to get the attribute dynamically
                if getattr(self, chat_type, None) is None:
                    self.get_chat_model(chat_type, My_handle.config)
                    # setattr(self, chat_type, GPT_MODEL.get(chat_type))
            
                # New LLMs need to be added here
                chat_model_methods = {
                    "chatgpt": lambda: self.chatgpt.get_gpt_resp(data["username"], data["content"], stream=True),
                    "zhipu": lambda: self.zhipu.get_resp(data["content"], stream=True),
                    "tongyi": lambda: self.tongyi.get_resp(data["content"], stream=True),
                    "tongyixingchen": lambda: self.tongyixingchen.get_resp(data["content"], stream=True),
                    "my_wenxinworkshop": lambda: self.my_wenxinworkshop.get_resp(data["content"], stream=True),
                    "volcengine": lambda: self.volcengine.get_resp({"prompt": data["content"]}, stream=True),
                    "dify": lambda: self.dify.get_resp({"prompt": data["content"]}, stream=True),
                }
            elif type == "vision":
                pass

            # Use a dict mapping to get the response content
            resp = chat_model_methods.get(chat_type, lambda: data["content"])()
            
            def split_by_chinese_punctuation(s):
                # Define the set of Chinese punctuation marks
                chinese_punctuation = "。、，；！？"
                
                # Iterate over each character in the string
                for i, char in enumerate(s):
                    if char in chinese_punctuation:
                        # Find the first Chinese punctuation mark and split there
                        return {"ret": True, "content1": s[:i+1], "content2": s[i+1:].lstrip()}
                
                # If no Chinese punctuation is found, return the original string and an empty string
                return {"ret": False, "content1": s, "content2": ""}

            if resp is not None:
                # Initial temporary text storage variable when streaming starts concatenating text content
                tmp = ""

                # Check whether the reply template is enabled
                if My_handle.config.get("reply_template", "enable"):
                    # Replace the reply content according to the template variable relationships
                    # Assume there are multiple unknown variables; users can define dynamic variables here
                    variables = {
                        'username': data["username"][:self.config.get("reply_template", "username_max_len")],
                        'data': "",
                        'cur_time': My_handle.common.get_bj_time(5),
                    }

                    reply_template_copywriting = My_handle.common.get_list_random_or_default(self.config.get("reply_template", "copywriting"), "")
                    # Use a dictionary for string replacement
                    if any(var in reply_template_copywriting for var in variables):
                        tmp = reply_template_copywriting.format(**{var: value for var, value in variables.items() if var in reply_template_copywriting})


                # Length of characters already cut off; for some special LLM streaming outputs, the leading characters need to be removed
                cut_len = 0

                # Special handling for the Zhipu agent
                if chat_type == "zhipu" and My_handle.config.get("zhipu", "model") == "Agent":
                    resp = resp.iter_lines()

                # Initialize the filter state
                filter_state = {
                    'is_filtering': False,
                    'current_tag': None,
                    'buffer': ''
                }

                buffer = b""

                def tmp_handle(resp_json: dict, tmp: str, cut_len: int=0):
                    if resp_json["ret"]:
                        # Sentence cut out
                        tmp_content = resp_json["content1"]
                        
                        #logger.warning(f"Sentence generation:{tmp_content}")

                        if chat_type in ["chatgpt", "zhipu", "tongyixingchen", "my_wenxinworkshop", "volcengine", "dify"]:
                            # Special handling for the Zhipu agent
                            if chat_type == "zhipu" and My_handle.config.get("zhipu", "model") == "Agent":
                                # Record and append the length of the cut-out text
                                cut_len += len(tmp_content)
                            else:
                                # Keep the content after the punctuation mark, to continue appending content later
                                tmp = resp_json["content2"]
                        elif chat_type in ["tongyi"]:
                            # Record and append the length of the cut-out text
                            cut_len += len(tmp_content)
                            
                        """
                        Double filtering to safeguard you
                        """
                        tmp_content = tmp_content.strip()

                        tmp_content = tmp_content.replace('\n', '。')

                        # Replace \n newline characters \n string with empty
                        tmp_content = re.sub(r'\\n|\n', '', tmp_content)
                        
                        # LLMCheck the reply content for banned words
                        tmp_content = self.prohibitions_handle(tmp_content, scope="output")
                        if tmp_content is None:
                            return tmp, cut_len

                        # logger.info("tmp_content=" + tmp_content)

                        # Whether to translate the reply content
                        if My_handle.config.get("translate", "enable") and (My_handle.config.get("translate", "trans_type") == "Reply" or \
                            My_handle.config.get("translate", "trans_type") == "Comment + Reply"):
                            tmp = My_handle.my_translate.trans(tmp_content)
                            if tmp:
                                tmp_content = tmp

                        self.write_to_comment_log(tmp_content, data)

                        # Determine the key mapping trigger type
                        if My_handle.config.get("key_mapping", "type") == "Reply" or My_handle.config.get("key_mapping", "type") == "Comment + Reply":
                            # Replacement content
                            data["content"] = tmp_content
                            # Key mapping; after it triggers, other later features are not executed
                            if self.key_mapping_handle("Reply", data):
                                pass

                        # Determine the custom command trigger type
                        if My_handle.config.get("custom_cmd", "type") == "Reply" or My_handle.config.get("custom_cmd", "type") == "Comment + Reply":
                            # Replacement content
                            data["content"] = tmp_content
                            # Custom command; after it triggers, other later features are not executed
                            if self.custom_cmd_handle("Reply", data):
                                pass
                            

                        # Important data needed for audio synthesis
                        message = {
                            "type": "comment",
                            "tts_type": My_handle.config.get("audio_synthesis_type"),
                            "data": My_handle.config.get(My_handle.config.get("audio_synthesis_type")),
                            "config": My_handle.config.get("filter"),
                            "username": data['username'],
                            "content": tmp_content
                        }

                        # Luoxi Live Danmaku Assistant
                        if My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "enable") and \
                            "comment_reply" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "type") and \
                            "On message created" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "trigger_position"):
                            asyncio.run(send_msg_to_live_comment_assistant(My_handle.config.get("luoxi_project", "Live_Comment_Assistant"), tmp_content))

                        self.audio_synthesis_handle(message)

                        return tmp, cut_len

                    return tmp, cut_len


                for chunk in resp:
                    # logger.warning(chunk)
                    if chunk is None:
                        continue

                    if chat_type in ["chatgpt", "zhipu"]:
                        # Special handling for the Zhipu agent
                        if chat_type == "zhipu" and My_handle.config.get("zhipu", "model") == "Agent":
                            decoded_line = chunk.decode('utf-8')
                            if decoded_line.startswith('data:'):
                                data_dict = json.loads(decoded_line[5:])
                                message = data_dict.get("message")
                                if len(message) > 0:
                                    content = message.get("content")
                                    if len(content) > 0:
                                        response_type = content.get("type")
                                        if response_type == "text":
                                            text = content.get("text", "")
                                            #logger.warning(f"cut_len={cut_len},Zhipu returned content:{text}")
                                            # This keeps outputting the full content, so the length of already processed text must be cut off
                                            tmp = text[cut_len:]
                                            resp_content = text
                                        else:
                                            continue
                                    else:
                                        continue
                                else:
                                    continue
                            else:
                                continue
                        else:
                            if chunk.choices[0].delta.content:
                                # Filter <></> tag content, mainly for deepseek responses
                                chunk.choices[0].delta.content = My_handle.common.llm_resp_content_filter_tags(chunk.choices[0].delta.content, filter_state)

                                # Streamed content is in append form
                                tmp += chunk.choices[0].delta.content
                                resp_content += chunk.choices[0].delta.content
                    elif chat_type in ["tongyi"]:
                        # This keeps outputting the full content, so the length of already processed text must be cut off
                        tmp = chunk.output.choices[0].message.content[cut_len:]
                        resp_content = chunk.output.choices[0].message.content
                    elif chat_type in ["tongyixingchen"]:
                        # Streamed content is in append form
                        tmp += chunk.data.choices[0].messages[0].content
                        resp_content += chunk.data.choices[0].messages[0].content
                    elif chat_type in ["volcengine"]:
                        tmp += chunk.choices[0].delta.content
                        resp_content += chunk.choices[0].delta.content
                    elif chat_type in ["my_wenxinworkshop"]:
                        tmp += chunk
                        resp_content += chunk
                    elif chat_type in ["dify"]:
                        # Add the new data to the buffer
                        buffer += chunk
                        
                        # Initializeresp_json
                        resp_json = {"ret": False, "content1": "", "content2": ""}
                        
                        # Try splitting the data by line
                        while b"\n" in buffer:
                            # Get one complete line
                            line, buffer = buffer.split(b"\n", 1)
                            line = line.strip()
                            
                            # Skip empty lines
                            if not line:
                                continue
                                
                            # Handle the data: prefix
                            if line.startswith(b"data: "):
                                try:
                                    # Parse JSON data
                                    data_chunk = json.loads(line[6:].decode('utf-8'))
                                    
                                    # Handle different types of events
                                    if "event" in data_chunk:
                                        if data_chunk["event"] == "message":
                                            answer = data_chunk.get("answer", "")

                                            # Filter <></> tag content, mainly for deepseek responses
                                            answer = My_handle.common.llm_resp_content_filter_tags(answer, filter_state)

                                            tmp += answer
                                            resp_content += answer

                                            resp_json = split_by_chinese_punctuation(tmp)
                                            #logger.warning(f"resp_json={resp_json}")
                                            tmp, cut_len = tmp_handle(resp_json, tmp, cut_len)
                                        elif data_chunk["event"] == "message_end":
                                            self.dify.add_assistant_msg_to_session(data_chunk["conversation_id"])
                                            resp_json = split_by_chinese_punctuation(tmp)
                                            if not resp_json['ret']:
                                                resp_json['ret'] = True
                                                logger.warning(f"resp_json={resp_json}")
                                                tmp, cut_len = tmp_handle(resp_json, tmp, cut_len)
                                            logger.info(f"[{chat_type}] Streaming reception complete")
                                            break
                                        elif data_chunk["event"] == "error":
                                            logger.error(f"DifyReturn an error: {data_chunk}")
                                            break
                                except json.JSONDecodeError as e:
                                    logger.error(f"JSONParse error: {e}. Original data: {line}")
                                    continue
                            else:
                                logger.debug(f"Skip lines that do not start with data:: {line}")
                                continue

                    if chat_type not in ["dify"]:
                        # Used for splitting; split sentences by Chinese punctuation
                        resp_json = split_by_chinese_punctuation(tmp)
                        #logger.warning(f"resp_json={resp_json}")
                        tmp, cut_len = tmp_handle(resp_json, tmp, cut_len)
                        #logger.warning(f"cut_len={cut_len}, tmp={tmp}")

                    if chat_type in ["chatgpt", "zhipu"]:
                        # logger.info(chunk)
                        # Special handling for the Zhipu agent
                        if chat_type == "zhipu" and My_handle.config.get("zhipu", "model") == "Agent":
                            decoded_line = chunk.decode('utf-8')
                            if decoded_line.startswith('data:'):
                                data_dict = json.loads(decoded_line[5:])
                                status = data_dict.get("status")
                                if len(status) > 0 and status == "finish":
                                    resp_json['ret'] = True
                                    tmp, cut_len = tmp_handle(resp_json, tmp, cut_len)

                                    logger.info(f"[{chat_type}] Streaming reception complete")
                                    break
                        else:
                            if chunk.choices[0].finish_reason == "stop":
                                if not resp_json['ret']:
                                    resp_json['ret'] = True
                                    tmp, cut_len = tmp_handle(resp_json, tmp, cut_len)

                                logger.info(f"[{chat_type}] Streaming reception complete")
                                break
                    elif chat_type in ["tongyi"]:
                        if chunk.output.choices[0].finish_reason == "stop":
                            if not resp_json['ret']:
                                resp_json['ret'] = True
                                tmp, cut_len = tmp_handle(resp_json, tmp, cut_len)

                            logger.info(f"[{chat_type}] Streaming reception complete")
                            break


            # Return is empty, trigger an exception alert
            else:
                self.abnormal_alarm_handle("llm")
                logger.warning("LLMData was not returned correctly, please check whether the config, network, etc. are normal. If everything checks out, it may be a compatibility issue caused by an API change; you can go to the official repository and submit an issue, link:https://github.com/Ikaros-521/AI-Vtuber/issues")
            
            # Whether to enable webui echo
            if webui_show:
                # Strip useless leading spaces and newlines from the resp_content string
                resp_content = resp_content.lstrip()

                self.webui_show_chat_log_callback(chat_type, data, resp_content)

            # Add the return to the context memory
            if type == "chat":
                # TODO: compatible with more streamingLLM
                # New streaming LLMs need to be added here
                chat_model_methods = {
                    "chatgpt": lambda: self.chatgpt.add_assistant_msg_to_session(data["username"], resp_content),
                    "zhipu": lambda: self.zhipu.add_assistant_msg_to_session(content_bak, resp_content),
                    "tongyi": lambda: self.tongyi.add_assistant_msg_to_session(content_bak, resp_content),
                    "tongyixingchen": lambda: self.tongyixingchen.add_assistant_msg_to_session(content_bak, resp_content),
                    "my_wenxinworkshop": lambda: self.my_wenxinworkshop.add_assistant_msg_to_session(content_bak, resp_content),
                    "volcengine": lambda: self.volcengine.add_assistant_msg_to_session(content_bak, resp_content),
                }
            elif type == "vision":
                pass

            # Use a dict mapping to get the response content
            func = chat_model_methods.get(chat_type, resp_content)

            if callable(func):
                # If func is a callable (function), execute it
                resp = func()
            elif isinstance(func, str):
                # If func is a string, skip execution
                pass
            else:
                # If func is neither a function nor a string, handle other cases
                pass

            return resp_content
        except Exception as e:
            logger.error(traceback.format_exc())

        return None

    # Points handling
    def integral_handle(self, type, data):
        """Points handling

        Args:
            type (str): Message data type (comment/gift/entrance)
            data (dict): The data passed in from the platform side, parsed directly

        Returns:
            bool: Whether the points event was triggered normally; True if yes, otherwiseFalse
        """
        username = data["username"]
        
        if My_handle.config.get("integral", "enable"):
            # Handle according to the message type
            if "comment" == type:
                content = data["content"]

                # Whether the check-in feature is enabled
                if My_handle.config.get("integral", "sign", "enable"):
                    # Check whether the danmaku content is a command
                    if content in My_handle.config.get("integral", "sign", "cmd"):
                        # Check whether the database has a points record for the current user (a UID is missing)
                        common_sql = '''
                        SELECT * FROM integral WHERE username =?
                        '''
                        integral_data = self.db.fetch_all(common_sql, (username,))

                        logger.debug(f"integral_data={integral_data}")

                        # Get the copywriting and synthesize speech; the number of check-in days is passed in for automatic lookup
                        def get_copywriting_and_audio_synthesis(sign_num):
                            # Determine which check-in count range the current number of check-in days falls in, and provide a different copywriting reply for each range
                            for integral_sign_copywriting in My_handle.config.get("integral", "sign", "copywriting"):
                                # Within this range, so your config must be correct, otherwise it will crash here!!!
                                if int(integral_sign_copywriting["sign_num_interval"].split("-")[0]) <= \
                                    sign_num <= \
                                    int(integral_sign_copywriting["sign_num_interval"].split("-")[1]):
                                    # Match copywriting
                                    resp_content = random.choice(integral_sign_copywriting["copywriting"])
                                    
                                    logger.debug(f"resp_content={resp_content}")

                                    data_json = {
                                        "username": data["username"],
                                        "get_integral": int(My_handle.config.get("integral", "sign", "get_integral")),
                                        "sign_num": sign_num + 1
                                    } 

                                    resp_content = My_handle.common.dynamic_variable_replacement(resp_content, data_json)
                                    
                                    # Bracket syntax replacement
                                    resp_content = My_handle.common.brackets_text_randomize(resp_content)
                                    
                                    # Generate the reply content
                                    message = {
                                        "type": "integral",
                                        "tts_type": My_handle.config.get("audio_synthesis_type"),
                                        "data": My_handle.config.get(My_handle.config.get("audio_synthesis_type")),
                                        "config": My_handle.config.get("filter"),
                                        "username": username,
                                        "content": resp_content
                                    }

                                    # Luoxi Live Danmaku Assistant
                                    if My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "enable") and \
                                        "integral" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "type") and \
                                        "On message created" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "trigger_position"):
                                        asyncio.run(send_msg_to_live_comment_assistant(My_handle.config.get("luoxi_project", "Live_Comment_Assistant"), resp_content))
                                    
                                    self.audio_synthesis_handle(message)

                        if integral_data == []:
                            # The user does not exist in the points table, insert the data
                            insert_data_sql = '''
                            INSERT INTO integral (platform, username, uid, integral, view_num, sign_num, last_sign_ts, total_price, last_ts) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            '''
                            self.db.execute(insert_data_sql, (
                                data["platform"], 
                                username, 
                                username, 
                                My_handle.config.get("integral", "sign", "get_integral"), 
                                1,
                                1,
                                datetime.now(),
                                0,
                                datetime.now())
                            )

                            logger.info(f"integralPoints table add user:{username}")

                            get_copywriting_and_audio_synthesis(0)

                            return True
                        else:
                            integral_data = integral_data[0]
                            # The user exists in the points table, update the data

                            # First check whether last_sign_ts is today; if so, the user has already checked in and cannot check in again
                            # Get the date-time string field; this is a pitfall: once the database structure or the select statement changes, there will be knock-on effects!!!
                            date_string = integral_data[6]

                            # Get the date part (first 10 characters) and compare it with the current date string
                            if date_string[:10] == datetime.now().date().strftime("%Y-%m-%d"):
                                resp_content = f"{username}you have already checked in today, no double check-ins~"
                                message = {
                                    "type": "integral",
                                    "tts_type": My_handle.config.get("audio_synthesis_type"),
                                    "data": My_handle.config.get(My_handle.config.get("audio_synthesis_type")),
                                    "config": My_handle.config.get("filter"),
                                    "username": username,
                                    "content": resp_content
                                }

                                # Luoxi Live Danmaku Assistant
                                if My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "enable") and \
                                    "integral" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "type") and \
                                    "On message created" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "trigger_position"):
                                    asyncio.run(send_msg_to_live_comment_assistant(My_handle.config.get("luoxi_project", "Live_Comment_Assistant"), resp_content))
                                
                                self.audio_synthesis_handle(message)

                                return True

                            # Update the user data
                            update_data_sql = '''
                            UPDATE integral SET integral=?, view_num=?, sign_num=?, last_sign_ts=?, last_ts=? WHERE username =?
                            '''
                            self.db.execute(update_data_sql, (
                                # This is a pitfall: once the database structure or the select statement changes, there will be knock-on effects!!!
                                integral_data[3] + My_handle.config.get("integral", "sign", "get_integral"), 
                                integral_data[4] + 1,
                                integral_data[5] + 1,
                                datetime.now(),
                                datetime.now(),
                                username
                                )
                            )

                            logger.info(f"integralPoints table update user:{username}")

                            get_copywriting_and_audio_synthesis(integral_data[5] + 1)

                            return True
            elif "gift" == type:
                # Whether the gift feature is enabled
                if My_handle.config.get("integral", "gift", "enable"):
                    # Check whether the database has a points record for the current user (a UID is missing)
                    common_sql = '''
                    SELECT * FROM integral WHERE username =?
                    '''
                    integral_data = self.db.fetch_all(common_sql, (username,))

                    logger.debug(f"integral_data={integral_data}")

                    get_integral = int(float(My_handle.config.get("integral", "gift", "get_integral_proportion")) * data["total_price"])

                    # Get the copywriting and synthesize speech; the total gift amount is passed in for automatic lookup
                    def get_copywriting_and_audio_synthesis(total_price):
                        # Determine which gift amount range the current gift amount falls in, and provide a different copywriting reply for each range
                        for integral_gift_copywriting in My_handle.config.get("integral", "gift", "copywriting"):
                            # Within this range, so your config must be correct, otherwise it will crash here!!!
                            if float(integral_gift_copywriting["gift_price_interval"].split("-")[0]) <= \
                                total_price <= \
                                float(integral_gift_copywriting["gift_price_interval"].split("-")[1]):
                                # Match copywriting
                                resp_content = random.choice(integral_gift_copywriting["copywriting"])
                                
                                logger.debug(f"resp_content={resp_content}")

                                data_json = {
                                    "username": data["username"],
                                    "gift_name": data["gift_name"],
                                    "get_integral": get_integral,
                                    'gift_num': data["num"],
                                    'unit_price': data["unit_price"],
                                    'total_price': data["total_price"],
                                    'cur_time': My_handle.common.get_bj_time(5),
                                } 

                                # Bracket syntax replacement
                                resp_content = My_handle.common.brackets_text_randomize(resp_content)

                                # Dynamic variable replacement
                                resp_content = My_handle.common.dynamic_variable_replacement(resp_content, data_json)
                                
                                # Generate the reply content
                                message = {
                                    "type": "integral",
                                    "tts_type": My_handle.config.get("audio_synthesis_type"),
                                    "data": My_handle.config.get(My_handle.config.get("audio_synthesis_type")),
                                    "config": My_handle.config.get("filter"),
                                    "username": username,
                                    "content": resp_content
                                }

                                # Luoxi Live Danmaku Assistant
                                if My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "enable") and \
                                    "integral" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "type") and \
                                    "On message created" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "trigger_position"):
                                    asyncio.run(send_msg_to_live_comment_assistant(My_handle.config.get("luoxi_project", "Live_Comment_Assistant"), resp_content))
                                

                                self.audio_synthesis_handle(message)

                    # TODO: there is a calculation bug here!!! The total gift value is calculated incorrectly, to be optimized later
                    if integral_data == []:
                        # The user does not exist in the points table, insert the data
                        insert_data_sql = '''
                        INSERT INTO integral (platform, username, uid, integral, view_num, sign_num, last_sign_ts, total_price, last_ts) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        '''
                        self.db.execute(insert_data_sql, (
                            data["platform"], 
                            username, 
                            username, 
                            get_integral, 
                            1,
                            1,
                            datetime.now(),
                            data["total_price"],
                            datetime.now())
                        )

                        logger.info(f"integralPoints table add user:{username}")

                        get_copywriting_and_audio_synthesis(data["total_price"])

                        return True
                    else:
                        integral_data = integral_data[0]
                        # The user exists in the points table, update the data

                        # Update the user data
                        update_data_sql = '''
                        UPDATE integral SET integral=?, total_price=?, last_ts=? WHERE username =?
                        '''
                        self.db.execute(update_data_sql, (
                            # This is a pitfall: once the database structure or the select statement changes, there will be knock-on effects!!!
                            integral_data[3] + get_integral, 
                            integral_data[7] + data["total_price"],
                            datetime.now(),
                            username
                            )
                        )

                        logger.info(f"integralPoints table update user:{username}")

                        get_copywriting_and_audio_synthesis(data["total_price"])

                        return True
            elif "entrance" == type:
                # Whether the entrance feature is enabled
                if My_handle.config.get("integral", "entrance", "enable"):
                    # Check whether the database has a points record for the current user (a UID is missing)
                    common_sql = '''
                    SELECT * FROM integral WHERE username =?
                    '''
                    integral_data = self.db.fetch_all(common_sql, (username,))

                    logger.debug(f"integral_data={integral_data}")

                    # Get the copywriting and synthesize speech; the number of viewing days is passed in for automatic lookup
                    def get_copywriting_and_audio_synthesis(view_num):
                        # Determine which check-in count range the current number of check-in days falls in, and provide a different copywriting reply for each range
                        for integral_entrance_copywriting in My_handle.config.get("integral", "entrance", "copywriting"):
                            # Within this range, so your config must be correct, otherwise it will crash here!!!
                            if int(integral_entrance_copywriting["entrance_num_interval"].split("-")[0]) <= \
                                view_num <= \
                                int(integral_entrance_copywriting["entrance_num_interval"].split("-")[1]):

                                if len(integral_entrance_copywriting["copywriting"]) <= 0:
                                    return False

                                # Match copywriting
                                resp_content = random.choice(integral_entrance_copywriting["copywriting"])
                                
                                logger.debug(f"resp_content={resp_content}")

                                data_json = {
                                    "username": data["username"],
                                    "get_integral": int(My_handle.config.get("integral", "entrance", "get_integral")),
                                    "entrance_num": view_num + 1
                                } 

                                resp_content = My_handle.common.dynamic_variable_replacement(resp_content, data_json)
                                
                                # Bracket syntax replacement
                                resp_content = My_handle.common.brackets_text_randomize(resp_content)

                                # Generate the reply content
                                message = {
                                    "type": "integral",
                                    "tts_type": My_handle.config.get("audio_synthesis_type"),
                                    "data": My_handle.config.get(My_handle.config.get("audio_synthesis_type")),
                                    "config": My_handle.config.get("filter"),
                                    "username": username,
                                    "content": resp_content
                                }

                                # Luoxi Live Danmaku Assistant
                                if My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "enable") and \
                                    "integral" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "type") and \
                                    "On message created" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "trigger_position"):
                                    asyncio.run(send_msg_to_live_comment_assistant(My_handle.config.get("luoxi_project", "Live_Comment_Assistant"), resp_content))
                                
                                
                                self.audio_synthesis_handle(message)

                    if integral_data == []:
                        # The user does not exist in the points table, insert the data
                        insert_data_sql = '''
                        INSERT INTO integral (platform, username, uid, integral, view_num, sign_num, last_sign_ts, total_price, last_ts) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        '''
                        self.db.execute(insert_data_sql, (
                            data["platform"], 
                            username, 
                            username, 
                            My_handle.config.get("integral", "entrance", "get_integral"), 
                            1,
                            0,
                            datetime.now(),
                            0,
                            datetime.now())
                        )

                        logger.info(f"integralPoints table add user:{username}")

                        get_copywriting_and_audio_synthesis(1)

                        return True
                    else:
                        integral_data = integral_data[0]
                        # The user exists in the points table, update the data

                        # First check whether last_ts is today; if so, it has already been viewed and cannot be recorded again
                        # Get the date-time string field; this is a pitfall: once the database structure or the select statement changes, there will be knock-on effects!!!
                        date_string = integral_data[8]

                        # Get the date part (first 10 characters) and compare it with the current date string
                        if date_string[:10] == datetime.now().date().strftime("%Y-%m-%d"):
                            return False

                        # Update the user data
                        update_data_sql = '''
                        UPDATE integral SET integral=?, view_num=?, last_ts=? WHERE username =?
                        '''
                        self.db.execute(update_data_sql, (
                            # This is a pitfall: once the database structure or the select statement changes, there will be knock-on effects!!!
                            integral_data[3] + My_handle.config.get("integral", "entrance", "get_integral"), 
                            integral_data[4] + 1,
                            datetime.now(),
                            username
                            )
                        )

                        logger.info(f"integralPoints table update user:{username}")

                        get_copywriting_and_audio_synthesis(integral_data[4] + 1)

                        return True
            elif "crud" == type:
                content = data["content"]
                
                # Whether the query feature is enabled
                if My_handle.config.get("integral", "crud", "query", "enable"):
                    # Check whether the danmaku content is a command
                    if content in My_handle.config.get("integral", "crud", "query", "cmd"):
                        # Check whether the database has a points record for the current user (a UID is missing)
                        common_sql = '''
                        SELECT * FROM integral WHERE username =?
                        '''
                        integral_data = self.db.fetch_all(common_sql, (username,))

                        logger.debug(f"integral_data={integral_data}")

                        # Get the copywriting and synthesize speech; the total points are passed in for automatic lookup
                        def get_copywriting_and_audio_synthesis(total_integral):
                            # Match copywriting
                            resp_content = random.choice(My_handle.config.get("integral", "crud", "query", "copywriting"))
                            
                            logger.debug(f"resp_content={resp_content}")

                            data_json = {
                                "username": data["username"],
                                "integral": total_integral
                            }

                            resp_content = My_handle.common.dynamic_variable_replacement(resp_content, data_json)

                            # If the points are 0, return a reply for having no points. This is basically impossible, unless there isbug
                            if total_integral == 0:
                                resp_content = data["username"] + ", no points found for you."
                            
                            # Bracket syntax replacement
                            resp_content = My_handle.common.brackets_text_randomize(resp_content)

                            # Generate the reply content
                            message = {
                                "type": "integral",
                                "tts_type": My_handle.config.get("audio_synthesis_type"),
                                "data": My_handle.config.get(My_handle.config.get("audio_synthesis_type")),
                                "config": My_handle.config.get("filter"),
                                "username": username,
                                "content": resp_content
                            }

                            # Luoxi Live Danmaku Assistant
                            if My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "enable") and \
                                "integral" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "type") and \
                                "On message created" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "trigger_position"):
                                asyncio.run(send_msg_to_live_comment_assistant(My_handle.config.get("luoxi_project", "Live_Comment_Assistant"), resp_content))
                            
                            
                            self.audio_synthesis_handle(message)

                        if integral_data == []:
                            logger.info(f"integralPoints table user not found:{username}")

                            get_copywriting_and_audio_synthesis(0)

                            return True
                        else:
                            integral_data = integral_data[0]
                            # The user exists in the points table

                            # Get the date-time string field; this is a pitfall: once the database structure or the select statement changes, there will be knock-on effects!!!
                            date_string = integral_data[3]

                            logger.info(f"integralPoints table user: {username}, total points:{date_string}")

                            get_copywriting_and_audio_synthesis(int(date_string))

                            return True
        return False


    # Key mapping handling
    def key_mapping_handle(self, type, data):
        """Key mapping handling

        Args:
            type (str): Data source type (danmaku/reply)
            data (dict): The data passed in from the platform side, parsed directly

        Returns:
            bool: Whether the key mapping event was triggered normally; True if yes, otherwiseFalse
        """
        flag = False

        # Get one copywriting and pass it to the audio synthesis function for audio synthesis
        def get_a_copywriting_and_audio_synthesis(key_mapping_config, data):
            try:
                # Randomly get a copywriting
                tmp = random.choice(key_mapping_config["copywriting"])

                # Bracket syntax replacement
                tmp = My_handle.common.brackets_text_randomize(tmp)
                
                # Dynamic variable replacement
                data_json = {
                    "username": data["username"],
                    "gift_name": data["gift_name"],
                    'gift_num': data["num"],
                    'unit_price': data["unit_price"],
                    'total_price': data["total_price"],
                    'cur_time': My_handle.common.get_bj_time(5),
                } 
                tmp = My_handle.common.dynamic_variable_replacement(tmp, data_json)

                # Important data needed for audio synthesis
                message = {
                    "type": "key_mapping",
                    "tts_type": My_handle.config.get("audio_synthesis_type"),
                    "data": My_handle.config.get(My_handle.config.get("audio_synthesis_type")),
                    "config": My_handle.config.get("filter"),
                    "username": data["username"],
                    "content": tmp
                }

                logger.info(f'[Trigger key mapping] Trigger copywriting:{tmp}')

                # Luoxi Live Danmaku Assistant
                if My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "enable") and \
                    "key_mapping_copywriting" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "type") and \
                    "On message created" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "trigger_position"):
                    asyncio.run(send_msg_to_live_comment_assistant(My_handle.config.get("luoxi_project", "Live_Comment_Assistant"), tmp))

                # TODO: Forwarding during playback is not implemented because the type definition is not that fine-grained
                self.audio_synthesis_handle(message)
            except Exception as e:
                logger.error(traceback.format_exc())

        # Get one local audio file and pass it to the audio synthesis function for audio playback
        def get_a_local_audio_and_audio_play(key_mapping_config, data):
            try:
                # Randomly get a copywriting
                if len(key_mapping_config["local_audio"]) <= 0:
                    return
                
                tmp = random.choice(key_mapping_config["local_audio"])

                # Important data needed for audio synthesis
                message = {
                    "type": "key_mapping",
                    "tts_type": My_handle.config.get("audio_synthesis_type"),
                    "data": My_handle.config.get(My_handle.config.get("audio_synthesis_type")),
                    "config": My_handle.config.get("filter"),
                    "username": data["username"],
                    "content": tmp,
                    "file_path": tmp
                }

                logger.info(f'[Trigger mapping] Play local audio:{tmp}')

                self.audio_synthesis_handle(message)
            except Exception as e:
                logger.error(traceback.format_exc())

        # Randomly pick a serial port to send data, content
        def get_a_serial_send_data_and_send(key_mapping_config, data):
            try:
                async def connect_serial_and_send_data(serial_name, baudrate, serial_data_type, data):
                    from utils.serial_manager_instance import get_serial_manager

                    serial_manager = get_serial_manager()
                    # Close the serial port; a singleton is useless here, ugh
                    # resp_json = await serial_manager.disconnect(serial_name)
                    # Open the serial port
                    resp_json = await serial_manager.connect(serial_name, int(baudrate))
                
                    # Send data to the serial port
                    resp_json = await serial_manager.send_data(serial_name, tmp, serial_data_type)

                    return resp_json
                    
                # Randomly get a copywriting
                tmp = random.choice(key_mapping_config["serial_send_data"])

                # Bracket syntax replacement
                tmp = My_handle.common.brackets_text_randomize(tmp)
                
                # Dynamic variable replacement
                data_json = {
                    "username": data.get("username", ""),
                    "gift_name": data.get("gift_name", ""),
                    "gift_num": data.get("num", ""),
                    "unit_price": data.get("unit_price", ""),
                    "total_price": data.get("total_price", ""),
                    "cur_time": My_handle.common.get_bj_time(5),
                }
                tmp = My_handle.common.dynamic_variable_replacement(tmp, data_json)

                # Define a function to get the corresponding config by serial_name
                def get_serial_config(serial_name: str):
                    for config in My_handle.config.get("serial", "config"):
                        if config["serial_name"] == serial_name:
                            return config
                    return None  # If no matching serial_name is found, return None

                serial_name = key_mapping_config["serial_name"]
                tmp_config = get_serial_config(serial_name)
                if tmp_config:
                    baudrate = tmp_config["baudrate"]
                    resp_json = asyncio.run(connect_serial_and_send_data(serial_name, baudrate, tmp_config["serial_data_type"], data))
                    
                    logger.info(f'[Trigger key mapping] Trigger serial port: {tmp},{resp_json["msg"]}')

                    return tmp
                
                logger.error(f"Failed to get the configuration of serial port name: {serial_name}, please go to the serial port page and check that the configuration is correct!")
            
                return None
            except Exception as e:
                logger.error(traceback.format_exc())
                return None

        # Get one local image path and pass it to the virtual camera for display
        def get_a_img_path_and_send(key_mapping_config, data):
            try:
                # Randomly get an image path
                if len(key_mapping_config["img_path"]) <= 0:
                    return
                
                tmp = random.choice(key_mapping_config["img_path"])

                self.sd.set_new_img(tmp)
            except Exception as e:
                logger.error(traceback.format_exc())


        try:
            import pyautogui

            # Content triggered by keywords is handled uniformly in this function
            def keyword_handle_trigger(trigger_type, keyword, key_mapping_config, data, flag):
                try:
                    if My_handle.config.get("key_mapping", trigger_type) in ["Keywords", "Keywords + Gift"]:
                        if trigger_type == "key_trigger_type":
                            logger.info(f'[Trigger key mapping] Keyword: {keyword} Key:{key_mapping_config["keys"]}')
                            for key in key_mapping_config["keys"]:
                                pyautogui.keyDown(key)
                            for key in key_mapping_config["keys"]:
                                pyautogui.keyUp(key)
                        elif trigger_type == "copywriting_trigger_type":
                            logger.info(f'[Trigger key mapping] Keyword: {keyword} , trigger copywriting')
                            get_a_copywriting_and_audio_synthesis(key_mapping_config, data)
                        elif trigger_type == "local_audio_trigger_type":
                            logger.info(f'[Trigger key mapping] Keyword: {keyword} , trigger local audio')
                            get_a_local_audio_and_audio_play(key_mapping_config, data)
                        elif trigger_type == "serial_trigger_type":
                            logger.info(f'[Trigger key mapping] Keyword: {keyword} , trigger serial port')
                            get_a_serial_send_data_and_send(key_mapping_config, data)
                        elif trigger_type == "img_path_trigger_type":
                            logger.info(f'[Trigger key mapping] Keyword: {keyword} , trigger image')
                            get_a_img_path_and_send(key_mapping_config, data)
                        
                        flag = True
                        
                    single_sentence_trigger_once_enable = My_handle.config.get("key_mapping", f"{trigger_type.split('_')[0]}_single_sentence_trigger_once_enable")
                    return {"trigger_once_enable": single_sentence_trigger_once_enable, "flag": flag}
                except Exception as e:
                    logger.error(f"[Trigger key mapping] Exception:{e}")
                    return {"trigger_once_enable": False, "flag": False}
                
            
            # Content triggered by gifts is handled uniformly in this function
            def gift_handle_trigger(trigger_type, gift_name, key_mapping_config, data, flag):
                try:
                    if My_handle.config.get("key_mapping", trigger_type) in ["Gift", "Keywords + Gift"]:
                        if trigger_type == "key_trigger_type":
                            logger.info(f'[Trigger key mapping] Gift: {gift_name} Key:{key_mapping_config["keys"]}')
                            for key in key_mapping_config["keys"]:
                                pyautogui.keyDown(key)
                            for key in key_mapping_config["keys"]:
                                pyautogui.keyUp(key)
                        elif trigger_type == "copywriting_trigger_type":
                            logger.info(f'[Trigger key mapping] Gift: {gift_name} , trigger copywriting')
                            get_a_copywriting_and_audio_synthesis(key_mapping_config, data)
                        elif trigger_type == "local_audio_trigger_type":
                            logger.info(f'[Trigger key mapping] Gift: {gift_name} , trigger local audio')
                            get_a_local_audio_and_audio_play(key_mapping_config, data)
                        elif trigger_type == "serial_trigger_type":
                            logger.info(f'[Trigger key mapping] Gift: {gift_name} , trigger serial port')
                            get_a_serial_send_data_and_send(key_mapping_config, data)
                        elif trigger_type == "img_path_trigger_type":
                            logger.info(f'[Trigger key mapping] Gift: {gift_name} , trigger image')
                            get_a_img_path_and_send(key_mapping_config, data)

                        flag = True
                        
                    single_sentence_trigger_once_enable = My_handle.config.get("key_mapping", f"{trigger_type.split('_')[0]}_single_sentence_trigger_once_enable")
                    return {"trigger_once_enable": single_sentence_trigger_once_enable, "flag": flag}
                except Exception as e:
                    logger.error(f"[Trigger key mapping] Exception:{e}")
                    return {"trigger_once_enable": False, "flag": False}
            
            # Official documentation:https://pyautogui.readthedocs.io/en/latest/keyboard.html#keyboard-keys
            if My_handle.config.get("key_mapping", "enable"):
                # Check whether the incoming data contains the gift_name key; if so, it is gift data
                if "gift_name" in data:
                    # Get all config data of key_mapping
                    key_mapping_configs = My_handle.config.get("key_mapping", "config")

                    # Iteratekey_mapping_configs
                    for key_mapping_config in key_mapping_configs:
                        # Iterate over all gift names in a single config
                        for gift in key_mapping_config["gift"]:
                            # Check whether the gift names are the same
                            if gift == data["gift_name"]:
                                """
                                Different trigger types each get an independent execution check
                                """

                                for trigger in ["key_trigger_type", "copywriting_trigger_type", "local_audio_trigger_type", "serial_trigger_type"]:
                                    resp_json = gift_handle_trigger(trigger, gift, key_mapping_config, data, flag)
                                    if resp_json["trigger_once_enable"]:
                                        return resp_json["flag"]  
                else:
                    content = data["content"]
                    # Check whether the command header matches
                    start_cmd = My_handle.config.get("key_mapping", "start_cmd")
                    if start_cmd != "" and content.startswith(start_cmd):
                        # Remove the command header
                        content = content[len(start_cmd):]

                    key_mapping_configs = My_handle.config.get("key_mapping", "config")
                    
                    for key_mapping_config in key_mapping_configs:
                        similarity = float(key_mapping_config["similarity"])
                        for keyword in key_mapping_config["keywords"]:
                            if type == "Comment":
                                # Determine similarity
                                ratio = difflib.SequenceMatcher(None, content, keyword).ratio()
                                if ratio >= similarity:
                                    """
                                    Different trigger types each get an independent execution check
                                    """
                                    
                                    for trigger in ["key_trigger_type", "copywriting_trigger_type", "local_audio_trigger_type", "serial_trigger_type", \
                                                    "img_path_trigger_type"]:
                                        resp_json = keyword_handle_trigger(trigger, keyword, key_mapping_config, data, flag)
                                        if resp_json["trigger_once_enable"]:
                                            return resp_json["flag"]  
                                        
                            elif type == "Reply":
                                logger.debug(f"keyword={keyword}, content={content}")
                                if keyword in content:
                                    for trigger in ["key_trigger_type", "copywriting_trigger_type", "local_audio_trigger_type", "serial_trigger_type", \
                                                    "img_path_trigger_type"]:
                                        resp_json = keyword_handle_trigger(trigger, keyword, key_mapping_config, data, flag)
                                        if resp_json["trigger_once_enable"]:
                                            return resp_json["flag"]
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(f'[Trigger key mapping] Error:{e}')

        return flag


    # Custom command handling
    def custom_cmd_handle(self, type, data):
        """Custom command handling

        Args:
            type (str): Data source type (danmaku/reply)
            data (dict): The data passed in from the platform side, parsed directly

        Returns:
            bool: Whether the custom command event was triggered normally; True if yes, otherwiseFalse
        """
        flag = False


        try:
            if My_handle.config.get("custom_cmd", "enable"):
                # Check whether the incoming data contains the gift_name key; if so, it is gift data
                if "gift_name" in data:
                    pass
                else:
                    username = data["username"]
                    content = data["content"]
                    custom_cmd_configs = My_handle.config.get("custom_cmd", "config")

                    for custom_cmd_config in custom_cmd_configs:
                        similarity = float(custom_cmd_config["similarity"])
                        for keyword in custom_cmd_config["keywords"]:
                            if type == "Comment":
                                # Determine similarity
                                ratio = difflib.SequenceMatcher(None, content, keyword).ratio()
                                if ratio >= similarity:
                                    resp = My_handle.common.send_request(
                                        custom_cmd_config["api_url"], 
                                        custom_cmd_config["api_type"],
                                        resp_data_type=custom_cmd_config["resp_data_type"]
                                    )

                                    # Use eval() to execute a string expression and get the result
                                    resp_content = eval(custom_cmd_config["data_analysis"])

                                    # Replace newlines in the string with periods
                                    resp_content = resp_content.replace('\n', '。')

                                    logger.debug(f"resp_content={resp_content}")

                                    # Banned word handling
                                    resp_content = self.prohibitions_handle(resp_content, scope="output")
                                    if resp_content is None:
                                        return flag

                                    variables = {
                                        'keyword': keyword,
                                        'cur_time': My_handle.common.get_bj_time(5),
                                        'username': username,
                                        'data': resp_content
                                    }

                                    tmp = custom_cmd_config["resp_template"]

                                    # Use a dictionary for string replacement
                                    if any(var in tmp for var in variables):
                                        resp_content = tmp.format(**{var: value for var, value in variables.items() if var in tmp})
                                    
                                    # Important data needed for audio synthesis
                                    message = {
                                        "type": "reread",
                                        "tts_type": My_handle.config.get("audio_synthesis_type"),
                                        "data": My_handle.config.get(My_handle.config.get("audio_synthesis_type")),
                                        "config": My_handle.config.get("filter"),
                                        "username": username,
                                        "content": resp_content
                                    }

                                    logger.debug(message)
                                    
                                    logger.info(f'[Trigger custom command] Keyword: {keyword} Returned content:{resp_content}')

                                    self.audio_synthesis_handle(message)

                                    self.webui_show_chat_log_callback("Custom commands", data, resp_content)

                                    flag = True
                                    
                            
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(f'[Trigger custom command] Error:{e}')

        return flag


    # Blacklist handling
    def blacklist_handle(self, data):
        """Blacklist handling

        Args:
            data (dict): Contains the username and danmaku content

        Returns:
            bool: TrueTrue means a blacklisted user, False means not a blacklisted user
        """
        try:
            if My_handle.config.get("filter", "blacklist", "enable"):
                username_blacklist = My_handle.config.get("filter", "blacklist", "username")
                if len(username_blacklist) == 0:
                    return False
                
                if data["username"] in username_blacklist:
                    logger.info(f'Danmaku blacklist filter, username:{data["username"]}')
                    return True
                
            return False
        except Exception as e:
            logger.error(traceback.format_exc())
            return False

    

    # Check whether the data is duplicated within the specified time period
    def is_data_repeat_in_limited_time(self, type: str=None, data: dict=None):
        """Check whether the data is duplicated within the specified time period

        Args:
            type (str): Data type being checked (comment|gift|entrance)
            data (dict): Contains the username and danmaku content

        Returns:
            dict: JSON data passed to audio synthesis
        """
        if My_handle.config.get("filter", "limited_time_deduplication", "enable"):
            logger.debug(f"Data duplicated within the specified time period My_handle.live_data={My_handle.live_data}")
                        
            if type is not None and type != "" and data is not None:
                if type == "comment":
                    # If there is duplicate data, returnTrue
                    for tmp in My_handle.live_data[type]:
                        if tmp['username'] == data['username'] and tmp['content'] == data['content']:
                            logger.debug(f"Data duplicated within the specified time period type={type},data={data}")
                            return True
                elif type == "gift":
                    # If there is duplicate data, returnTrue
                    for tmp in My_handle.live_data[type]:
                        if tmp['username'] == data['username']:
                            logger.debug(f"Data duplicated within the specified time period type={type},data={data}")
                            return True
                elif type == "entrance":   
                    # If there is duplicate data, returnTrue
                    for tmp in My_handle.live_data[type]:
                        if tmp['username'] == data['username']:
                            logger.debug(f"Data duplicated within the specified time period type={type},data={data}")
                            return True
                
                # Insert if it does not exist, returnFalse
                My_handle.live_data[type].append(data)
        return False

    # Decide whether to run a web search and return the processed result
    def search_online_handle(self, content: str):
        try:
            if My_handle.config.get("search_online", "enable"):
                # Whether keyword commands are enabled
                if My_handle.config.get("search_online", "keyword_enable"):
                    # No keyword hit, return directly
                    if My_handle.config.get("search_online", "before_keyword") and not any(content.startswith(prefix) for prefix in \
                        My_handle.config.get("search_online", "before_keyword")):
                        return content
                    else:
                        for prefix in My_handle.config.get("search_online", "before_keyword"):
                            if content.startswith(prefix):
                                content = content[len(prefix):]  # Delete the matching prefix
                                break
            
                from .search_engine import search_online

                if My_handle.config.get("search_online", "http_proxy") == "" and My_handle.config.get("search_online", "https_proxy") == "":
                    proxies = None
                else:
                    proxies = {
                        "http": My_handle.config.get("search_online", "http_proxy"),
                        "https": My_handle.config.get("search_online", "https_proxy")
                    }
                summaries = search_online(
                    content, 
                    engine=My_handle.config.get("search_online", "engine"), 
                    engine_id=int(My_handle.config.get("search_online", "engine_id")), 
                    count=int(My_handle.config.get("search_online", "count")), 
                    proxies=proxies
                )
                if summaries != []:
                    # Append index number
                    indexed_summaries = [f"Reference {i+1}. {summary}" for i, summary in enumerate(summaries)]
                    
                    # Replace redundant newlines in the content
                    cleaned_summaries = [summary.replace('\n', ' ') for summary in indexed_summaries]

                    variables = {
                        'summary': cleaned_summaries,
                        'cur_time': My_handle.common.get_bj_time(5),
                        'data': content
                    }

                    tmp = My_handle.config.get("search_online", "resp_template")

                    # Use a dictionary for string replacement
                    if any(var in tmp for var in variables):
                        content = tmp.format(**{var: value for var, value in variables.items() if var in tmp})

            return content
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(f"Web search error: {e}")
            return content

    """                                                              
                                                                           
                                                         ,`                
                             @@@@`               =@@\`   /@@/              
                ,/@@] =@@@`  @@@/                 =@@\/@@@@@@@@@[          
           .\@@/[@@@@` ,@@@ =@/.             ,[[[[.=@^ ,@@@@\`             
                *@@^,`  .]]]@@@@@@\`          ,@@@@@@[[[. =@@@@.           
           .]]]]/@@`\@@/ *@@^  =@@@/           ,@@@@@@@@/`@@@`             
            =@@*    .@@@@@@@@/`@@@^             ,@@\]]/@@@@@.              
            =@@      =@@*.@@\]/@@^               ,\@@\   ,]]@@@@]          
          ,/@@@@@@@^  \@/[@@^               .@@@@@@@@@[[[\@\.              
          ,@/. .@@@      .@@\]/@@@@@@`          ,@@@,@@@.,]@@@`            
               .@@/@@@@@/[@@/                  /@@\]@@@@@@@@@@@@@]         
               =@@^      .@@^                ]@@@@@^ @@@  @@@ ,@@@@@@\].   
           ,]]/@@@`      .@@^             ./@/` .@@^.@@@/@@@/              
             \@@@`       .@@^                       .@@@ .[[               
                         .@@`                        @@^                   
                                                                                                                                          

    """

    # Danmaku handling: danmaku messages from the live room are all handled in this function
    def comment_handle(self, data):
        """Danmaku handling: danmaku messages from the live room are all handled in this function

        Args:
            data (dict): Contains the username and danmaku content

        Returns:
            dict: JSON data passed to audio synthesis
        """

        try:
            username = data["username"]
            content = data["content"]

            # Output the danmaku message sent by the current user
            logger.debug(f"[{username}]: {content}")

            # Deduplicate data within the specified time
            if self.is_data_repeat_in_limited_time("comment", data):
                return None

            # Blacklist filtering
            if self.blacklist_handle(data):
                return None

            # Giveaway entries and poll votes are counted silently (no AI reply to a bare "1")
            if self.engage_consume(username, content):
                return None

            # Viewer commands / chapter votes for the Novel and Story readers ("!tiep", "1" / "2"): counted silently, no AI reply
            if self.reader_cmd_consume(username, content):
                return None
            
            # After basic initial filtering, danmaku data can be forwarded through the Luoxi live danmaku assistant.
            # Luoxi Live Danmaku Assistant
            if My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "enable") and \
                "comment" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "type") and \
                "On message created" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "trigger_position"):
                asyncio.run(send_msg_to_live_comment_assistant(My_handle.config.get("luoxi_project", "Live_Comment_Assistant"), content))


            # Chat history returned to the webui
            if My_handle.config.get("talk", "show_chat_log"):
                if "ori_username" not in data:
                    data["ori_username"] = data["username"]
                if "ori_content" not in data:
                    data["ori_content"] = data["content"]
                if "user_face" not in data:
                    data["user_face"] = 'https://robohash.org/ui'

                # Data returned to the webui
                return_webui_json = {
                    "type": "llm",
                    "data": {
                        "type": "Comment message",
                        "username": data["ori_username"],
                        "user_face": data["user_face"],
                        "content_type": "question",
                        "content": data["ori_content"],
                        "timestamp": My_handle.common.get_bj_time(0)
                    }
                }
                webui_ip = "127.0.0.1" if My_handle.config.get("webui", "ip") == "0.0.0.0" else My_handle.config.get("webui", "ip")
                tmp_json = My_handle.common.send_request(f'http://{webui_ip}:{My_handle.config.get("webui", "port")}/callback', "POST", return_webui_json, timeout=10)
            

            # Record database
            if My_handle.config.get("database", "comment_enable"):
                insert_data_sql = '''
                INSERT INTO danmu (username, content, ts) VALUES (?, ?, ?)
                '''
                self.db.execute(insert_data_sql, (username, content, datetime.now()))



            # Merge consecutive * at the end of the string, mainly for cases where the username cannot be obtained
            username = My_handle.common.merge_consecutive_asterisks(username)

            # 0, points mechanism running
            if self.integral_handle("comment", data):
                return
            if self.integral_handle("crud", data):
                return

            """
            The username must also be filtered, to guard against bombers
            """
            # Banned word check on the username and danmaku
            username = self.prohibitions_handle(username)
            if username is None:
                return
            
            content = self.prohibitions_handle(content)
            if content is None:
                return
            
            # Danmaku format check, special character replacement and specified language filtering
            content = self.comment_check_and_replace(content)
            if content is None:
                return
            
            # Check whether the string is all punctuation; if so, filter it out
            if My_handle.common.is_punctuation_string(content):
                logger.debug(f"User: {username}], sent a danmaku of only symbols, filtered")
                return
            
            # Determine the key mapping trigger type
            if My_handle.config.get("key_mapping", "type") == "Comment" or My_handle.config.get("key_mapping", "type") == "Comment + Reply":
                # Key mapping; after it triggers, other later features are not executed
                if self.key_mapping_handle("Comment", data):
                    return
                
            # Determine the custom command trigger type
            if My_handle.config.get("custom_cmd", "type") == "Comment" or My_handle.config.get("custom_cmd", "type") == "Comment + Reply":
                # Custom command; after it triggers, other later features are not executed
                if self.custom_cmd_handle("Comment", data):
                    return
            
            try:
                # Read danmaku
                if My_handle.config.get("read_comment", "enable"):
                    logger.debug(f"Read danmaku content:{content}")

                    # Important data needed for audio synthesis
                    message = {
                        "type": "read_comment",
                        "tts_type": My_handle.config.get("audio_synthesis_type"),
                        "data": My_handle.config.get(My_handle.config.get("audio_synthesis_type")),
                        "config": My_handle.config.get("filter"),
                        "username": username,
                        "content": content
                    }

                    # Decide whether the username needs to be read out
                    if My_handle.config.get("read_comment", "read_username_enable"):
                        # Replace special characters in the username with empty
                        message['username'] = My_handle.common.replace_special_characters(message['username'], "！!@#￥$%^&*_-+/——=()（）【】}|{:;<>~`\\")
                        message['username'] = message['username'][:self.config.get("read_comment", "username_max_len")]

                        # Convert digits in the username string to Chinese numerals
                        if My_handle.config.get("filter", "username_convert_digits_to_chinese"):
                            message["username"] = My_handle.common.convert_digits_to_chinese(message["username"])
                            logger.debug(f"Convert digits in the username string to Chinese:{message['username']}")

                        if len(self.config.get("read_comment", "read_username_copywriting")) > 0:
                            tmp_content = random.choice(self.config.get("read_comment", "read_username_copywriting"))
                            if "{username}" in tmp_content:
                                message['content'] = tmp_content.format(username=message['username']) + message['content']

                    # Whether the periodic trigger feature is enabled; when enabled, data is cached and only triggered when the period arrives
                    if My_handle.config.get("read_comment", "periodic_trigger", "enable"):
                        My_handle.task_data["read_comment"]["data"].append(message)
                    else:
                        self.audio_synthesis_handle(message)
            except Exception as e:
                logger.error(traceback.format_exc())

            # 1, local Q&A library handling
            if self.local_qa_handle(data):
                return

            # 2, song request mode; after it triggers, other later features are not executed
            if self.choose_song_handle(data):
                return

            # 3, drawing mode; after it triggers, other later features are not executed
            if self.sd_handle(data):
                return
            
            # 4, whether to translate the danmaku content
            if My_handle.config.get("translate", "enable") and (My_handle.config.get("translate", "trans_type") == "Comment" or \
                My_handle.config.get("translate", "trans_type") == "Comment + Reply"):
                tmp = My_handle.my_translate.trans(content)
                if tmp:
                    content = tmp
                    # logger.info(f"After translation:{content}")

            # 5, web search
            content = self.search_online_handle(content)

            data_json = {
                "username": username,
                "content": content,
                "ori_username": data["username"],
                "ori_content": data["content"]
            }

            """
            Run different logic depending on the chat type
            """ 
            chat_type = My_handle.config.get("chat_type")
            # Simple factual product questions are answered straight from the catalog (fast, no LLM, nothing invented)
            quick_reply = None
            intent = live_analytics.classify_intent(data["content"])
            matched_product = None
            catalog = self.get_product_catalog()
            if catalog is not None:
                found = catalog.find_relevant(data["content"], 1)
                matched_product = found[0] if found else None
            # Answers the seller taught in the "Teach" tab win over everything else (they are the seller's own words)
            taught_reply = None
            try:
                taught_reply = self._get_taught_book().answer(data["content"], matched_product["id"] if matched_product else None)
            except Exception as e:
                logger.debug(f"taught answers: {e}")
            if taught_reply:
                quick_reply = taught_reply
                logger.info(f"Taught answer: {quick_reply}")
            if not quick_reply and My_handle.config.get("products", "quick_answers") and catalog is not None:
                quick_reply = catalog.quick_answer(data["content"])
                if not quick_reply and intent == "buy" and matched_product:
                    quick_reply = catalog.buy_reply(matched_product)
                if quick_reply:
                    logger.info(f"Quick product answer: {quick_reply}")
            cache_key, cache_hit = None, False
            if not quick_reply and chat_type in self.chat_type_list:
                try:
                    cache_key = answer_cache.make_key(data["content"], matched_product["id"] if matched_product else None,
                                                      self._answer_version())
                    cached = self._get_answer_cache().get(cache_key)
                    if cached:
                        quick_reply, cache_hit = cached, True
                        logger.info(f"Answer cache hit: {quick_reply}")
                except Exception as e:
                    logger.debug(f"answer cache lookup: {e}")
            analytics = self.get_analytics()
            analytics.record("comment", user=username, text=data["content"], intent=intent,
                             product_id=matched_product["id"] if matched_product else None)
            if self.coverage_human():   # the seller is hosting: keep the question for them, say nothing
                analytics.record("handoff", user=username, text=data["content"], intent=intent)
                return None
            analytics.record("answer", source="taught" if taught_reply else ("cache" if cache_hit else ("quick" if quick_reply else "llm")),
                             product_id=matched_product["id"] if matched_product else None)
            if matched_product and intent in live_analytics.SALES_INTENTS:
                self.spotlight_handle(matched_product)

            if quick_reply:
                resp_content = quick_reply
            elif chat_type in self.chat_type_list:
                data_json["content"] = My_handle.config.get("before_prompt")
                # Whether to enable the danmaku template
                if self.config.get("comment_template", "enable"):
                    # Assume there are multiple unknown variables; users can define dynamic variables here
                    variables = {
                        'username': username,
                        'comment': content,
                        'cur_time': My_handle.common.get_bj_time(5),
                    }

                    comment_template_copywriting = self.config.get("comment_template", "copywriting")
                    # Use a dictionary for string replacement
                    if any(var in comment_template_copywriting for var in variables):
                        content = comment_template_copywriting.format(**{var: value for var, value in variables.items() if var in comment_template_copywriting})

                # Product knowledge for questions about the cart items
                catalog = self.get_product_catalog()
                if catalog is not None:
                    product_context = catalog.context_for(data["content"])
                    if product_context:
                        data_json["content"] += (My_handle.config.get("products", "context_prefix") or "") + product_context + "\n"

                data_json["content"] += content + My_handle.config.get("after_prompt")

                logger.debug(f"data_json={data_json}")
                
                # Whether the currently selected LLM type supports stream and it is enabledstream
                if "stream" in self.config.get(chat_type) and self.config.get(chat_type, "stream"):
                    logger.warning("Use streaming inferenceLLM")
                    t0 = time.time()
                    resp_content = self.llm_stream_handle_and_audio_synthesis(chat_type, data_json)
                    analytics.record("latency", ms=int((time.time() - t0) * 1000), source="llm")
                    if not lang_guard.needs_retry(resp_content):
                        self._note_unsure(data["content"], matched_product, resp_content)
                        self._cache_store(cache_key, resp_content, data["username"])
                        return resp_content
                    # everything the model said was dropped by the language guard -> one non-streaming retry
                    logger.warning("Streamed reply was not speakable (wrong language); retrying once")
                    resp_content = self.llm_handle(chat_type, dict(data_json, content=data_json["content"] + lang_guard.RETRY_NOTE, _retried=True))
                    if resp_content is not None:
                        logger.info(f"[AIReply to {username}]:{resp_content}")
                        self._note_unsure(data["content"], matched_product, resp_content)
                    else:
                        resp_content = ""
                        logger.warning(f"Warning: {chat_type} has no return")
                else:
                    t0 = time.time()
                    resp_content = self.llm_handle(chat_type, data_json)
                    analytics.record("latency", ms=int((time.time() - t0) * 1000), source="llm")
                    if resp_content is not None:
                        logger.info(f"[AIReply to {username}]:{resp_content}")
                        self._note_unsure(data["content"], matched_product, resp_content)
                        self._cache_store(cache_key, resp_content, data["username"])
                    else:
                        resp_content = ""
                        logger.warning(f"Warning: {chat_type} has no return")
            elif chat_type == "game":
                if My_handle.config.get("game", "enable"):
                    self.game.parse_keys_and_simulate_keys_press(content.split(), 2)
                return
            elif chat_type == "none":
                return
            elif chat_type == "reread":
                resp_content = self.llm_handle(chat_type, data_json)
            else:
                resp_content = content

            # Empty data, end
            if resp_content == "" or resp_content is None:
                return

            """
            Double filtering to safeguard you
            """
            resp_content = resp_content.strip()

            resp_content = resp_content.replace('\n', '。')
            
            # LLMCheck the reply content for banned words
            resp_content = self.prohibitions_handle(resp_content, scope="output")
            if resp_content is None:
                return

            # logger.info("resp_content=" + resp_content)

            # Whether to translate the reply content
            if My_handle.config.get("translate", "enable") and (My_handle.config.get("translate", "trans_type") == "Reply" or \
                My_handle.config.get("translate", "trans_type") == "Comment + Reply"):
                tmp = My_handle.my_translate.trans(resp_content)
                if tmp:
                    resp_content = tmp

            self.write_to_comment_log(resp_content, {"username": username, "content": content})

            # Determine the key mapping trigger type
            if My_handle.config.get("key_mapping", "type") == "Reply" or My_handle.config.get("key_mapping", "type") == "Comment + Reply":
                # Replacement content
                data["content"] = resp_content
                # Key mapping; after it triggers, other later features are not executed
                if self.key_mapping_handle("Reply", data):
                    pass

            # Determine the custom command trigger type
            if My_handle.config.get("custom_cmd", "type") == "Reply" or My_handle.config.get("custom_cmd", "type") == "Comment + Reply":
                # Replacement content
                data["content"] = resp_content
                # Custom command; after it triggers, other later features are not executed
                if self.custom_cmd_handle("Reply", data):
                    pass
                

            # Important data needed for audio synthesis
            message = {
                "type": "comment",
                "tts_type": My_handle.config.get("audio_synthesis_type"),
                "data": My_handle.config.get(My_handle.config.get("audio_synthesis_type")),
                "config": My_handle.config.get("filter"),
                "username": username,
                "content": resp_content
            }

            # Luoxi Live Danmaku Assistant
            if My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "enable") and \
                "comment_reply" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "type") and \
                "On message created" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "trigger_position"):
                asyncio.run(send_msg_to_live_comment_assistant(My_handle.config.get("luoxi_project", "Live_Comment_Assistant"), resp_content))

            # Synthesize audio
            self.audio_synthesis_handle(message)

            return message
        except Exception as e:
            logger.error(traceback.format_exc())
            return None


    # Gift handling
    def gift_handle(self, data):
        try:
            # Deduplicate data within the specified time
            if self.is_data_repeat_in_limited_time("gift", data):
                return None
            self.get_analytics().record("gift", user=data.get("username"), gift=data.get("gift_name"), num=data.get("num"))
            
            # Record database
            if My_handle.config.get("database", "gift_enable"):
                insert_data_sql = '''
                INSERT INTO gift (username, gift_name, gift_num, unit_price, total_price, ts) VALUES (?, ?, ?, ?, ?, ?)
                '''
                self.db.execute(insert_data_sql, (
                    data['username'], 
                    data['gift_name'], 
                    data['num'], 
                    data['unit_price'], 
                    data['total_price'],
                    datetime.now())
                )

            # Key mapping; after it triggers, other later features are still executed
            self.key_mapping_handle("Comment", data)
            # Custom command trigger
            self.custom_cmd_handle("Comment", data)
            
            # Banned content handling
            data['username'] = self.prohibitions_handle(data['username'])
            if data['username'] is None:
                return None
            
            # Points handling
            if self.integral_handle("gift", data):
                return None

            # Merge consecutive * at the end of the string, mainly for cases where the username cannot be obtained
            data['username'] = My_handle.common.merge_consecutive_asterisks(data['username'])
            # Remove special characters from the username
            data['username'] = My_handle.common.replace_special_characters(data['username'], "！!@#￥$%^&*_-+/——=()（）【】}|{:;<>~`\\")  

            data['username'] = data['username'][:self.config.get("thanks", "username_max_len")]

            # Convert digits in the username string to Chinese numerals
            if My_handle.config.get("filter", "username_convert_digits_to_chinese"):
                data["username"] = My_handle.common.convert_digits_to_chinese(data["username"])

            # logger.debug(f"[{data['username']}]: {data}")
        
            if not My_handle.config.get("thanks")["gift_enable"]:
                return None
            if self.coverage_human():
                return None

            # If the total gift price is below the configured minimum for gift thanks
            if data["total_price"] < My_handle.config.get("thanks")["lowest_price"]:
                return None

            if My_handle.config.get("thanks", "gift_random"):
                resp_content = random.choice(My_handle.config.get("thanks", "gift_copy"))
            else:
                # Check whether the class variable list has data; if not, copy the data and then take the first item in order
                if len(My_handle.thanks_gift_copy) == 0:
                    if len(My_handle.config.get("thanks", "gift_copy")) == 0:
                        logger.warning("You deleted the gift copywriting, so why trigger the gift thanks at all? Just do not enable it, why delete it")
                        return None
                resp_content = My_handle.thanks_gift_copy.pop(0)

            
            # Bracket syntax replacement
            resp_content = My_handle.common.brackets_text_randomize(resp_content)
            
            # Dynamic variable replacement
            data_json = {
                "username": data["username"],
                "gift_name": data["gift_name"],
                'gift_num': data["num"],
                'unit_price': data["unit_price"],
                'total_price': data["total_price"],
                'cur_time': My_handle.common.get_bj_time(5),
                'product': self.current_product_name(),
            } 
            resp_content = My_handle.common.dynamic_variable_replacement(resp_content, data_json)


            message = {
                "type": "gift",
                "tts_type": My_handle.config.get("audio_synthesis_type"),
                "data": My_handle.config.get(My_handle.config.get("audio_synthesis_type")),
                "config": My_handle.config.get("filter"),
                "username": data["username"],
                "content": resp_content,
                "gift_info": data
            }

            # Luoxi Live Danmaku Assistant
            if My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "enable") and \
                "gift_reply" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "type") and \
                "On message created" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "trigger_position"):
                asyncio.run(send_msg_to_live_comment_assistant(My_handle.config.get("luoxi_project", "Live_Comment_Assistant"), resp_content))
            

            # Whether the periodic trigger feature is enabled; when enabled, data is cached and only triggered when the period arrives
            if My_handle.config.get("thanks", "gift", "periodic_trigger", "enable"):
                My_handle.task_data["thanks"]["gift"]["data"].append(message)
            else:
                self.audio_synthesis_handle(message)

            return message
        except Exception as e:
            logger.error(traceback.format_exc())
            return None


    # Entrance handling
    def _get_taught_book(self):
        from utils import setup_wizard, teach
        if getattr(My_handle, "_taught_book", None) is None:
            My_handle._taught_book = teach.TaughtBook(os.path.join(setup_wizard.ROOT, "data", "taught.json"))
        return My_handle._taught_book

    def coverage_human(self):
        """True while the seller has marked these hours as 'I am hosting' (the AI then stays quiet). Re-read every 5 s."""
        try:
            now = time.time()
            cache = self.__dict__.get("_coverage_cache")
            if not cache or now - cache[0] > 5:
                cache = (now, coverage.is_human(coverage.load()))
                self._coverage_cache = cache
            return cache[1]
        except Exception:
            return False

    def _answer_version(self):
        """Changes whenever the seller edits products or the flash sale changes -> cached answers are dropped."""
        parts = []
        for path in (My_handle.config.get("products", "path") or "data/products.json",
                     My_handle.config.get("products", "flash_sale_path") or "data/flash_sale.json"):
            try:
                parts.append(str(int(os.path.getmtime(path))))
            except OSError:
                parts.append("0")
        return "-".join(parts)

    def _get_answer_cache(self):
        if getattr(My_handle, "_answer_cache", None) is None:
            My_handle._answer_cache = answer_cache.AnswerCache()
        return My_handle._answer_cache

    def _cache_store(self, key, reply, username):
        """Remember a good LLM answer so the same question is answered instantly next time."""
        try:
            from utils import teach
            unsure = isinstance(reply, str) and teach.is_unsure(reply)
            if key and answer_cache.cacheable(reply, username, unsure) and not lang_guard.has_cjk(reply):
                self._get_answer_cache().put(key, reply)
        except Exception as e:
            logger.debug(f"answer cache store: {e}")

    def _note_unsure(self, question, product, reply):
        """When the AI admits it does not know, log the question so the seller can teach the answer afterwards."""
        try:
            from utils import teach
            if isinstance(reply, str) and teach.is_unsure(reply):
                self.get_analytics().record("unsure", text=question, product_id=product["id"] if product else None, reply=reply[:200])
        except Exception as e:
            logger.debug(f"note unsure: {e}")

    def _get_viewer_book(self):
        """The returning-viewer book, or None when the seller has not opted in."""
        from utils import returning, setup_wizard
        if not setup_wizard.load_setup().get("returning_viewers"):
            return None
        if getattr(My_handle, "_viewer_book", None) is None:
            My_handle._viewer_book = returning.ViewerBook(os.path.join(setup_wizard.ROOT, "data", "viewers.json"))
        return My_handle._viewer_book

    def entrance_handle(self, data):
        try:
            # Deduplicate data within the specified time
            if self.is_data_repeat_in_limited_time("entrance", data):
                return None
            self.get_analytics().record("entrance", user=data.get("username"))

            # Opt-in "welcome back" (hashed viewer book, off unless the seller enables it in Setup)
            returning_visits = 0
            try:
                book = self._get_viewer_book()
                if book is not None:
                    returning_visits = book.visit(data.get("username") or "")
            except Exception as e:
                logger.debug(f"returning viewers: {e}")
            if self.coverage_human():
                return None

            # Record database
            if My_handle.config.get("database", "entrance_enable"):
                insert_data_sql = '''
                INSERT INTO entrance (username, ts) VALUES (?, ?)
                '''
                self.db.execute(insert_data_sql, (data['username'], datetime.now()))

            # Banned content handling
            data['username'] = self.prohibitions_handle(data['username'])
            if data['username'] is None:
                return None
            
            if self.integral_handle("entrance", data):
                return None

            # Merge consecutive * at the end of the string, mainly for cases where the username cannot be obtained
            data['username'] = My_handle.common.merge_consecutive_asterisks(data['username'])
            # Remove special characters from the username
            data['username'] = My_handle.common.replace_special_characters(data['username'], "！!@#￥$%^&*_-+/——=()（）【】}|{:;<>~`\\")

            data['username'] = data['username'][:self.config.get("thanks", "username_max_len")]

            # Convert digits in the username string to Chinese numerals
            if My_handle.config.get("filter", "username_convert_digits_to_chinese"):
                data["username"] = My_handle.common.convert_digits_to_chinese(data["username"])

            # logger.debug(f"[{data['username']}]: {data['content']}")
        
            if not My_handle.config.get("thanks")["entrance_enable"] and not returning_visits:
                return None

            welcome_back = None
            if returning_visits:
                from utils import returning as _returning
                welcome_back = _returning.greeting(data['username'], returning_visits)

            if welcome_back:
                resp_content = welcome_back
            elif not My_handle.config.get("thanks")["entrance_enable"]:
                return None
            elif My_handle.config.get("thanks", "entrance_random"):
                resp_content = self.thanks_fill(random.choice(My_handle.config.get("thanks", "entrance_copy")), data)
            else:
                # Check whether the class variable list has data; if not, copy the data and then take the first item in order
                if len(My_handle.thanks_entrance_copy) == 0:
                    if len(My_handle.config.get("thanks", "entrance_copy")) == 0:
                        logger.warning("You deleted the entrance copywriting, so why trigger the entrance thanks at all? Just do not enable it, why delete it")
                        return None
                    My_handle.thanks_entrance_copy = copy.copy(My_handle.config.get("thanks", "entrance_copy"))
                resp_content = self.thanks_fill(My_handle.thanks_entrance_copy.pop(0), data)

            # Bracket syntax replacement
            resp_content = My_handle.common.brackets_text_randomize(resp_content)

            message = {
                "type": "entrance",
                "tts_type": My_handle.config.get("audio_synthesis_type"),
                "data": My_handle.config.get(My_handle.config.get("audio_synthesis_type")),
                "config": My_handle.config.get("filter"),
                "username": data['username'],
                "content": resp_content
            }

            # Luoxi Live Danmaku Assistant
            if My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "enable") and \
                "entrance_reply" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "type") and \
                "On message created" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "trigger_position"):
                asyncio.run(send_msg_to_live_comment_assistant(My_handle.config.get("luoxi_project", "Live_Comment_Assistant"), resp_content))
            
            # Whether the periodic trigger feature is enabled; when enabled, data is cached and only triggered when the period arrives
            if My_handle.config.get("thanks", "entrance", "periodic_trigger", "enable"):
                My_handle.task_data["thanks"]["entrance"]["data"].append(message)
            else:
                self.audio_synthesis_handle(message)

            return message
        except Exception as e:
            logger.error(traceback.format_exc())
            return None


    # Follow handling
    def follow_handle(self, data):
        try:
            # Merge consecutive * at the end of the string, mainly for cases where the username cannot be obtained
            data['username'] = My_handle.common.merge_consecutive_asterisks(data['username'])
            # Remove special characters from the username
            data['username'] = My_handle.common.replace_special_characters(data['username'], "！!@#￥$%^&*_-+/——=()（）【】}|{:;<>~`\\")

            data['username'] = data['username'][:self.config.get("thanks", "username_max_len")]

            # Banned content handling
            data['username'] = self.prohibitions_handle(data['username'])
            if data['username'] is None:
                return None

            if self.coverage_human():
                return None

            # Convert digits in the username string to Chinese numerals
            if My_handle.config.get("filter", "username_convert_digits_to_chinese"):
                data["username"] = My_handle.common.convert_digits_to_chinese(data["username"])

            # logger.debug(f"[{data['username']}]: {data['content']}")
        
            if not My_handle.config.get("thanks")["follow_enable"]:
                return None

            if My_handle.config.get("thanks", "follow_random"):
                resp_content = self.thanks_fill(random.choice(My_handle.config.get("thanks", "follow_copy")), data)
            else:
                # Check whether the class variable list has data; if not, copy the data and then take the first item in order
                if len(My_handle.thanks_follow_copy) == 0:
                    if len(My_handle.config.get("thanks", "follow_copy")) == 0:
                        logger.warning("You deleted the follow copywriting, so why trigger the follow thanks at all? Just do not enable it, why delete it")
                        return None
                    My_handle.thanks_follow_copy = copy.copy(My_handle.config.get("thanks", "follow_copy"))
                resp_content = self.thanks_fill(My_handle.thanks_follow_copy.pop(0), data)
            
            # Bracket syntax replacement
            resp_content = My_handle.common.brackets_text_randomize(resp_content)

            message = {
                "type": "follow",
                "tts_type": My_handle.config.get("audio_synthesis_type"),
                "data": My_handle.config.get(My_handle.config.get("audio_synthesis_type")),
                "config": My_handle.config.get("filter"),
                "username": data['username'],
                "content": resp_content
            }

            # Luoxi Live Danmaku Assistant
            if My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "enable") and \
                "follow_reply" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "type") and \
                "On message created" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "trigger_position"):
                asyncio.run(send_msg_to_live_comment_assistant(My_handle.config.get("luoxi_project", "Live_Comment_Assistant"), resp_content))
            

            # Whether the periodic trigger feature is enabled; when enabled, data is cached and only triggered when the period arrives
            if My_handle.config.get("thanks", "follow", "periodic_trigger", "enable"):
                My_handle.task_data["thanks"]["follow"]["data"].append(message)
            else:
                self.audio_synthesis_handle(message)

            return message
        except Exception as e:
            logger.error(traceback.format_exc())
            return None

    # Scheduled handling
    def schedule_handle(self, data):
        try:
            content = data["content"]

            message = {
                "type": "schedule",
                "tts_type": My_handle.config.get("audio_synthesis_type"),
                "data": My_handle.config.get(My_handle.config.get("audio_synthesis_type")),
                "config": My_handle.config.get("filter"),
                "username": data['username'],
                "content": content
            }

            # Luoxi Live Danmaku Assistant
            if My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "enable") and \
                "schedule" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "type") and \
                "On message created" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "trigger_position"):
                asyncio.run(send_msg_to_live_comment_assistant(My_handle.config.get("luoxi_project", "Live_Comment_Assistant"), content))
            
            
            self.audio_synthesis_handle(message)

            return message
        except Exception as e:
            logger.error(traceback.format_exc())
            return None

    """
.....................................................................................................................
..............:*.....................................-*=........:+-......................-*+.........................
..............:*%+.:#%%%%%%%%%%%%*..:+++++++-........=@+........+%=-++++++***##%%=......=%@*+++++++++++:.............
.............--.-+:............-@*..=%#+++*@*........=@+.......+%+.:=+++=+%#-:........-#%%%+-------=#%#:.............
.............%#.......+#.......-@*..=%+...-@*+@@@@@@@@@@@@+...=%*:.......-#*:.......:*%*:.+%*-...-*%*-...............
.............%#..::::-*#-:::::.-@*..=%+...-@*........=@+.....+%@+........-#*:.......+*:.....*%@%%%*..................
.............%#.-****#@%*****+.-%*..=%*:::=@*.-*=....=@+....+%%%+........-##:..........:-*%%%%+-*%%%%#+-::...........
.............%#.....:@@#:......-%*..=%*---+@*.:*%=...=@+...+@==#+.+%@@@@@@@@@@@@@@**%@@#=...#@:.......=*%%...........
.............%#....+%+*%#%*:...-%*..=%+...-@*..-#%=..=@+......=#+........-##:........+******%%#********:.............
.............%#..-%#:.*#:.=%#=.-%*..=%+...-@*...:-:..=@+......=#+........-#*:........::::::*%=-::::::#%:.............
.............%#-#%-...*#....=+:-%*..=%*---+@*........=@+......=#+........-#*:.............=%*:.......#@..............
.............%#.:.....+#.......-%*..=%#+++*@*........=@+......=#+........-#*:...........-#%+.........#@..............
.............%#.......::..:====*%+..-*=...:*=...-*++*%#-......=#+..+##############-.-=*%#+:...=++==+%%-..............
.............*+...........:****+:...............:----:........-*=...................=*=........--==-:................
.....................................................................................................................
    """
    # Idle task processing
    def idle_time_task_handle(self, data):
        try:
            type = data["type"]
            content = data["content"]
            username = data["username"]

            # Convert digits in the username string to Chinese numerals
            if My_handle.config.get("filter", "username_convert_digits_to_chinese"):
                username = My_handle.common.convert_digits_to_chinese(username)

            if type == "reread":
                # Output the danmaku message sent by the current user
                logger.info(f"[{username}]: {content}")

                # Danmaku format check, special character replacement and specified language filtering
                content = self.comment_check_and_replace(content)
                if content is None:
                    return None
                
                # Determine the key mapping trigger type
                if My_handle.config.get("key_mapping", "type") == "Comment" or My_handle.config.get("key_mapping", "type") == "Comment + Reply":
                    # Key mapping; after it triggers, other later features are not executed
                    if self.key_mapping_handle("Comment", data):
                        return None
                    
                # Determine the custom command trigger type
                if My_handle.config.get("custom_cmd", "type") == "Comment" or My_handle.config.get("custom_cmd", "type") == "Comment + Reply":
                    # Custom command; after it triggers, other later features are not executed
                    if self.custom_cmd_handle("Comment", data):
                        return None

                # Important data needed for audio synthesis
                message = {
                    "type": "idle_time_task",
                    "tts_type": My_handle.config.get("audio_synthesis_type"),
                    "data": My_handle.config.get(My_handle.config.get("audio_synthesis_type")),
                    "config": My_handle.config.get("filter"),
                    "username": username,
                    "content": content,
                    "content_type": type
                }

                # Luoxi Live Danmaku Assistant
                if My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "enable") and \
                    "idle_time_task" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "type") and \
                    "On message created" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "trigger_position"):
                    asyncio.run(send_msg_to_live_comment_assistant(My_handle.config.get("luoxi_project", "Live_Comment_Assistant"), content))

                
                self.audio_synthesis_handle(message)

                return message
            elif type == "comment":
                # Record database
                if My_handle.config.get("database", "comment_enable"):
                    insert_data_sql = '''
                    INSERT INTO danmu (username, content, ts) VALUES (?, ?, ?)
                    '''
                    self.db.execute(insert_data_sql, (username, content, datetime.now()))

                # Output the danmaku message sent by the current user
                logger.info(f"[{username}]: {content}")

                # Danmaku format check, special character replacement and specified language filtering
                content = self.comment_check_and_replace(content)
                if content is None:
                    return None
                
                # Determine the key mapping trigger type
                if My_handle.config.get("key_mapping", "type") == "Comment" or My_handle.config.get("key_mapping", "type") == "Comment + Reply":
                    # Key mapping; after it triggers, other later features are not executed
                    if self.key_mapping_handle("Comment", data):
                        return None
                    
                # Determine the custom command trigger type
                if My_handle.config.get("custom_cmd", "type") == "Comment" or My_handle.config.get("custom_cmd", "type") == "Comment + Reply":
                    # Custom command; after it triggers, other later features are not executed
                    if self.custom_cmd_handle("Comment", data):
                        return None
                
                # 1, local Q&A library handling
                if self.local_qa_handle(data):
                    return None

                # 2, song request mode; after it triggers, other later features are not executed
                if self.choose_song_handle(data):
                    return None

                # 3, drawing mode; after it triggers, other later features are not executed
                if self.sd_handle(data):
                    return None

                """
                Run different logic depending on the chat type
                """ 
                chat_type = My_handle.config.get("chat_type")
                if chat_type == "game":
                    if My_handle.config.get("game", "enable"):
                        self.game.parse_keys_and_simulate_keys_press(content.split(), 2)
                    return None
                elif chat_type == "none":
                    return None
                else:
                    # Generic data_json construction
                    data_json = {
                        "username": username,
                        "content": My_handle.config.get("before_prompt") + content + My_handle.config.get("after_prompt") if chat_type != "reread" else content,
                        "ori_username": data["username"],
                        "ori_content": data["content"]
                    }

                    logger.debug("data_json={data_json}")
                    
                    # Call the unified LLM interface and get the returned content
                    resp_content = self.llm_handle(chat_type, data_json) if chat_type != "game" else ""

                    if resp_content:
                        logger.info(f"[AIReply to {username}]:{resp_content}")
                    else:
                        logger.warning(f"Warning: {chat_type} has no return")
                        resp_content = ""

                """
                Double filtering to safeguard you
                """
                resp_content = resp_content.replace('\n', '。')
                
                # LLMCheck the reply content for banned words
                resp_content = self.prohibitions_handle(resp_content, scope="output")
                if resp_content is None:
                    return None

                # logger.info("resp_content=" + resp_content)

                self.write_to_comment_log(resp_content, {"username": username, "content": content})

                # Determine the key mapping trigger type
                if My_handle.config.get("key_mapping", "type") == "Reply" or My_handle.config.get("key_mapping", "type") == "Comment + Reply":
                    # Replacement content
                    data["content"] = resp_content
                    # Key mapping; after it triggers, other later features are not executed
                    if self.key_mapping_handle("Reply", data):
                        pass

                # Determine the custom command mapping trigger type
                if My_handle.config.get("custom_cmd", "type") == "Reply" or My_handle.config.get("custom_cmd", "type") == "Comment + Reply":
                    # Replacement content
                    data["content"] = resp_content
                    # Custom command; after it triggers, other later features are not executed
                    if self.custom_cmd_handle("Reply", data):
                        pass
                    

                # Important data needed for audio synthesis
                message = {
                    "type": "idle_time_task",
                    "tts_type": My_handle.config.get("audio_synthesis_type"),
                    "data": My_handle.config.get(My_handle.config.get("audio_synthesis_type")),
                    "config": My_handle.config.get("filter"),
                    "username": username,
                    "content": resp_content,
                    "content_type": type
                }

                # Luoxi Live Danmaku Assistant
                if My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "enable") and \
                    "idle_time_task" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "type") and \
                    "On message created" in My_handle.config.get("luoxi_project", "Live_Comment_Assistant", "trigger_position"):
                    asyncio.run(send_msg_to_live_comment_assistant(My_handle.config.get("luoxi_project", "Live_Comment_Assistant"), resp_content))

                
                self.audio_synthesis_handle(message)

                return message
            elif type == "local_audio":
                logger.info(f'[{username}]: {data["file_path"]}')

                message = {
                    "type": "idle_time_task",
                    "tts_type": My_handle.config.get("audio_synthesis_type"),
                    "data": My_handle.config.get(My_handle.config.get("audio_synthesis_type")),
                    "config": My_handle.config.get("filter"),
                    "username": username,
                    "content": content,
                    "content_type": type,
                    "file_path": os.path.abspath(data["file_path"])
                }

                self.audio_synthesis_handle(message)

                return message
        except Exception as e:
            logger.error(traceback.format_exc())
            return None


    # Image recognition scheduled task
    def image_recognition_schedule_handle(self, data):
        try:
            username = data["username"]
            content = My_handle.config.get("image_recognition", "prompt")
            # Distinguish the image source type
            type = data["type"]

            # Convert digits in the username string to Chinese numerals
            if My_handle.config.get("filter", "username_convert_digits_to_chinese"):
                username = My_handle.common.convert_digits_to_chinese(username)

            if type == "Window screenshot":
                # Take a screenshot by window name
                screenshot_path = My_handle.common.capture_window_by_title(My_handle.config.get("image_recognition", "img_save_path"), My_handle.config.get("image_recognition", "screenshot_window_title"))
            elif type == "Camera screenshot":
                # Take a screenshot by camera index
                screenshot_path = My_handle.common.capture_image(My_handle.config.get("image_recognition", "img_save_path"), int(My_handle.config.get("image_recognition", "cam_index")))

            # Generic data_json construction
            data_json = {
                "username": username,
                "content": content,
                "img_data": screenshot_path,
                "ori_username": data["username"],
                "ori_content": content
            }
            
            # Call the unified LLM interface and get the returned content
            resp_content = self.llm_handle(My_handle.config.get("image_recognition", "model"), data_json, type="vision")

            if resp_content:
                logger.info(f"[AIReply to {username}]:{resp_content}")
            else:
                logger.warning(f'Warning:{My_handle.config.get("image_recognition", "model")}No return')
                resp_content = ""

            """
            Double filtering to safeguard you
            """
            resp_content = resp_content.replace('\n', '。')
            
            # LLMCheck the reply content for banned words
            resp_content = self.prohibitions_handle(resp_content, scope="output")
            if resp_content is None:
                return

            # logger.info("resp_content=" + resp_content)

            self.write_to_comment_log(resp_content, {"username": username, "content": content})

            # Determine the key mapping trigger type
            if My_handle.config.get("key_mapping", "type") == "Reply" or My_handle.config.get("key_mapping", "type") == "Comment + Reply":
                # Replacement content
                data["content"] = resp_content
                # Key mapping; after it triggers, other later features are not executed
                if self.key_mapping_handle("Reply", data):
                    pass

            # Determine the custom command trigger type
            if My_handle.config.get("custom_cmd", "type") == "Reply" or My_handle.config.get("custom_cmd", "type") == "Comment + Reply":
                # Replacement content
                data["content"] = resp_content
                # Custom command; after it triggers, other later features are not executed
                if self.custom_cmd_handle("Reply", data):
                    pass
                

            # Important data needed for audio synthesis
            message = {
                "type": "image_recognition_schedule",
                "tts_type": My_handle.config.get("audio_synthesis_type"),
                "data": My_handle.config.get(My_handle.config.get("audio_synthesis_type")),
                "config": My_handle.config.get("filter"),
                "username": username,
                "content": resp_content
            }

            
            self.audio_synthesis_handle(message)
        except Exception as e:
            logger.error(traceback.format_exc())


    # Chat handling (voice input)
    def talk_handle(self, data):
        """Chat handling (voice input)

        Args:
            data (dict): Contains the username and danmaku content

        Returns:
            dict: JSON data passed to audio synthesis
        """

        try:
            username = data["username"]
            content = data["content"]

            # Output the danmaku message sent by the current user
            logger.debug(f"[{username}]: {content}")

            if My_handle.config.get("talk", "show_chat_log"):
                if "ori_username" not in data:
                    data["ori_username"] = data["username"]
                if "ori_content" not in data:
                    data["ori_content"] = data["content"]
                if "user_face" not in data:
                    data["user_face"] = 'https://robohash.org/ui'

                # Data returned to the webui
                return_webui_json = {
                    "type": "llm",
                    "data": {
                        "type": "Comment message",
                        "username": data["ori_username"],
                        "user_face": data["user_face"],
                        "content_type": "question",
                        "content": data["ori_content"],
                        "timestamp": My_handle.common.get_bj_time(0)
                    }
                }
                webui_ip = "127.0.0.1" if My_handle.config.get("webui", "ip") == "0.0.0.0" else My_handle.config.get("webui", "ip")
                tmp_json = My_handle.common.send_request(f'http://{webui_ip}:{My_handle.config.get("webui", "port")}/callback', "POST", return_webui_json, timeout=10)
            

            # Record database
            if My_handle.config.get("database", "comment_enable"):
                insert_data_sql = '''
                INSERT INTO danmu (username, content, ts) VALUES (?, ?, ?)
                '''
                self.db.execute(insert_data_sql, (username, content, datetime.now()))

            # 0, points mechanism running
            if self.integral_handle("comment", data):
                return
            if self.integral_handle("crud", data):
                return

            """
            The username must also be filtered, to guard against bombers
            """
            # Banned word check on the username and danmaku
            username = self.prohibitions_handle(username)
            if username is None:
                return
            
            content = self.prohibitions_handle(content)
            if content is None:
                return
            
            # Danmaku format check, special character replacement and specified language filtering
            content = self.comment_check_and_replace(content)
            if content is None:
                return
            
            # Check whether the string is all punctuation; if so, filter it out
            if My_handle.common.is_punctuation_string(content):
                logger.debug(f"User: {username}], sent a danmaku of only symbols, filtered")
                return
            
            # Determine the key mapping trigger type
            if My_handle.config.get("key_mapping", "type") == "Comment" or My_handle.config.get("key_mapping", "type") == "Comment + Reply":
                # Key mapping; after it triggers, other later features are not executed
                if self.key_mapping_handle("Comment", data):
                    return
                
            # Determine the custom command trigger type
            if My_handle.config.get("custom_cmd", "type") == "Comment" or My_handle.config.get("custom_cmd", "type") == "Comment + Reply":
                # Custom command; after it triggers, other later features are not executed
                if self.custom_cmd_handle("Comment", data):
                    return
            
            try:
                # Read danmaku
                if My_handle.config.get("read_comment", "enable") and False:
                    logger.debug(f"Read danmaku content:{content}")

                    # Important data needed for audio synthesis
                    message = {
                        "type": "read_comment",
                        "tts_type": My_handle.config.get("audio_synthesis_type"),
                        "data": My_handle.config.get(My_handle.config.get("audio_synthesis_type")),
                        "config": My_handle.config.get("filter"),
                        "username": username,
                        "content": content
                    }

                    # Decide whether the username needs to be read out
                    if My_handle.config.get("read_comment", "read_username_enable"):
                        # Replace special characters in the username with empty
                        message['username'] = My_handle.common.replace_special_characters(message['username'], "！!@#￥$%^&*_-+/——=()（）【】}|{:;<>~`\\")
                        message['username'] = message['username'][:self.config.get("read_comment", "username_max_len")]

                        if len(self.config.get("read_comment", "read_username_copywriting")) > 0:
                            tmp_content = random.choice(self.config.get("read_comment", "read_username_copywriting"))
                            if "{username}" in tmp_content:
                                message['content'] = tmp_content.format(username=message['username']) + message['content']

                    
                    self.audio_synthesis_handle(message)
            except Exception as e:
                logger.error(traceback.format_exc())

            # 1, local Q&A library handling
            if self.local_qa_handle(data):
                return

            # 2, song request mode; after it triggers, other later features are not executed
            if self.choose_song_handle(data):
                return

            # 3, drawing mode; after it triggers, other later features are not executed
            if self.sd_handle(data):
                return
            
            # 4, whether to translate the danmaku content
            if My_handle.config.get("translate", "enable") and (My_handle.config.get("translate", "trans_type") == "Comment" or \
                My_handle.config.get("translate", "trans_type") == "Comment + Reply"):
                tmp = My_handle.my_translate.trans(content)
                if tmp:
                    content = tmp
                    # logger.info(f"After translation:{content}")

            # 5, web search
            content = self.search_online_handle(content)

            data_json = {
                "username": username,
                "content": content,
                "ori_username": data["username"],
                "ori_content": data["content"]
            }

            """
            Run different logic depending on the chat type
            """ 
            chat_type = My_handle.config.get("chat_type")
            if chat_type in self.chat_type_list:
                

                data_json["content"] = My_handle.config.get("before_prompt")
                # Whether to enable the danmaku template
                if self.config.get("comment_template", "enable"):
                    # Assume there are multiple unknown variables; users can define dynamic variables here
                    variables = {
                        'username': username,
                        'comment': content,
                        'cur_time': My_handle.common.get_bj_time(5),
                    }

                    comment_template_copywriting = self.config.get("comment_template", "copywriting")
                    # Use a dictionary for string replacement
                    if any(var in comment_template_copywriting for var in variables):
                        content = comment_template_copywriting.format(**{var: value for var, value in variables.items() if var in comment_template_copywriting})

                data_json["content"] += content + My_handle.config.get("after_prompt")

                logger.debug(f"data_json={data_json}")
                
                # Whether the currently selected LLM type supports stream and it is enabledstream
                if "stream" in self.config.get(chat_type) and self.config.get(chat_type, "stream"):
                    logger.warning("Use streaming inferenceLLM")
                    resp_content = self.llm_stream_handle_and_audio_synthesis(chat_type, data_json)
                    return resp_content
                else:
                    resp_content = self.llm_handle(chat_type, data_json)
                    if resp_content is not None:
                        logger.info(f"[AIReply to {username}]:{resp_content}")
                    else:
                        resp_content = ""
                        logger.warning(f"Warning: {chat_type} has no return")
            elif chat_type == "game":
                if My_handle.config.get("game", "enable"):
                    self.game.parse_keys_and_simulate_keys_press(content.split(), 2)
                return
            elif chat_type == "none":
                return
            elif chat_type == "reread":
                resp_content = self.llm_handle(chat_type, data_json)
            else:
                resp_content = content

            # Empty data, end
            if resp_content == "" or resp_content is None:
                return

            """
            Double filtering to safeguard you
            """
            resp_content = resp_content.strip()

            resp_content = resp_content.replace('\n', '。')
            
            # LLMCheck the reply content for banned words
            resp_content = self.prohibitions_handle(resp_content, scope="output")
            if resp_content is None:
                return

            # logger.info("resp_content=" + resp_content)

            # Whether to translate the reply content
            if My_handle.config.get("translate", "enable") and (My_handle.config.get("translate", "trans_type") == "Reply" or \
                My_handle.config.get("translate", "trans_type") == "Comment + Reply"):
                tmp = My_handle.my_translate.trans(resp_content)
                if tmp:
                    resp_content = tmp

            self.write_to_comment_log(resp_content, {"username": username, "content": content})

            # Determine the key mapping trigger type
            if My_handle.config.get("key_mapping", "type") == "Reply" or My_handle.config.get("key_mapping", "type") == "Comment + Reply":
                # Replacement content
                data["content"] = resp_content
                # Key mapping; after it triggers, other later features are not executed
                if self.key_mapping_handle("Reply", data):
                    pass

            # Determine the custom command trigger type
            if My_handle.config.get("custom_cmd", "type") == "Reply" or My_handle.config.get("custom_cmd", "type") == "Comment + Reply":
                # Replacement content
                data["content"] = resp_content
                # Custom command; after it triggers, other later features are not executed
                if self.custom_cmd_handle("Reply", data):
                    pass
                

            # Important data needed for audio synthesis
            message = {
                "type": "talk",
                "tts_type": My_handle.config.get("audio_synthesis_type"),
                "data": My_handle.config.get(My_handle.config.get("audio_synthesis_type")),
                "config": My_handle.config.get("filter"),
                "username": username,
                "content": resp_content
            }

            self.audio_synthesis_handle(message)

            return message
        except Exception as e:
            logger.error(traceback.format_exc())
            return None


    """
    Data discard part
    When adding new event handling, content must be appended to this section
    """
    def process_data(self, data, timer_flag):
        with self.data_lock:
            if timer_flag not in self.timers or not self.timers[timer_flag].is_alive():
                self.timers[timer_flag] = threading.Timer(self.get_interval(timer_flag), self.process_last_data, args=(timer_flag,))
                self.timers[timer_flag].start()

            # self.timers[timer_flag].last_data = data
            if hasattr(self.timers[timer_flag], 'last_data'):
                self.timers[timer_flag].last_data.append(data)
                # Pay attention to the config naming here!!!
                # Number of data items to keep
                if len(self.timers[timer_flag].last_data) > int(My_handle.config.get("filter", timer_flag + "_forget_reserve_num")):
                    self.timers[timer_flag].last_data.pop(0)
            else:
                self.timers[timer_flag].last_data = [data]

    def process_last_data(self, timer_flag):
        with self.data_lock:
            timer = self.timers.get(timer_flag)
            if timer and timer.last_data is not None and timer.last_data != []:
                logger.debug(f"Preprocess timer trigger type={timer_flag},data={timer.last_data}")

                My_handle.is_handleing = 1

                if timer_flag == "comment":
                    for data in timer.last_data:
                        self.comment_handle(data)
                elif timer_flag == "gift":
                    for data in timer.last_data:
                        self.gift_handle(data)
                    #self.gift_handle(timer.last_data)
                elif timer_flag == "entrance":
                    for data in timer.last_data:
                        self.entrance_handle(data)
                    #self.entrance_handle(timer.last_data)
                elif timer_flag == "follow":
                    for data in timer.last_data:
                        self.follow_handle(data)
                elif timer_flag == "talk":
                    # Chat temporarily shares the danmaku handling logic
                    for data in timer.last_data:
                        self.talk_handle(data)
                    #self.comment_handle(timer.last_data)
                elif timer_flag == "schedule":
                    # Scheduled task handling
                    for data in timer.last_data:
                        self.schedule_handle(data)
                    #self.schedule_handle(timer.last_data)
                elif timer_flag == "idle_time_task":
                    # Scheduled task handling
                    for data in timer.last_data:
                        self.idle_time_task_handle(data)
                    #self.idle_time_task_handle(timer.last_data)
                elif timer_flag == "image_recognition_schedule":
                    # Scheduled task handling
                    for data in timer.last_data:
                        self.image_recognition_schedule_handle(data)

                My_handle.is_handleing = 0

                # Clear data
                timer.last_data = []

    def get_interval(self, timer_flag):
        # Define the intervals of different timers according to the flag
        intervals = {
            "comment": My_handle.config.get("filter", "comment_forget_duration"),
            "gift": My_handle.config.get("filter", "gift_forget_duration"),
            "entrance": My_handle.config.get("filter", "entrance_forget_duration"),
            "follow": My_handle.config.get("filter", "follow_forget_duration"),
            "talk": My_handle.config.get("filter", "talk_forget_duration"),
            "schedule": My_handle.config.get("filter", "schedule_forget_duration"),
            "idle_time_task": My_handle.config.get("filter", "idle_time_task_forget_duration")
            # Add more timers and their intervals as needed, and remember to add the config items in config.json
        }

        # Default interval is 0.1 seconds
        return intervals.get(timer_flag, 0.1)


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
            My_handle.abnormal_alarm_data[type]["error_count"] += 1

            if not My_handle.config.get("abnormal_alarm", type, "enable"):
                return True
            
            if My_handle.config.get("abnormal_alarm", type, "type") == "local_audio":
                # Whether the error count is greater than the auto-restart error count
                if My_handle.abnormal_alarm_data[type]["error_count"] >= My_handle.config.get("abnormal_alarm", type, "auto_restart_error_num"):
                    data = {
                        "type": "restart",
                        "api_type": "api",
                        "data": {
                            "config_path": "config.json"
                        }
                    }

                    webui_ip = "127.0.0.1" if My_handle.config.get("webui", "ip") == "0.0.0.0" else My_handle.config.get("webui", "ip")
                    My_handle.common.send_request(f'http://{webui_ip}:{My_handle.config.get("webui", "port")}/sys_cmd', "POST", data)

                # Whether the error count is less than the alert-start error count; if so, do not trigger an alert
                if My_handle.abnormal_alarm_data[type]["error_count"] < My_handle.config.get("abnormal_alarm", type, "start_alarm_error_num"):
                    return

                path_list = My_handle.common.get_all_file_paths(My_handle.config.get("abnormal_alarm", type, "local_audio_path"))

                # Randomly pick one element from the list
                audio_path = random.choice(path_list)

                message = {
                    "type": "abnormal_alarm",
                    "tts_type": My_handle.config.get("audio_synthesis_type"),
                    "data": My_handle.config.get(My_handle.config.get("audio_synthesis_type")),
                    "config": My_handle.config.get("filter"),
                    "username": "System",
                    "content": os.path.join(My_handle.config.get("abnormal_alarm", type, "local_audio_path"), My_handle.common.extract_filename(audio_path, True))
                }

                logger.warning(f"[Exception alert-{type}] {My_handle.common.extract_filename(audio_path, False)}")

                self.audio_synthesis_handle(message)

        except Exception as e:
            logger.error(traceback.format_exc())

            return False

        return True

