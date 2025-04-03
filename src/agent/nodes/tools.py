import asyncio

from langgraph.store.base import BaseStore
from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END

from agent.utils import split_model_and_provider
from agent.tools.memory import upsert_memory_func
from agent.tools.cve import web_quick_search_func
from agent.state import State
from agent.configuration import Configuration



async def tools(state: State,config: RunnableConfig, *, store: BaseStore):
    """
    Second node of the graph: executes the tools called by the LLM.
    It is called only if the LLM decided to call a tool.
    It is now provided with upsert_memory and web_quick_search tools.
    """
    # Extract tool calls from the last message
    tool_calls = state.messages[-1].tool_calls
    # Concurrently execute all upsert_memory calls
    tool_names = [tc["name"] for tc in tool_calls]
    if "upsert_memory" in tool_names:
        saved_memories = await asyncio.gather(
        *(
            upsert_memory_func(**tc["args"], store=store)
            for tc in tool_calls
        )
        )
        # Format the results of memory storage operations
        # This provides confirmation to the model that the actions it took were completed
        results = [
            {
                "role": "tool",
                "content": mem,
                "tool_call_id": tc["id"],
            }
            for tc, mem in zip(tool_calls, saved_memories)
        ]
        
    elif "web_quick_search" in tool_names:
        configurable = Configuration.from_runnable_config(config)
        llm = init_chat_model(**split_model_and_provider(configurable.model))
        responses = await asyncio.gather(
            *(
                web_quick_search_func(**tc["args"],llm_model=llm)
                for tc in tool_calls
            )
        )
        results = [
        {
            "role": "tool",
            "content": response,
            "tool_call_id": tc["id"],
        }
        for tc, response in zip(tool_calls, responses)
        ]
    
    else:
        raise ValueError("No valid tool calls found.")
    
    return {"messages": results}

__all__ = ["tools"]