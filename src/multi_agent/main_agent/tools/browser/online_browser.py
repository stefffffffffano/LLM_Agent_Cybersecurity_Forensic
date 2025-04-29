from pydantic import BaseModel, Field
import requests
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
from duckduckgo_search import DDGS
import re
from openai import OpenAI
import numpy as np


from langchain_core.tools import Tool
from langchain_core.tools import InjectedToolArg
from langchain_core.messages import HumanMessage
from typing import Annotated


class Context_generator:
    def __init__(self, 
                 llm='gpt-4o_client', 
                 embedder='openai', 
                 n_documents_per_source=10,
                 context_length=5,
                 verbose=False):
        
        self.llm = llm
        if embedder == 'openai':
            self.embedder = 'openai'
        else:
            self.embedder = SentenceTransformer(embedder)
        self.n_documents_per_source = n_documents_per_source
        self.context_length = context_length
        self.verbose = verbose
    

    def is_text_clean(self, text):
        try:
            text.encode('utf-8').decode('utf-8')
            return True
        except UnicodeDecodeError:
            return False

    def extract_and_clean_content(self, url):
        try:
            response = requests.get(url, timeout=5)  # added timeout
            content_type = response.headers.get("Content-Type", "")
            if not content_type.startswith("text/html"):
                if self.verbose:
                    print(f"[SKIP] Content-Type not valid: {content_type}")
                return None

            soup = BeautifulSoup(response.content, 'html.parser')
            for script_or_style in soup(['script', 'style']):
                script_or_style.decompose()
            text = soup.get_text()
            text = re.sub(r'\s+', ' ', text).strip()

            # Filter contents
            if len(text) < 50 or not self.is_text_clean(text):
                return None

            return text

        except requests.exceptions.Timeout:
            if self.verbose:
                print(f"[TIMEOUT] Timeout for {url}")
        except requests.exceptions.RequestException as e:
            if self.verbose:
                print(f"[ERROR] Failed request for {url}: {e}")
        return None

    
    def get_web_search_results(self, query):
        print('Scraping the web...')
        results = DDGS().text(query, max_results=self.n_documents_per_source)
        documents = []

        for result in tqdm(results):
            url = result.get('href')
            if not url:
                continue
            doc = self.extract_and_clean_content(url)
            if doc:
                documents.append(doc)

        return documents

    def get_openai_embeddings(self, texts, batch_size=100):
        """Transform text into embeddings using OpenAI API, in safe batches."""
        texts = [t if t is not None else "" for t in texts]
        texts = [t.strip() for t in texts if t.strip() != "" and self.is_text_clean(t)]

        if len(texts) == 0:
            raise ValueError("No valid input texts provided to embedding function.")
        
        client = OpenAI()
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                response = client.embeddings.create(
                    input=batch,
                    model="text-embedding-3-small"
                )
                # Order based on indeces
                sorted_data = sorted(response.data, key=lambda x: x.index)
                batch_embeddings = [np.array(r.embedding) for r in sorted_data]
                all_embeddings.extend(batch_embeddings)
            except Exception as e:
                if self.verbose:
                    print(f"[EMBED ERROR] Error during embedding {i}: {e}")

        return all_embeddings

    def cosine_similarity(self, a, b):
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    def embedd_and_rank_text(self, query, chunks,model=None):
        if self.embedder == 'openai':
            embeddings = self.get_openai_embeddings([query] + chunks)
            query_embedding = embeddings[0]
            chunk_embeddings = embeddings[1:]
        else:
            query_embedding = self.embedder.encode(query)
            chunk_embeddings = self.embedder.encode(chunks)

        similarities = [self.cosine_similarity(query_embedding, emb) for emb in chunk_embeddings]
        ranked_chunks = [chunk for _, chunk in sorted(zip(similarities, chunks), key=lambda x: x[0], reverse=True)]

        if self.context_length:
            ranked_chunks = ranked_chunks[:self.context_length]
        return ranked_chunks

    def invoke(self, query):
        print('Query to embed:', query)
        documents = self.get_web_search_results(query)
        if self.verbose:
            print('Number of web pages obtained for the given query:', len(documents))  
        
        # We also remove empty chunks
        chunks = []
        for doc in documents:
            if doc!=None:
                window_size = 512
                step_size = 256
                for i in range(0, len(doc), step_size):
                    chunk = doc[i:i + window_size]
                    if chunk:
                        chunks.append(chunk)

        chunks = [chunk for chunk in chunks if chunk != '']
        if self.verbose:
            print('Number of chunks:', len(chunks))

        if len(chunks) == 0:
            context = 'No information found.'
        else:
            # The sorted chunks are generated by using the embedder to get the embeddings of the query and the chunks
            context = self.embedd_and_rank_text(query, chunks, self.embedder)
            if self.verbose:
                print('Context length:', len(context))

            # The sorted chunks are transformed into a single string
            context = '\n'.join([f'Information {i+1}: '+chunk for i, chunk in enumerate(context)])
        return context

#Pydantic schema for arguments
class WebQuickSearchArgs(BaseModel):
    query: str

#executed asynchronous function
def web_quick_search_func(
    query: str,
    *,
    llm_model: Annotated[object, InjectedToolArg]
) -> str:
    try:
        rag_model = Context_generator(llm=llm_model, 
                                            n_documents_per_source=10,
                                            verbose = True)
            
        response = rag_model.invoke(query)
    except Exception as e:
        response = f"An error occurred during the web search: {str(e)}"
    return response

#Tool used for binding
web_quick_search = Tool(
    name="web_quick_search",
    description="""Perform a quick web search.
    Use this tool to find the latest information on a specific topic if they are not in your memory nor \
    in your training knowledge.
    You can call this tool only once per step, avoid multiple calls to this tool in the same step.
    Args:
        query: The search query. For example:
            "CVEs associated with couchDB?"
    """,
    args_schema=WebQuickSearchArgs,
    func=web_quick_search_func
)

__all__ = ["web_quick_search", "web_quick_search_func"]