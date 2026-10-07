# -*- coding: UTF-8 -*-
"""
@Project : AI-Vtuber
@File    : claude_model.py
@Author  : HildaM
@Email   : Hilda_quan@163.com
@Date    : 2023/06/17 Afternoon 4:44
@Description : Local vector database config
"""

import json
import logging

from langchain.vectorstores import FAISS
import os
from tqdm.auto import tqdm
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import DirectoryLoader, TextLoader
from utils.chat_with_file.vector_store.embeddings import get_text2vec_model, get_default_model, DEFAULT_MODEL_NAME
import tiktoken
import zipfile
import pickle

tokenizer_name = tiktoken.encoding_for_model('gpt-4')
tokenizer = tiktoken.get_encoding(tokenizer_name.name)


#######################################################################################################################
# Files vector_store
#######################################################################################################################
def check_existence(path):
    return os.path.isfile(path) or os.path.isdir(path)


def list_files(directory, ext=".pdf"):
    # List all files in the directory
    files_in_directory = os.listdir(directory)
    # Filter the list to only include PDF files
    files_list = [file for file in files_in_directory if file.endswith(ext)]
    return files_list


def list_pdf_files(directory):
    # List all files in the directory
    files_in_directory = os.listdir(directory)
    # Filter the list to only include PDF files
    pdf_files = [file for file in files_in_directory if file.endswith(".pdf")]
    return pdf_files


def tiktoken_len(text):
    # evaluate how many tokens for the given text
    tokens = tokenizer.encode(text, disallowed_special=())
    return len(tokens)


def get_chunks(docs, chunk_size=500, chunk_overlap=20, length_function=tiktoken_len):
    # Construct the text splitter
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size,
                                                   chunk_overlap=chunk_overlap,
                                                   length_function=length_function,
                                                   separators=["\n\n", "\n", " ", ""])
    chunks = []
    for idx, page in enumerate(tqdm(docs)):
        source = page.metadata.get('source')
        content = page.page_content
        if len(content) > chunk_size:
            texts = text_splitter.split_text(content)
            chunks.extend([str({'content': texts[i], 'chunk': i, 'source': os.path.basename(source)}) for i in
                           range(len(texts))])
    return chunks


#######################################################################################################################
# Create FAISS object
#######################################################################################################################

"""
    Supported models: 
        distilbert-dot-tas_b-b256-msmarco
"""


def create_faiss_index_from_zip(zip_file_path, embedding_model_name=None, pdf_loader=None,
                                chunk_size=500, chunk_overlap=20):
    # Select model
    if embedding_model_name is None:
        embeddings = get_default_model()
        embedding_model_name = DEFAULT_MODEL_NAME
    elif isinstance(embedding_model_name, str):
        embeddings = get_text2vec_model(embedding_model_name)

    # Create the directory for storing the vector database
    # Stored file format
    # structure: ./data/vector_base
    #               - source data
    #               - embeddings
    #               - faiss_index
    store_path = os.getcwd() + "/data/vector_base/"
    if not os.path.exists(store_path):
        os.makedirs(store_path)
        project_path = store_path
        source_data = os.path.join(project_path, "source_data")
        embeddings_data = os.path.join(project_path, "embeddings")
        index_data = os.path.join(project_path, "faiss_index")
        os.makedirs(source_data)  # ./vector_base/source_data
        os.makedirs(embeddings_data)  # ./vector_base/embeddings
        os.makedirs(index_data)  # ./vector_base/faiss_index
    else:
        logging.warning(
            "The vector database already exists, and the old one is loaded by default. To load new data, delete vector_base under the data directory and restart")
        logging.info("Loading the existing vector database file")
        db = load_exist_faiss_file(store_path)
        if db is None:
            logging.error("The loaded old database is empty, the database file may be abnormal. Please delete the vector_base folder completely and import the data again")
            exit(-1)
        return db

    # Extract the data package
    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
        # extract everything to "source_data"
        zip_ref.extractall(source_data)

    # Assemble the database metadata and write it to db_meta.json
    db_meta = {"pdf_loader": pdf_loader.__name__,
               "chunk_size": chunk_size,
               "chunk_overlap": chunk_overlap,
               "embedding_model": embedding_model_name,
               "files": os.listdir(source_data),
               "source_path": source_data}
    with open(os.path.join(project_path, "db_meta.json"), "w", encoding="utf-8") as f:
        json.dump(db_meta, f)

    # Handle different text files
    all_docs = []
    for ext in [".txt", ".tex", ".md", ".pdf"]:
        if ext in [".txt", ".tex", ".md"]:
            loader = DirectoryLoader(source_data, glob=f"**/*{ext}", loader_cls=TextLoader,
                                     loader_kwargs={'autodetect_encoding': True})
        elif ext in [".pdf"]:
            loader = DirectoryLoader(source_data, glob=f"**/*{ext}", loader_cls=pdf_loader)
        else:
            continue
        docs = loader.load()
        all_docs = all_docs + docs

    # Data sharding
    chunks = get_chunks(all_docs, chunk_size, chunk_overlap)

    # Vector data
    text_embeddings = embeddings.embed_documents(chunks)
    text_embedding_pairs = list(zip(chunks, text_embeddings))

    # Vector data save location
    embeddings_save_to = os.path.join(embeddings_data, 'text_embedding_pairs.pickle')

    # Save data
    with open(embeddings_save_to, 'wb') as handle:
        pickle.dump(text_embedding_pairs, handle, protocol=pickle.HIGHEST_PROTOCOL)

    # Save the vector data into FAISS
    db = FAISS.from_embeddings(text_embedding_pairs, embeddings)
    db.save_local(index_data)

    return db


def find_file(file_name, directory):
    for root, dirs, files in os.walk(directory):
        if file_name in files:
            return os.path.join(root, file_name)
    return None  # If the file was not found


def find_file_dir(file_name, directory):
    for root, dirs, files in os.walk(directory):
        if file_name in files:
            return root  # return the directory instead of the full path
    return None  # If the file was not found


# Load the local vector database
def load_exist_faiss_file(path):
    # Get metadata
    db_meta_json = find_file("db_meta.json", path)
    if db_meta_json is not None:
        with open(db_meta_json, "r", encoding="utf-8") as f:
            db_meta_dict = json.load(f)
    else:
        logging.error("vector_baseThe vector database is corrupted, please delete this folder completely and then import the data again!")
        exit(-1)

    # Get model data
    embedding = get_text2vec_model(db_meta_dict["embedding_model"])

    # Loadindex.faiss
    faiss_path = find_file_dir("index.faiss", path)
    if faiss_path is not None:
        db = FAISS.load_local(faiss_path, embedding)
        return db
    else:
        logging.error("Failed to load index.faiss, the model is corrupted. Please delete the vector_base folder completely and import the data again")
        exit(-1)


# Test code
if __name__ == "__main__":
    from langchain.document_loaders import PyPDFLoader

    zip_file_path = "data/伊卡洛斯百度百科.zip"
    create_faiss_index_from_zip(zip_file_path=zip_file_path, pdf_loader=PyPDFLoader)
    db = load_exist_faiss_file(zip_file_path)
    if db is not None:
        logging.info("Local database loaded successfully!")