from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.base import BaseStore


from multi_agent.main_agent.nodes import tools, route_message,main_agent
from multi_agent.common.main_agent_state import State  

def build_graph(store: BaseStore) -> StateGraph:
    """
    Build the state graph for the agent. This function creates a directed graph with nodes and edges.
    The graph consists of two main nodes: call_model and tools.
    """
    
    memory = MemorySaver()
    builder = StateGraph(State)

    builder.add_node("main_agent", main_agent)
    builder.add_node("tools", tools)

    builder.add_conditional_edges(
        "main_agent",
        route_message,
        {"tools": "tools", END: END,"main_agent": "main_agent"},
    )

    #Added this conditional edge in a way that the agent checks if done
    
    builder.add_conditional_edges(
    "tools",
    route_message,
    {"main_agent": "main_agent", END: END}
    )

    builder.add_edge(START, "main_agent")

    return builder.compile(checkpointer=memory, store=store)


__all__ = ["build_graph"]