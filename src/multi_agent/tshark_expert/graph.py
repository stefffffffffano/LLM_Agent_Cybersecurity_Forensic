from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver


from multi_agent.tshark_expert.nodes import tools, route_message,tshark_expert
from multi_agent.common.tshark_expert_state import State  

def build_graph() -> StateGraph:
    """
    Build the state graph for the agent. This function creates a directed graph with nodes and edges.
    The graph consists of two main nodes: tshark_expert and tools.
    """
    
    memory = MemorySaver()
    builder = StateGraph(State)

    builder.add_node("tshark_expert", tshark_expert)
    builder.add_node("tools", tools)

    builder.add_conditional_edges(
        "tshark_expert",
        route_message,
        {"tools": "tools", END: END, "tshark_expert": "tshark_expert"},
    )

    builder.add_conditional_edges(
        "tools",
        route_message,
        {"tshark_expert": "tshark_expert", END: END},
    )
    
    builder.add_edge(START, "tshark_expert")

    return builder.compile(checkpointer=memory)


__all__ = ["build_graph"]