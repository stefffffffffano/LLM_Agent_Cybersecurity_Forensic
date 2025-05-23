"""
This module implements a web search tool using the same quick web search that is used by the agent.
The only thing that changes is the description.

"""
from pydantic import BaseModel

from langchain_core.tools import Tool
from browser import web_quick_search_func 


# Pydantic schema for arguments
class WebSearchArgs(BaseModel):
    query: str

web_search = Tool(
    name="web_quick_search",
    description="""Perform a quick web search. 
    Use this tool to find the latest information on a specific CVE. Specify only one CVE ID in the query
    at a time.
    The tool will return the most relevant information from the web.
    Args:
        query: The search query. e.g. "CVE-2023-1234"
    """,
    args_schema=WebSearchArgs,
    func=web_quick_search_func
)

__all__ = ["web_search"]