# -*- coding: UTF-8 -*-
"""
@Project : AI-Vtuber 
@File    : claude_model.py
@Author  : HildaM
@Email   : Hilda_quan@163.com
@Date    : 2023/06/17 Afternoon 4:44 
@Description : Localized vector database, implementinglangchain_pdf
"""
import logging
from langchain.document_loaders import PyPDFLoader

from utils.chat_with_file.chat_mode.chat_model import Chat_model

from utils.gpt_model.gpt import GPT_MODEL
from utils.my_handle import My_handle


# Since the data returned by similarity_search is not standard JSON and cannot be formatted with Python, string operations are the only way to get the data
# The returned data is very standard, so the content info is easy to get
def get_content(data: str):
    prefix = "{'content': "
    suffix = ", 'chunk'"

    start = data.find(prefix)
    end = data.find(suffix)
    return data[start:end]


class Claude_mode(Chat_model):
    pdf_loader = PyPDFLoader
    local_db = None
    claude = None

    def __init__(self, data):
        super(Claude_mode, self).__init__(data)

        logging.info(f"Local data file path: {self.data_path}")

        # Load the pdf and generate the vector database
        self.load_zip_as_db(self.data_path, self.pdf_loader,
                            self.chunk_size,self.chunk_overlap)
        # Initialize the claude client
        self.claude = GPT_MODEL.get("claude")

    def load_zip_as_db(self, zip_file_path,
                       pdf_loader,
                       chunk_size=300,
                       chunk_overlap=20):
        from utils.chat_with_file.vector_store.faiss import create_faiss_index_from_zip

        if chunk_overlap >= chunk_size:
            logging.error("The input chunk_overlap is greater than chunk_size. To avoid creation failure, chunk_overlap will be corrected to one tenth of chunk_size")
            chunk_overlap = round(chunk_size / 10)
        if zip_file_path is None:
            logging.error("zipFile path is empty. Vector database build failed. Please restart")
            exit(-1)

        self.local_db = create_faiss_index_from_zip(
            zip_file_path=zip_file_path,
            embedding_model_name=self.local_vector_embedding_model,
            pdf_loader=pdf_loader,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

        logging.info("Vector knowledge base created successfully!")

    # Call the local vector database to get related info
    def get_local_database_data(self, message):
        logging.info(f"Start querying the local vector database for info about {message}........")

        contents = []
        docs = self.local_db.similarity_search(message, k=self.local_max_query)
        for i in range(self.local_max_query):
            # Preprocess chunking
            content = docs[i].page_content.replace('\n', ' ')
            logging.info(f"No.{i} Related info: {content}")
            data = get_content(content)
            # Updatecontents
            contents.append(data)

        logging.info("Relevant info queried from the local vector database: {}".format(contents))
        if len(contents) == 0 or contents is None:
            return
        related_data = "\n---\n".join(contents) + "\n---\n"
        return related_data

    def get_model_resp(self, question=""):
        related_data = self.get_local_database_data(question)
        if related_data is None or len(related_data) <= 0:
            content = question
        else:
            content = related_data + "\n" + self.question_prompt + " question: " + question

        resp = self.claude.get_resp(content)
        return resp


if __name__ == '__main__':
    my_handle = My_handle("config.json")
    if my_handle is None:
        print("Program initialization failed!")
        exit(0)