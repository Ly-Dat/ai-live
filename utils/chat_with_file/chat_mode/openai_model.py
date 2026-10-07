import os
import zipfile

from PyPDF2 import PdfReader
from langchain.document_loaders import DirectoryLoader, TextLoader, PyPDFLoader
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores import ElasticVectorSearch, Pinecone, Weaviate, FAISS
from langchain.chains.question_answering import load_qa_chain
from langchain.llms import OpenAI
from langchain.chat_models import ChatOpenAI
from langchain.callbacks import get_openai_callback
from langchain.prompts import PromptTemplate
from tqdm.auto import tqdm

import logging

from utils.chat_with_file.chat_mode.chat_model import Chat_model


class Openai_mode(Chat_model):
    docsearch = None
    chain = None

    def __init__(self, data):
        # Config info
        super(Openai_mode, self).__init__(data)

        logging.info(f"pdfFile path: {self.data_path}")

        # Load the local zip file
        # Stored file format
        # structure: ./data/vector_base
        #               - source data
        store_path = os.getcwd() + "/data/vector_base/"
        if not os.path.exists(store_path):
            os.makedirs(store_path)
            project_path = store_path
            source_data = os.path.join(project_path, "source_data")
            os.makedirs(source_data)  # ./vector_base/source_data
        else:
            project_path = store_path
            source_data = os.path.join(project_path, "source_data")

        # Extract the data package
        with zipfile.ZipFile(self.data_path, 'r') as zip_ref:
            # extract everything to "source_data"
            zip_ref.extractall(source_data)

        logging.info(f"source_data={source_data}")

        # Handle different text files
        all_docs = []
        for ext in [".txt", ".tex", ".md", ".pdf"]:
            if ext in [".txt", ".tex", ".md"]:
                loader = DirectoryLoader(source_data, glob=f"**/*{ext}", loader_cls=TextLoader,
                                         loader_kwargs={'autodetect_encoding': True})
            elif ext in [".pdf"]:
                loader = DirectoryLoader(source_data, glob=f"**/*{ext}", loader_cls=PyPDFLoader)
            else:
                continue
            docs = loader.load()
            all_docs = all_docs + docs

        # logging.info(all_docs)

        # We need to split the text that we read into smaller chunks so that during information retreival we don't hit the token size limits. 
        # We need to split the text we read into smaller chunks so the token size limit is not reached during information retrieval.
        text_splitter = CharacterTextSplitter(
            # Separators for splitting text
            separator=self.separator,
            # Maximum number of characters per text chunk (the more characters per chunk, the more tokens consumed and the more detailed the reply)
            chunk_size=self.chunk_size,
            # Number of overlapping characters between two adjacent text chunks
            # This overlap helps maintain text coherence, especially when the text is used to train language models or other machine learning models that need context information
            chunk_overlap=self.chunk_overlap,
            # Used to compute the length of text chunks
            # Here the length function is len, which means the length of each text chunk is its character count. In some cases you may want to use other length functions.
            # For example, if your text is made of words, you may want a function that counts the words in a text chunk instead of characters.
            length_function=len,
        )

        texts = []

        for idx, page in enumerate(tqdm(all_docs)):
            content = page.page_content

            # logging.debug(f"[{content}]")

            if len(content) > self.chunk_size:
                texts = texts + text_splitter.split_text(content)

        logging.info("Split into a total of" + str(len(texts)) + "Chunk text content")

        logging.debug(texts)

        # Created an OpenAIEmbeddings instance, then used it to convert some text into vector representations (embeddings).
        # Then, these vectors are loaded into a FAISS (Facebook AI Similarity Search) index for similarity search.
        # This kind of index lets you quickly find the vectors most similar to a given vector among a large number of vectors.
        embeddings = OpenAIEmbeddings(openai_api_key=self.openai_api_key[0])
        # Convert the string list to UTF-8 encoding
        # encode_texts = [s.encode('utf-8') for s in texts]
        self.docsearch = FAISS.from_texts(texts, embeddings)

        if self.chat_mode == "openai_gpt":
            # The prompt template here can be modified yourself, such asUse the following context to answer the final question first. Then summarize and answer based on your own knowledge
            # Use the following context to answer the final question. If you do not know the answer, say you do not know or that you cannot find the answer in the article; do not try to make up an answer.
            # Use the following pieces of context to answer the question at the end. If you don't know the answer, just say that you don't know or you can't find the answer in the article, don't try to make up an answer
            prompt_template = self.question_prompt + """
            
            content：{context}

            question: {question}
            """
            PROMPT = PromptTemplate(
                template=prompt_template, input_variables=["context", "question"]
            )

            # Create a question-answer chain (QA Chain) using a custom prompt template
            self.chain = load_qa_chain(
                ChatOpenAI(model_name=self.openai_model_name, openai_api_key=self.openai_api_key[0]), \
                chain_type=self.chain_type, prompt=PROMPT)

    def get_model_resp(self, content=""):
        if self.chat_mode == "openai_vector_search":
            # Use only langchain without calling GPT, which saves tokens, for a simple local data search
            resp_contents = self.docsearch.similarity_search(content)
            if len(resp_contents) != 0:
                resp_content = resp_contents[0].page_content
            else:
                resp_content = "No matching results found."

            return resp_content

        # When the user enters a query, the system first runs a similarity search in the local document collection to find the documents most relevant to the query.
        # Then it passes these relevant documents along with the user query as input to the language model. The language model generates an answer based on this input.
        # If the system cannot find any documents related to the user query in the local document collection, or if the language model cannot generate a meaningful answer from the given input,
        # Then the system may be unable to answer the user query.
        elif self.chat_mode == "openai_gpt":
            with get_openai_callback() as cb:
                query = content
                # Run a similarity search on the user query and run it with the QA chain
                docs = self.docsearch.similarity_search(query)

                # You can print the matched document content to take a look
                # logging.info(docs)

                res = self.chain.run(input_documents=docs, question=query)
                # logging.info(f"Output: {res}")

                # Show cost
                if self.show_token_cost:
                    # Related consumption and cost
                    logging.info(f"Total Tokens: {cb.total_tokens}")
                    logging.info(f"Prompt Tokens: {cb.prompt_tokens}")
                    logging.info(f"Completion Tokens: {cb.completion_tokens}")
                    logging.info(f"Successful Requests: {cb.successful_requests}")
                    logging.info(f"Total Cost (USD): ${cb.total_cost}")

                return res
