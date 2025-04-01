from datetime import datetime
import asyncio

from langgraph.store.base import BaseStore
from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END

from .utils import count_tokens, split_model_and_provider
from .tools import upsert_memory,upsert_memory_func
from .state import State
from .configuration import Configuration

from langchain_core.callbacks import BaseCallbackHandler
from typing import Any

class PromptDebugHandler(BaseCallbackHandler):
    def on_llm_start(self, serialized: dict, prompts: list[str], **kwargs: Any) -> None:
        print("\n================== FULL PROMPT SENT TO LLM ==================\n")
        for i, prompt in enumerate(prompts):
            print(f"--- Prompt {i+1} ---\n{prompt}\n")
        print("=============================================================\n")

async def call_model(state: State, config: RunnableConfig,*,store:BaseStore) -> dict:
    configurable = Configuration.from_runnable_config(config)
    MAX_FIFO_TOKENS = configurable.max_fifo_tokens
    MAX_WORKING_CONTEXT_TOKENS = configurable.max_working_context_tokens
    
    assert store is not None, "Store not injected!"
    fifo_token_counter = 0
    fifo_messages_to_be_included = 0

    # FIFO messages (from beginning)
    for m in state.messages:
        fifo_token_counter += count_tokens(m)
        if fifo_token_counter < MAX_FIFO_TOKENS:
            fifo_messages_to_be_included += 1
        else:
            break

    # Semantic search: last 3 user/assistant messages as base
    recent_messages = state.messages[-3:]
    search_query = " ".join([m.content for m in recent_messages if hasattr(m, "content")])
    results = await store.asearch("memories", query=search_query, limit=10)
    working_context_token_counter = 0
    working_context = []
    for mem in results:
        content = mem.value.get("content", "")
        context = mem.value.get("context", "")
        mem_str = f"{content} ({context})"
        tok = count_tokens(mem_str)
        if working_context_token_counter + tok < MAX_WORKING_CONTEXT_TOKENS:
            working_context.append(f"{mem.key.upper()}: {mem_str}, score={mem.score:.2f}")
            working_context_token_counter += tok
        else:
            break

    if working_context:
        working_context_str = "\n".join(working_context)
        working_context_prompt = f"""
        You are provided with contextual memories retrieved from past interactions.
        Use them if they are relevant.

        <memories>
        {working_context_str}
        </memories>
        """
    else:
        working_context_prompt = ""


    system_prompt = configurable.system_prompt.format(
        user_info=working_context_prompt,
        time=datetime.now().isoformat()
    )

    # Initialize the language model to be used for memory extraction
    llm = init_chat_model(**split_model_and_provider(configurable.model))

    

    debug_config = RunnableConfig(callbacks=[PromptDebugHandler()])
    llm_with_tools = llm.bind_tools([upsert_memory])

    messages = [{"role": "system", "content": system_prompt}, *state.messages[-fifo_messages_to_be_included:]]

    msg = await llm_with_tools.ainvoke(messages, config=debug_config)

    """
    msg = await llm.bind_tools([upsert_memory]).ainvoke(
        [{"role": "system", "content": system_prompt}, *state.messages[-fifo_messages_to_be_included:]]
    )"""

    return {"messages": [msg]}




async def store_memory(state: State, *, store: BaseStore):
    # Extract tool calls from the last message
    tool_calls = state.messages[-1].tool_calls
    # Concurrently execute all upsert_memory calls
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
    return {"messages": results}


def route_message(state: State):
    """Determine the next step based on the presence of tool calls."""
    msg = state.messages[-1]
    if msg.tool_calls:
        # If there are tool calls, we need to store memories
        return "store_memory"
    # Otherwise, finish; user can send the next message
    return END