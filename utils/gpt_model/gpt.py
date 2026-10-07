# -*- coding: UTF-8 -*-
"""
@Project : AI-Vtuber 
@File    : gpt.py
@Author  : HildaM
@Email   : Hilda_quan@163.com
@Date    : 2023/06/23 Afternoon 7:47 
@Description :  Unified model layer abstraction
"""
from utils.my_log import logger

from utils.gpt_model.chatgpt import Chatgpt
from utils.gpt_model.text_generation_webui import TEXT_GENERATION_WEBUI
# from utils.gpt_model.sparkdesk import SPARKDESK
from utils.gpt_model.langchain_chatchat import Langchain_ChatChat
from utils.gpt_model.zhipu import Zhipu
from utils.gpt_model.bard import Bard_api
from utils.gpt_model.tongyi import TongYi
try:
    from utils.gpt_model.tongyixingchen import TongYiXingChen
except Exception as e:
    print(f"Skip TongYiXingChen import: {e}")
    TongYiXingChen = None
    
# from utils.gpt_model.my_wenxinworkshop import My_WenXinWorkShop
from utils.gpt_model.gemini import Gemini
from utils.gpt_model.koboldcpp import Koboldcpp
from utils.gpt_model.anythingllm import AnythingLLM
from utils.gpt_model.gpt4free import GPT4Free
from utils.gpt_model.custom_llm import Custom_LLM
from utils.gpt_model.llm_tpu import LLM_TPU
from utils.gpt_model.dify import Dify
from utils.gpt_model.volcengine import VolcEngine

class GPT_Model:
    openai = None
    
    def set_model_config(self, model_name, config):
        model_classes = {
            "text_generation_webui": TEXT_GENERATION_WEBUI,
#             "sparkdesk": SPARKDESK,
            "langchain_chatchat": Langchain_ChatChat,
            "zhipu": Zhipu,
            "bard": Bard_api,
            "tongyi": TongYi,
            "tongyixingchen": TongYiXingChen,
#             "my_wenxinworkshop": My_WenXinWorkShop,
            "gemini": Gemini,
            "koboldcpp": Koboldcpp,
            "anythingllm": AnythingLLM,
            "gpt4free": GPT4Free,
            "custom_llm": Custom_LLM,
            "llm_tpu": LLM_TPU,
            "dify": Dify,
            "volcengine": VolcEngine,
        }

        if model_name == "openai":
            self.openai = config
        elif model_name == "chatgpt":
            if self.openai is None:
                logger.error("openai key is empty, cannot configure the chatgpt model")
                exit(-1)
            self.chatgpt = Chatgpt(self.openai, config)
        elif model_name in model_classes:
            setattr(self, model_name, model_classes[model_name](config))

    def set_vision_model_config(self, model_name, config):
        model_classes = {
            "gemini": Gemini,
            "zhipu": Zhipu,
        }

        setattr(self, model_name, model_classes[model_name](config))

    def get(self, name):
        logger.info("GPT_MODEL: Entered the get method")
        try:
            if name != "reread":
                return getattr(self, name)
        except AttributeError:
            logger.warning(f"{name} This model is not supported. If it is not an LLM type, this is only a warning and it can be used normally, so rest assured")
            return None

    def get_openai_key(self):
        if self.openai is None:
            logger.error("openai_key is empty")
            return None
        return self.openai["api_key"]

    def get_openai_model_name(self):
        if self.openai is None:
            logger.warning("openaimodel is empty, will be set to the defaultgpt-3.5")
            return "gpt-3.5-turbo-0301"
        return self.openai["model"]


# Global variable
GPT_MODEL = GPT_Model()
