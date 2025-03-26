"""Graphs that extract memories on a schedule."""
import asyncio
import logging
from datetime import datetime

from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from langgraph.store.base import BaseStore

from memory_agent import configuration, tools, utils
from memory_agent.state import State
from memory_agent.utils import count_tokens

logger = logging.getLogger(__name__)

# Initialize the language model to be used for memory extraction
llm = init_chat_model()




"""
from functools import partial


def create_graph(store):
    builder = StateGraph(State, config_schema=configuration.Configuration)

    builder.add_node("call_model", partial(call_model, store=store))
    builder.add_edge("__start__", "call_model")
    builder.add_node("store_memory", partial(store_memory, store=store))
    builder.add_conditional_edges("call_model", route_message, ["store_memory", END])
    builder.add_edge("store_memory", "call_model")

    graph = builder.compile()
    graph.name = "MemoryAgent"
    return graph
"""


async def call_model(state: State, config: RunnableConfig, *, store: BaseStore) -> dict:
    """The prompt is built following MEMGPT implementation.
        System instructions: automatically managed by LangGraph when binding a tool by copying the docstring
        Working context: retrieved semantically from memory based on latest messages
        FIFO Queue: last messages of the conversation

        There is a limit defined in the configuration file for the working context and the FIFO Queue,
        in order to be sure that we do not go over the context window.
        We count token using tiktokens with an utility function defined in memory_agent/utils.py.
    """

    #retrieve constants from the configuration file
    configurable = configuration.Configuration.from_runnable_config(config)
    #Limits passed in the configuration
    MAX_FIFO_TOKENS = configurable.max_fifo_tokens
    MAX_WORKING_CONTEXT_TOKENS = configurable.max_working_context_tokens
    fifo_token_counter = 0
    fifo_messages_to_be_included = 0
    working_context_token_counter = 0
    working_context_messages_to_be_included = 0


    #FIFO prompt: iterate over messages and build the FIFO prompt by concateneting messages unitl we are below the max_fifo_tokens
    for m in state.messages[:]:
        fifo_token_counter+=count_tokens(m)
        if(fifo_token_counter<MAX_FIFO_TOKENS):
            fifo_messages_to_be_included+=1
    
    # Semantic search in the db, retrieve 10 messages that are relevant with respect to the context
    #Memories are already ordered based on similarity score-> the error is in the next 21 lines
    memories = await store.asearch(
        ("memories"),
        query=str([m.content for m in state.messages[-3:]]),
        limit=10,
    )

    memories=None
    if(memories):
        for mem in memories:
            working_context_token_counter+=count_tokens(mem)
            if(working_context_token_counter<MAX_WORKING_CONTEXT_TOKENS):
                working_context_messages_to_be_included+=1
        
        #Prepare the fifo prompt: just include who said it and what said
        working_context = "\n".join(
        f"{m.key.upper()}: {m.value}, similarity: {m.score}" for m in memories[0:working_context_messages_to_be_included]
        )
        if working_context:
            working_context=f"""
            You are provided with contextual memories retrieved from past interactions.\n
            Use them if they are relevant:\n\n
            <memories>
            {working_context}
            </memories>
            """
    else:
        working_context = ""

    # Prepare the system prompt with user memories and current time
    # This helps the model understand the context and temporal relevance
    sys = configurable.system_prompt.format(
        user_info=working_context, time=datetime.now().isoformat() #in the template they also used a timestamp to help the LLM getting the flow of the conversation
    )

    # Invoke the language model with the prepared prompt and tools
    # "bind_tools" gives the LLM the JSON schema for all tools in the list so it knows how
    # to use them.
    msg = await llm.bind_tools([tools.upsert_memory]).ainvoke(
        [{"role": "system", "content": sys}, *state.messages[-fifo_messages_to_be_included:]],
        {"configurable": utils.split_model_and_provider(configurable.model)},
    )
    return {"messages": [msg]}


async def store_memory(state: State, config: RunnableConfig, *, store: BaseStore):
    # Extract tool calls from the last message
    tool_calls = state.messages[-1].tool_calls
    # Concurrently execute all upsert_memory calls
    saved_memories = await asyncio.gather(
        *(
            tools.upsert_memory(**tc["args"], store=store)
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


# Create the graph + all nodes
builder = StateGraph(State, config_schema=configuration.Configuration)

# Define the flow of the memory extraction process
builder.add_node(call_model)
builder.add_edge("__start__", "call_model")
builder.add_node(store_memory)
builder.add_conditional_edges("call_model", route_message, ["store_memory", END])
# Right now, we're returning control to the user after storing a memory
# Depending on the model, you may want to route back to the model
# to let it first store memories, then generate a response
builder.add_edge("store_memory", "call_model")
graph = builder.compile()
graph.name = "MemoryAgent"


__all__ = ["graph"]

"""
Stefano è uno studente di 23 anni di ingegneria informatica al politecnico di Torino, sta lavorando a una tesi su AI agents per valutarne il funzionamento in cybersecurity forensic"""