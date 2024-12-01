import logging
from flask import url_for, Response
import numpy as np
import openai
import os
from dotenv import load_dotenv
import json
import faiss
from utils import is_chunk_infos_empty
import time
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from concurrent.futures import ThreadPoolExecutor
import asyncio
import aiohttp


nltk.download('punkt')

# Load environment variables from .env file
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

INDEX_PATH = 'index.faiss'
CHUNK_INFOS_PATH = 'chunk_infos.json'

executor = ThreadPoolExecutor()
BATCH_SIZE = 16


def embed_text(texts, batch_size=16):
    try:
        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = openai.Embedding.create(input=batch, model="text-embedding-ada-002")
            batch_embeddings = [resp['embedding'] for resp in response['data']]
            embeddings.extend(batch_embeddings)
        return embeddings
    except Exception as e:
        logging.error(f"An error occurred while embedding: {str(e)}")
        raise

def dynamic_split_into_chunks(text, max_chunk_size=500):
    try:
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = ""

        for paragraph in paragraphs:
            if len(word_tokenize(current_chunk)) + len(word_tokenize(paragraph)) <= max_chunk_size:
                current_chunk += " " + paragraph
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                if len(word_tokenize(paragraph)) <= max_chunk_size:
                    current_chunk = paragraph
                else:
                    sentences = sent_tokenize(paragraph)
                    for sentence in sentences:
                        if len(word_tokenize(current_chunk)) + len(word_tokenize(sentence)) <= max_chunk_size:
                            current_chunk += " " + sentence
                        else:
                            if current_chunk:
                                chunks.append(current_chunk.strip())
                            current_chunk = sentence
        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks
    except Exception as e:
        logging.error(f"An error occurred while splitting text into chunks: {str(e)}")
        raise

def add_document_to_index(document):
    try:
        add_start = time.time()
        doc_id, title, content, ip_address = document  # Expect 4 elements instead of 5

        doc_chunks = dynamic_split_into_chunks(content)
        embeddings = embed_text(doc_chunks)
        chunk_infos = [(i, int(doc_id), title, chunk) for i, chunk in enumerate(doc_chunks)]

        print(f"Adding Document ID: {doc_id}, Title: {title}, Chunks:")
        for i, chunk in enumerate(chunk_infos):
            print(f"Chunk {i}: {chunk}...")

        if not is_chunk_infos_empty(INDEX_PATH, CHUNK_INFOS_PATH):
            index = faiss.read_index(INDEX_PATH)
            with open(CHUNK_INFOS_PATH, 'r') as f:
                existing_chunk_infos = json.load(f)
            start_id = len(existing_chunk_infos)
            chunk_infos = [(start_id + i, info[1], info[2], info[3]) for i, info in enumerate(chunk_infos)]
        else:
            index = faiss.IndexFlatL2(len(embeddings[0]))
            existing_chunk_infos = []

        index.add(np.array(embeddings, dtype=np.float32))
        faiss.write_index(index, INDEX_PATH)

        existing_chunk_infos.extend(chunk_infos)
        with open(CHUNK_INFOS_PATH, 'w') as f:
            json.dump(existing_chunk_infos, f)

        add_end = time.time()
        print("Add time: ", add_end - add_start)
        print(f"Document {doc_id} added successfully.")
    except Exception as e:
        logging.error(f"Error in add_document_to_index: {e}")
        raise

