# -*- coding: UTF-8 -*-
"""
@Project : AI-Vtuber
@File    : gpt.py
@Description :  Unified model layer abstraction.

Each provider module is imported only when that provider is configured. Importing all of them at start-up cost
several seconds and a lot of memory (langchain, google, zhipu, dashscope ... SDKs) for providers nobody was using.
"""
import importlib

from utils.my_log import logger

# name -> (module, class)
_CHAT = {
    "text_generation_webui": ("utils.gpt_model.text_generation_webui", "TEXT_GENERATION_WEBUI"),
    "langchain_chatchat": ("utils.gpt_model.langchain_chatchat", "Langchain_ChatChat"),
    "zhipu": ("utils.gpt_model.zhipu", "Zhipu"),
    "bard": ("utils.gpt_model.bard", "Bard_api"),
    "tongyi": ("utils.gpt_model.tongyi", "TongYi"),
    "tongyixingchen": ("utils.gpt_model.tongyixingchen", "TongYiXingChen"),
    "gemini": ("utils.gpt_model.gemini", "Gemini"),
    "koboldcpp": ("utils.gpt_model.koboldcpp", "Koboldcpp"),
    "anythingllm": ("utils.gpt_model.anythingllm", "AnythingLLM"),
    "gpt4free": ("utils.gpt_model.gpt4free", "GPT4Free"),
    "custom_llm": ("utils.gpt_model.custom_llm", "Custom_LLM"),
    "llm_tpu": ("utils.gpt_model.llm_tpu", "LLM_TPU"),
    "dify": ("utils.gpt_model.dify", "Dify"),
    "volcengine": ("utils.gpt_model.volcengine", "VolcEngine"),
}
_VISION = {
    "gemini": ("utils.gpt_model.gemini", "Gemini"),
    "zhipu": ("utils.gpt_model.zhipu", "Zhipu"),
}


def _load(table, name):
    module, cls = table[name]
    try:
        return getattr(importlib.import_module(module), cls)
    except Exception as e:
        logger.error(f"Could not load the '{name}' model ({module}): {e}")
        raise


class GPT_Model:
    openai = None

    def set_model_config(self, model_name, config):
        if model_name == "openai":
            self.openai = config
        elif model_name == "chatgpt":
            if self.openai is None:
                logger.error("openai key is empty, cannot configure the chatgpt model")
                exit(-1)
            from utils.gpt_model.chatgpt import Chatgpt
            self.chatgpt = Chatgpt(self.openai, config)
        elif model_name in _CHAT:
            setattr(self, model_name, _load(_CHAT, model_name)(config))

    def set_vision_model_config(self, model_name, config):
        setattr(self, model_name, _load(_VISION, model_name)(config))

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
