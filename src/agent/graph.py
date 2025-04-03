from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.base import BaseStore

from agent.nodes import tools, route_message,call_model
from agent.state import State  

def build_graph(store: BaseStore) -> StateGraph:
    """
    Build the state graph for the agent. This function creates a directed graph with nodes and edges.
    The graph consists of two main nodes: call_model and tools.
    """
    
    memory = MemorySaver()
    builder = StateGraph(State)

    builder.add_node("call_model", call_model)
    builder.add_node("tools", tools)

    builder.add_conditional_edges(
        "call_model",
        route_message,
        {"tools": "tools", END: END},
    )

    builder.add_edge("tools", "call_model")
    builder.add_edge(START, "call_model")

    return builder.compile(checkpointer=memory, store=store)


__all__ = ["build_graph"]