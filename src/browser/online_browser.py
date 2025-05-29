import os
import re
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from pydantic import BaseModel

from langchain_core.tools import Tool
from .chunking_utils import ChunkingHandler
from .summarization_utils import SummarizationHandler

class Context_generator:
    def __init__(self, llm, research="CVE", strategy="LLM_summary", embedder="openai", n_documents_per_source=10, context_length=5,context_window_size=8192, verbose=False):
        self.llm = llm
        self.verbose = verbose
        self.research = research
        self.strategy = strategy
        self.n_documents_per_source = n_documents_per_source
        self.context_length = context_length
        self.chunker = ChunkingHandler(embedder=embedder, verbose=verbose)
        self.summarizer = SummarizationHandler(llm, research=research, verbose=verbose,context_window_size=context_window_size)

        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.google_cse_id = os.getenv("GOOGLE_CSE_ID")

        if not self.google_api_key or not self.google_cse_id:
            raise ValueError("GOOGLE_API_KEY and GOOGLE_CSE_ID must be set as environment variables.")

    def is_text_clean(self, text):
        try:
            text.encode('utf-8').decode('utf-8')
            return True
        except UnicodeDecodeError:
            return False

    def extract_and_clean_content(self, url):
        try:
            response = requests.get(url, timeout=10)
            if not response.headers.get("Content-Type", "").startswith("text/html"):
                return None

            soup = BeautifulSoup(response.content, 'html.parser')
            for tag in soup(['script', 'style']):
                tag.decompose()
            text = re.sub(r'\s+', ' ', soup.get_text()).strip()
            return text if len(text) >= 50 and self.is_text_clean(text) else None
        except:
            return None

    def get_web_search_results(self, query):
        print("Searching with Google API...")
        documents = []
        params = {'q': query, 'key': self.google_api_key, 'cx': self.google_cse_id, 'start': 1}
        try:
            response = requests.get("https://www.googleapis.com/customsearch/v1", params=params, timeout=10)
            results = response.json().get("items", [])
        except:
            return []

        for item in tqdm(results, disable=not self.verbose, leave=False):
            url = item.get("link")
            doc = self.extract_and_clean_content(url)
            if url and doc:
                documents.append((url, doc))
            if len(documents) >= self.n_documents_per_source:
                break
        return documents

    def invoke(self, query):
        print("Query:", query)
        docs = self.get_web_search_results(query)
        if not docs:
            return "No documents retrieved from web search."

        input_token_count = 0
        output_token_count = 0

        if self.strategy == "LLM_summary":
            summaries = {}
            for url, doc in tqdm(docs, desc="Summarizing", disable=not self.verbose, leave=False):
                summary, in_tok, out_tok = self.summarizer.summarize(doc, query)
                input_token_count += in_tok
                output_token_count += out_tok
                if summary:
                    summaries[url] = summary
            if not summaries:
                return ("No relevant summaries could be extracted.", input_token_count, output_token_count)
            final_summary, agg_in, agg_out = self.summarizer.aggregate(summaries, query)
            return (final_summary, input_token_count + agg_in, output_token_count + agg_out)

        elif self.strategy == "chunking":
            chunks = []
            for _, doc in docs:
                chunks.extend(self.chunker.chunk_text(doc))
            if not chunks:
                return "No content found for chunking."
            top_chunks = self.chunker.embedd_and_rank_text(query, chunks, self.context_length)
            return ('\n'.join(f"Information {i+1}: {chunk}" for i, chunk in enumerate(top_chunks)), input_token_count, output_token_count)

        else:
            raise NotImplementedError(f"Strategy {self.strategy} not supported.")

# Tool wrapper
class WebQuickSearchArgs(BaseModel):
    query: str

def web_quick_search_func(query: str, llm_model: object,context_window_size: int = 8192, research: str = "CVE", strategy: str = "LLM_summary") -> tuple[str, int, int]:
    try:
        rag_model = Context_generator(
            llm=llm_model,
            n_documents_per_source=10,
            verbose=True,
            research=research,
            strategy=strategy,
            context_window_size=context_window_size,
        )
        result = rag_model.invoke(query)
        return result if isinstance(result, tuple) else (result, 0, 0)
    except Exception as e:
        return (f"An error occurred during the web search: {str(e)}", 0, 0)

web_quick_search = Tool(
    name="web_quick_search",
    description="""Perform a quick web search. 
    Use this tool to find the latest information on a specific topic if it is not in your memory
    or training knowledge. You can call this tool only once per step.
    Args:
        query: The search query. 
    IMPORTANT: 
    -Do not report a CVE code in the search query, just report the service name (with the version, if possible) and the type of 
    attack exploited, if you know it.
    - Do not iterate repating the same or similar queries many times, as this will not improve the results.
    """,
    args_schema=WebQuickSearchArgs,
    func=web_quick_search_func
)

__all__ = ["web_quick_search", "web_quick_search_func"]
