from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from llm_as_a_judge.nodes import tools, route_message, judge
from llm_as_a_judge.state import State  

def build_graph() -> StateGraph:
    """
    Build the state graph for the agent. This function creates a directed graph with nodes and edges.
    """
    
    memory = MemorySaver()
    builder = StateGraph(State)

    builder.add_node("judge", judge)
    builder.add_node("tools", tools)


    builder.add_edge(START, "judge")

    builder.add_conditional_edges(
        "judge",
        route_message,
        {"tools": "tools", END: END,"judge": "judge"},
    )

    #Added this conditional edge in a way that the agent checks if done
    
    builder.add_conditional_edges(
    "tools",
    route_message,
    {"judge": "judge", END: END}
    )

    return builder.compile(checkpointer=memory)


__all__ = ["build_graph"]