def delete_document_from_index(doc_id):
    try:
        delete_start = time.time()
        if not os.path.exists(INDEX_PATH) or not os.path.exists(CHUNK_INFOS_PATH):
            print("Index or chunk information file does not exist.")
            return

        index = faiss.read_index(INDEX_PATH)
        with open(CHUNK_INFOS_PATH, 'r') as f:
            chunk_infos = json.load(f)

        print(f"chunk_infos: {chunk_infos}")
        print(f"Document ID to delete: {doc_id}")

        chunks_to_remove = [i for i, info in enumerate(chunk_infos) if info[1] == doc_id]
        print(f"Chunks to remove: {chunks_to_remove}")

        if not chunks_to_remove:
            print("No chunks found to remove for the given document ID.")
            return

        remaining_chunk_infos = [info for i, info in enumerate(chunk_infos) if info[1] != doc_id]
        remaining_embeddings = [index.reconstruct(i) for i in range(index.ntotal) if i not in chunks_to_remove]
        print(f"Remaining chunks count: {len(remaining_chunk_infos)}")
        print(f"Remaining embeddings count: {len(remaining_embeddings)}")

        if remaining_embeddings:
            index = faiss.IndexFlatL2(len(remaining_embeddings[0]))
            index.add(np.array(remaining_embeddings, dtype=np.float32))
            print("New FAISS index created with remaining embeddings.")
        else:
            index = faiss.IndexFlatL2(0)
            print("No remaining embeddings. Created an empty FAISS index.")

        faiss.write_index(index, INDEX_PATH)
        with open(CHUNK_INFOS_PATH, 'w') as f:
            json.dump(remaining_chunk_infos, f)

        delete_end = time.time()
        print("Delete time: ", delete_end - delete_start)
        print("Chunks successfully removed from index and chunk information updated.")
    except Exception as e:
        logging.error(f"Error in delete_document_from_index: {e}")
        raise

def complete_sentence(text):
    try:
        sentences = sent_tokenize(text)
        return " ".join(sentences[:-1]) if len(sentences) > 1 else text
    except Exception as e:
        logging.error(f"Error in complete_sentence: {e}")
        raise
# def get_answer(question, documents, max_context_length=10000, top_k=25, retries=3, timeout_duration=60):
#     try:
#         logging.info("Generating answer for the question...")

#         question_embedding = embed_text([question])[0]
#         if is_chunk_infos_empty(INDEX_PATH, CHUNK_INFOS_PATH):
#             yield "Lütfen dosya yükleyin"
#             return

#         index = faiss.read_index(INDEX_PATH)

#         with open(CHUNK_INFOS_PATH, 'r') as f:
#             chunk_infos = json.load(f)

#         logging.info(f"Index and chunk infos loaded successfully. Searching for top {top_k} chunks...")

#         D, I = index.search(np.array([question_embedding], dtype=np.float32), top_k)

#         ranked_chunks = [(D[0][i], chunk_infos[I[0][i]]) for i in range(top_k)]
#         ranked_chunks.sort(key=lambda x: x[0])

#         context = ""
#         used_chunk_ids = set()

#         for _, chunk_info in ranked_chunks:
#             chunk_id, doc_id, title, chunk = chunk_info
#             if len(context) + len(chunk) <= max_context_length and chunk_id not in used_chunk_ids:
#                 context += f"\n\n{title}\n{chunk}"
#                 used_chunk_ids.add(chunk_id)

#         logging.info(f"Context generated, preparing to call OpenAI API for response generation...")

#         response = None
#         for attempt in range(retries):
#             try:
#                 response = openai.ChatCompletion.create(
#                     model="gpt-4o",
#                     messages=[
#                         {"role": "system", "content": "You are a INFINIA assistant. Answer only company-related questions based on provided documents. Only use these documents to generate answers. Do not answer irrelevant questions. Consider date while answering questions"},
#                         {"role": "user", "content": f"Question: {question}\nContext: {context}"}
#                     ],
#                     #  Give reference to the sources have answer to the ONLY RELEVANT question in [] at the end of the answer. If question is irrelevant, do not put any references in [] at the end of the answer.
#                     max_tokens=1000,
#                     stream=True,
#                     timeout=timeout_duration,
#                 )
#                 break  # Exit loop if request is successful
#             except openai.error.Timeout as e:
#                 logging.warning(f"OpenAI API request timed out on attempt {attempt + 1}. Retrying...")
#             except openai.error.APIError as e:
#                 logging.warning(f"OpenAI API error on attempt {attempt + 1}: {e}. Retrying...")
#             except Exception as e:
#                 logging.error(f"Unexpected error on attempt {attempt + 1}: {e}.")
#                 break  # Break if it's a non-recoverable error
#             time.sleep(2)  # Optional: wait before retrying

#         if response is None:
#             yield "API is currently unresponsive. Please try again later."
#             return

