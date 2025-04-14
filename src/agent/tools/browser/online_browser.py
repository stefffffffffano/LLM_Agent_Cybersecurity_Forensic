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


class WebQuickSearch(BaseModel):
    """Run a quick online search given a query"""
    query: str = Field(...)

    def run(self, llm_model, query_strategy):
        print('Original search query:', self.query)
        try:
            rag_model = Context_generator(llm=llm_model, 
                                            query_strategy=query_strategy, 
                                            n_documents_per_source=10,
                                            verbose = True)
            
            response = rag_model.invoke(self.query)
        except Exception as e:
            response = f"An error occurred during the web search: {str(e)}"
        return response



WWW_SCRAPER_PROMPT = """Your task is to create the most effective search query to find information that answers the user's question. \
Your query will be used to search the web using a web engine (e.g. google, duckduckgo).\
This is the question: {question}. 
Provide the final query without brackets.
"""

EXPANDED_QUERY_PROMPT = """You are a Language Model specialized in query expansion for Retrieval-Augmented Generation (RAG) systems. \
Your task is to modify the provided query in order to improve information retrieval. \
Ensure the expanded query remains precise and relevant to the original intent. Output the expanded query enclosed within <expanded_query> tags, \
and do not include any additional text or explanation (e.g. <expanded_query>[example_query]</expanded_query>).\
Query: {query}
Expanded Query: 
"""

class Context_generator:
    def __init__(self, 
                 llm='gpt-4o_client', 
                 embedder='openai', 
                 query_strategy='standard',
                 n_documents_per_source=10,
                 context_length=5,
                 verbose=False):
        
        self.llm = llm
        if embedder == 'openai':
            self.embedder = 'openai'
        else:
            self.embedder = SentenceTransformer(embedder)
        self.query_strategy = query_strategy
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
            response = requests.get(url, timeout=5)  # timeout aggiunto
            content_type = response.headers.get("Content-Type", "")
            if not content_type.startswith("text/html"):
                if self.verbose:
                    print(f"[SKIP] Content-Type non valido: {content_type}")
                return None

            soup = BeautifulSoup(response.content, 'html.parser')
            for script_or_style in soup(['script', 'style']):
                script_or_style.decompose()
            text = soup.get_text()
            text = re.sub(r'\s+', ' ', text).strip()

            # Filtra contenuti troppo brevi o sospetti
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


    def parse_query(self, answer):
        start_tag = "<expanded_query>"
        end_tag = "</expanded_query>"
        start_index = answer.find(start_tag) + len(start_tag)
        end_index = answer.find(end_tag)
        if start_index != -1 and end_index != -1:
            answer = answer[start_index:end_index].strip()
        return answer
    
    def expand_query(self, query):
        prompt = EXPANDED_QUERY_PROMPT.format(query=query)
        messages = [HumanMessage(content=prompt)]
        response = self.llm.invoke(messages)
        expanded_query = self.parse_query(response.content)
        if self.verbose:
            print('Expanded query for retrieval:', expanded_query)
        return expanded_query

    def invoke(self, query):
        # Whether to use the user query or a different strategy (e.g. query expansion)
        if self.query_strategy == 'standard':
            query_to_embedd = query
        elif self.query_strategy == 'expansion':
            query_to_embedd = self.expand_query(query)
        elif self.query_strategy == 'multi_query':
            # TODO implement multi-query expansion
            pass
        else:
            raise ValueError(f"query_strategy ({self.query_strategy}) not implemented")
        
        print('Query to embed:', query_to_embedd)
        prompt = WWW_SCRAPER_PROMPT.format(question=query)
        messages = [HumanMessage(content=prompt)]
        #Tends to lose the context when doing this way
        search_query = self.llm.invoke(messages).content
        print('Search query:', search_query)
        
        documents = self.get_web_search_results(search_query)
        if self.verbose:
            print('Number of web pages obtained for the given query:', len(documents))  
        
        # Now the different documents have to be divided into smaller pieces according to the chunking strategy.
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
            context = self.embedd_and_rank_text(query_to_embedd, chunks, self.embedder)
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
    llm_model: Annotated[object, InjectedToolArg],
    query_strategy: Annotated[str, InjectedToolArg] = "standard"
) -> str:
    tool = WebQuickSearch(query=query)
    return tool.run(llm_model=llm_model, query_strategy=query_strategy)

#Tool used for binding
web_quick_search = Tool(
    name="web_quick_search",
    description="""Perform a quick web search using a retrieval-augmented generation (RAG) approach.
    Use this tool to find the latest information on a specific topic if they are not in your memory nor \
    in your training knowledge.
    You can call this tool only once per step, avoid multiple calls to this tool in the same step.
    Args:
        query: The search query. For example:
            "What are the latest advances in quantum computing?"
    """,
    args_schema=WebQuickSearchArgs,
    func=web_quick_search_func
)

__all__ = ["web_quick_search", "web_quick_search_func"]