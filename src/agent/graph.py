from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.base import BaseStore

from .nodes import store_memory, route_message,call_model
from .state import State  

def build_graph(store: BaseStore) -> StateGraph:
    memory = MemorySaver()
    builder = StateGraph(State)

    builder.add_node("call_model", call_model)
    builder.add_node("store_memory", store_memory)

    builder.add_conditional_edges(
        "call_model",
        route_message,
        {"store_memory": "store_memory", END: END},
    )

    builder.add_edge("store_memory", "call_model")
    builder.add_edge(START, "call_model")

    return builder.compile(checkpointer=memory, store=store)


__all__ = ["build_graph"]