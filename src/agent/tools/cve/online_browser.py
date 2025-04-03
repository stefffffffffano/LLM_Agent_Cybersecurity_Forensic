from pydantic import BaseModel, Field
import requests
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
from duckduckgo_search import DDGS
import re


from langchain_core.tools import Tool
from langchain_core.tools import InjectedToolArg
from langchain_core.messages import SystemMessage, HumanMessage
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
Provide the final query without beackets.
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
                 embedder='multi-qa-mpnet-base-dot-v1', 
                 query_strategy='standard',
                 n_documents_per_source=10,
                 context_length=5,
                 verbose=False):
        
        self.llm = llm
        self.embedder = SentenceTransformer(embedder)
        self.query_strategy = query_strategy
        self.n_documents_per_source = n_documents_per_source
        self.context_length = context_length
        self.verbose = verbose
            

    def extract_and_clean_content(self, url):
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        # Remove script and style elements
        for script_or_style in soup(['script', 'style']):
            script_or_style.decompose()
        # Get text and clean it
        text = soup.get_text()
        text = re.sub(r'\s+', ' ', text)  
        text = text.strip()
        return text

    def get_web_search_results(self, query):
        print('Scraping the web...')
        results = DDGS().text(query, max_results=self.n_documents_per_source)
        documents = []
        for result in tqdm(results):
            try:
                doc = self.extract_and_clean_content(result['href'])
                documents.append(doc)
            except Exception as e:
                if self.verbose:
                    print(f"An error occurred while fetching the document: {e}")
        return documents

    def embedd_and_rank_text(self, query, chunks, model):
        query_embedding = model.encode(query, convert_to_tensor=True) 
        abstract_embeddings = model.encode(chunks, convert_to_tensor=True)
        if query_embedding.is_cuda:
            query_embedding = query_embedding.cpu()
        if abstract_embeddings.is_cuda:
            abstract_embeddings = abstract_embeddings.cpu()
        similarities = model.similarity(query_embedding, abstract_embeddings)[0]
        sorted_indices = similarities.argsort(descending=True)
        ranked_chunks = [chunks[i] for i in sorted_indices]
        if self.context_length != None:
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
        """
        expanded_query = self.llm.invoke(response_model=None,
                                         system_prompt=EXPANDED_QUERY_PROMPT.format(query=query),
                                         messages='').choices[0].message.content """
        #expanded_query = self.parse_query(expanded_query)
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
            # TODO implement multi-query explansion
            pass
        else:
            raise ValueError(f"query_strategy ({self.query_strategy}) not implemented")
        
        print('Query to embed:', query_to_embedd)
        """
        query = self.llm.invoke(response_model=None, 
                                system_prompt = WWW_SCRAPER_PROMPT.format(question=query),
                                messages='').choices[0].message.content"""
        prompt = WWW_SCRAPER_PROMPT.format(question=query)
        messages = [HumanMessage(content=prompt)]
        search_query = self.llm.invoke(messages).content

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
async def web_quick_search_func(
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

    Args:
        query: The search query. For example:
            "What are the latest advances in quantum computing?"
    """,
    args_schema=WebQuickSearchArgs,
    func=web_quick_search_func
)

__all__ = ["web_quick_search", "web_quick_search_func"]