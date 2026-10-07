# -*- coding: UTF-8 -*-
"""
@Project : AI-Vtuber
@File    : claude_model.py
@Author  : HildaM
@Email   : Hilda_quan@163.com
@Date    : 2023/06/17 Afternoon 4:44
@Description : Local vector database model settings
"""

from langchain.embeddings import HuggingFaceEmbeddings
import os


# Project root path
TEC2VEC_MODELS_PATH = os.getcwd() + "\\" + "data" + "\\" + "text2vec_models" "\\"

# Default model
DEFAULT_MODEL_NAME = "sebastian-hofstaetter_distilbert-dot-tas_b-b256-msmarco"


def get_default_model():
    return HuggingFaceEmbeddings(model_name=TEC2VEC_MODELS_PATH + DEFAULT_MODEL_NAME)


def get_text2vec_model(model_name):
    """
        0. Check for empty. If empty, load the built-in model
        1. First check whether the model exists in the project data/tec2vec_models directory
        2. If it exists, load it directly
        3. Does not exist, download it from Huggingface to local and save it in the system cache
    """
    if model_name is None:
        return HuggingFaceEmbeddings(model_name=TEC2VEC_MODELS_PATH + DEFAULT_MODEL_NAME)

    model_path = TEC2VEC_MODELS_PATH + model_name
    if os.path.exists(model_path):
        return HuggingFaceEmbeddings(model_name=model_path)
    else:
        return HuggingFaceEmbeddings(model_name=model_name)