#         for chunk in response:
#             if 'choices' in chunk:
#                 for choice in chunk['choices']:
#                     if 'delta' in choice and 'content' in choice['delta']:
#                         yield choice['delta']['content']
#     except Exception as e:
#         logging.error(f"Error in get_answer: {e}")
#         yield "An error occurred while generating the answer. Please try again later."

def get_answer(question, documents, max_context_length=10000, top_k=25, retries=3, timeout_duration=60):
    try:
        logging.info("Generating answer for the question...")

        question_embedding = embed_text([question])[0]
        if is_chunk_infos_empty(INDEX_PATH, CHUNK_INFOS_PATH):
            yield "Lütfen dosya yükleyin"
            return

        index = faiss.read_index(INDEX_PATH)

        with open(CHUNK_INFOS_PATH, 'r') as f:
            chunk_infos = json.load(f)

        logging.info(f"Index and chunk infos loaded successfully. Searching for top {top_k} chunks...")

        D, I = index.search(np.array([question_embedding], dtype=np.float32), top_k)

        # Log the size of the search results and chunk infos for debugging
        num_results = len(I[0])  # Get the actual number of results returned
        num_chunks = len(chunk_infos)
        logging.info(f"Found {num_results} relevant document chunks. Chunk infos size: {num_chunks}")

        ranked_chunks = []
        
        for i in range(min(num_results, top_k)):  # Only iterate over available results
            if I[0][i] < num_chunks:  # Check if the index is within the bounds of chunk_infos
                ranked_chunks.append((D[0][i], chunk_infos[I[0][i]]))
            else:
                # Log an error if the index is out of bounds
                logging.error(f"Index {I[0][i]} is out of bounds for chunk_infos with size {num_chunks}")
        
        if not ranked_chunks:
            logging.error("No valid ranked chunks found. Exiting...")
            yield "No valid results found for this question."
            return

        ranked_chunks.sort(key=lambda x: x[0])

        context = ""
        used_chunk_ids = set()

        for _, chunk_info in ranked_chunks:
            chunk_id, doc_id, title, chunk = chunk_info
            if len(context) + len(chunk) <= max_context_length and chunk_id not in used_chunk_ids:
                context += f"\n\n{title}\n{chunk}"
                used_chunk_ids.add(chunk_id)

        logging.info(f"Context generated, preparing to call OpenAI API for response generation...")

        response = None
        for attempt in range(retries):
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are a INFINIA assistant. Answer only company-related questions based on provided documents. Only use these documents to generate answers. Do not answer irrelevant questions. Consider date while answering questions"},
                        {"role": "user", "content": f"Question: {question}\nContext: {context}"}
                    ],
                    max_tokens=1000,
                    stream=True,
                    timeout=timeout_duration,
                )
                break  # Exit loop if request is successful
            except openai.error.Timeout as e:
                logging.warning(f"OpenAI API request timed out on attempt {attempt + 1}. Retrying...")
            except openai.error.APIError as e:
                logging.warning(f"OpenAI API error on attempt {attempt + 1}: {e}. Retrying...")
            except Exception as e:
                logging.error(f"Unexpected error on attempt {attempt + 1}: {e}.")
                break  # Break if it's a non-recoverable error
            time.sleep(2)  # Optional: wait before retrying

        if response is None:
            yield "API is currently unresponsive. Please try again later."
            return
         # Stream the response in sentences rather than cutting words
        accumulated = ""
        for chunk in response:
            if 'choices' in chunk:
                for choice in chunk['choices']:
                    if 'delta' in choice and 'content' in choice['delta']:
                        accumulated += choice['delta']['content']
                        sentences = accumulated.split(". ")
                        
                        for sentence in sentences[:-1]:  # Stream all complete sentences
                            print(sentence + "\n")
                            yield sentence + ". "  # Ensure a space after each sentence
                        accumulated = sentences[-1]  # Keep the last incomplete sentence in buffer

        # Yield any remaining part in the buffer
        if accumulated:
            yield accumulated

    except Exception as e:
        logging.error(f"Error in get_answer: {e}")
        yield "An error occurred while generating the answer. Please try again later."
