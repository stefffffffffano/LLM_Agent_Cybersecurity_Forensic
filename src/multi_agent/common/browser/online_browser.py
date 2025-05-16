import os
import re
import requests
import numpy as np
from bs4 import BeautifulSoup
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from openai import OpenAI
from pydantic import BaseModel

from langchain_core.messages import HumanMessage
from langchain_core.tools import Tool



class Context_generator:
    def __init__(self, 
                 llm, 
                 research: str = "CVE",
                 strategy: str = "LLM_summary",
                 embedder='openai', 
                 n_documents_per_source=10,
                 context_length=5,
                 verbose=False):

        self.llm = llm
        self.verbose = verbose
        self.research = research
        self.strategy = strategy
        self.n_documents_per_source = n_documents_per_source
        self.context_length = context_length

        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.google_cse_id = os.getenv("GOOGLE_CSE_ID")

        if not self.google_api_key or not self.google_cse_id:
            raise ValueError("GOOGLE_API_KEY and GOOGLE_CSE_ID must be set as environment variables.")

        if embedder == 'openai':
            self.embedder = 'openai'
        else:
            self.embedder = SentenceTransformer(embedder)

    def is_text_clean(self, text):
        try:
            text.encode('utf-8').decode('utf-8')
            return True
        except UnicodeDecodeError:
            return False

    def extract_and_clean_content(self, url):
        try:
            response = requests.get(url, timeout=10)
            content_type = response.headers.get("Content-Type", "")
            if not content_type.startswith("text/html"):
                if self.verbose:
                    print(f"[SKIP] {url} - Content-Type not valid: {content_type}")
                return None

            soup = BeautifulSoup(response.content, 'html.parser')
            for script_or_style in soup(['script', 'style']):
                script_or_style.decompose()
            text = soup.get_text()
            text = re.sub(r'\s+', ' ', text).strip()

            if len(text) < 50 or not self.is_text_clean(text):
                return None

            return text
        except Exception as e:
            if self.verbose:
                print(f"[ERROR] Failed to fetch {url}: {e}")
            return None

    def get_web_search_results(self, query):
        print('Searching with Google API...')
        documents = []
        start = 1

        while len(documents) < self.n_documents_per_source:
            params = {
                'q': query,
                'key': self.google_api_key,
                'cx': self.google_cse_id,
                'start': start,
            }
            try:
                response = requests.get("https://www.googleapis.com/customsearch/v1", params=params, timeout=10)
                response.raise_for_status()
                results = response.json()
            except Exception as e:
                if self.verbose:
                    print(f"[GOOGLE SEARCH ERROR] {e}")
                break

            items = results.get("items", [])
            if not items:
                break

            for item in tqdm(items, disable=not self.verbose):
                url = item.get("link")
                if not url:
                    continue
                doc = self.extract_and_clean_content(url)
                if doc:
                    documents.append((url, doc))
                if len(documents) >= self.n_documents_per_source:
                    break

            start += 10

        return documents

    def summarize_with_llm(self, content: str, query: str, character_limit: int = 600) -> str:
        if self.research == "CVE":
            prompt = (
                f"You are an AI assistant tasked with summarizing content relevant to '{query}' for a forensic analyst\
                that is trying to identify the CVE related to a specific service/application. "
                f"Please provide a concise summary in {character_limit} characters or less where you highlight your findings\
                for each CVE detected in the web page."
            )
        else: 
            prompt = (
                f"You are an AI assistant tasked with summarizing content relevant to '{query}' for a forensic analyst\
                that is trying to execute tshark commands in the most effective way, trying to solve errors and applying filters. "
                f"Please provide a concise summary in {character_limit} characters or less where you highlight your findings."
            )
        try:
            messages = [
                HumanMessage(role="system", content=prompt),
                HumanMessage(role="user", content=content[:300000])
            ]
            response = self.llm.invoke(messages)
            #Count input and output tokens
            input_token_count = response.response_metadata.get("token_usage", {}).get("prompt_tokens", 0)
            output_token_count = response.response_metadata.get("token_usage", {}).get("completion_tokens", 0)
            return (response.content.strip(),input_token_count,output_token_count)
        except Exception as e:
            if self.verbose:
                print(f"[LLM SUMMARY ERROR] {e}")
            return (None,0,0)

    def get_openai_embeddings(self, texts, batch_size=100):
        texts = [t.strip() for t in texts if t and t.strip() != "" and self.is_text_clean(t)]

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
                sorted_data = sorted(response.data, key=lambda x: x.index)
                batch_embeddings = [np.array(r.embedding) for r in sorted_data]
                all_embeddings.extend(batch_embeddings)
            except Exception as e:
                if self.verbose:
                    print(f"[EMBED ERROR] Error during embedding batch {i}: {e}")

        return all_embeddings

    def cosine_similarity(self, a, b):
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    

    def embedd_and_rank_text(self, query, chunks):
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
        print("Query:", query)
        results = self.get_web_search_results(query)

        if self.verbose:
            print(f"Fetched {len(results)} documents")

        if not results:
            return "No documents retrieved from web search."
        #Count tokens (In case LLM is used to summarize)
        input_token_count = 0
        output_token_count = 0
        if self.strategy == "LLM_summary":
            summary_dict = {}
            for url, doc in tqdm(results, desc="Summarizing", disable=not self.verbose):
                (summary,inputCount,outputCount) = self.summarize_with_llm(doc, query)
                input_token_count += inputCount
                output_token_count += outputCount
                if summary:
                    summary_dict[url] = summary

            if not summary_dict:
                return "No relevant summaries could be extracted from the search results. Try refining your query."

            summaries = list(summary_dict.values())
            urls = list(summary_dict.keys())

            # Embedding e ranking
            try:
                ranked_summaries = self.embedd_and_rank_text(query, summaries)
            except Exception as e:
                if self.verbose:
                    print(f"[EMBEDDING ERROR] {e}")
                return "An error occurred while computing semantic similarities."

            # Ricostruzione output con URL
            ranked_pairs = [(url, summary_dict[url]) for url in urls if summary_dict[url] in ranked_summaries]
            ranked_output = [f"{url}: {summary}" for url, summary in ranked_pairs if summary in ranked_summaries]

            return ("\n".join(ranked_output[:self.context_length],input_token_count,output_token_count))

        else:  # strategy == "chunking"
            chunks = []
            for _, doc in results:
                if doc:
                    window_size = 512
                    step_size = 256
                    for i in range(0, len(doc), step_size):
                        chunk = doc[i:i + window_size]
                        if chunk:
                            chunks.append(chunk)

            chunks = [chunk for chunk in chunks if chunk.strip()]
            if self.verbose:
                print(f'Number of chunks: {len(chunks)}')

            if not chunks:
                return "No relevant content could be extracted for chunk-based retrieval."

            try:
                top_chunks = self.embedd_and_rank_text(query, chunks)
            except Exception as e:
                if self.verbose:
                    print(f"[EMBEDDING ERROR] {e}")
                return "An error occurred while computing semantic similarities."

            if self.verbose:
                print(f'Context length: {len(top_chunks)}')

            return ('\n'.join([f'Information {i+1}: {chunk}' for i, chunk in enumerate(top_chunks)]),input_token_count,output_token_count) #counter = 0 in this case


# Pydantic schema for arguments
class WebQuickSearchArgs(BaseModel):
    query: str

# Executed asynchronous function
def web_quick_search_func(
    query: str,
    llm_model: object,
    research: str = "CVE", #It could be CVE or tshark based on which agent is calling it (the prompt changes) 
    strategy: str = "LLM_summary", #It could be LLM_summary or chuncking
) -> str:
    try:
        rag_model = Context_generator(
            llm=llm_model,
            n_documents_per_source=10,
            verbose=True,
            research=research,
            strategy=strategy,
        )
        response = rag_model.invoke(query)
    except Exception as e:
        response = f"An error occurred during the web search: {str(e)}"
    return response

# Tool used for binding
web_quick_search = Tool(
    name="web_quick_search",
    description="""Perform a quick web search. 
    Use this tool to find the latest information on a specific topic if it is not in your memory
    or training knowledge. You can call this tool only once per step.
    Args:
        query: The search query. 
    """,
    args_schema=WebQuickSearchArgs,
    func=web_quick_search_func
)

__all__ = ["web_quick_search", "web_quick_search_func"]
