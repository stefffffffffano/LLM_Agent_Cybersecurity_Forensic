from pydantic import BaseModel

from langchain_core.tools import Tool
from langchain_core.tools import InjectedToolArg
#from langchain_community.tools.tavily_search import TavilySearchResults

from tavily import TavilyClient

from typing import Annotated
import os



#Pydantic schema for arguments
class WebQuickSearchArgs(BaseModel):
    query: str




def web_quick_search_func(
    query: str,
    *,
    llm_model: Annotated[object, InjectedToolArg],  # not used, mantained for compatibility
) -> str:
    # api key
    api_key = os.getenv("TAVILY_API_KEY")
    client = TavilyClient(api_key=api_key)

    # Request with included summary
    response = client.search(query=query, include_answer=True, max_results=5)

    # Format output
    summary = response.get("answer", "No summary available.")

    return f"\n{summary}\n"




#Tool used for binding
web_quick_search = Tool(
    name="web_quick_search",
    description="""Perform a quick web search using Tavily.
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