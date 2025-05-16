from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.base import BaseStore

from multi_agent.main_agent.nodes import tools, route_message,main_agent,pcap_flows_reporter
from multi_agent.common.global_state import State_global  
from multi_agent.log_reporter.log_reporter import log_reporter

def build_graph(store: BaseStore) -> StateGraph:
    """
    Build the state graph for the agent. This function creates a directed graph with nodes and edges.
    The graph consists of three main nodes: log_reporter, main_agent and tools.
    """
    
    memory = MemorySaver()
    builder = StateGraph(State_global)

    builder.add_node("main_agent", main_agent)
    builder.add_node("tools", tools)
    builder.add_node("log_reporter", log_reporter)
    builder.add_node("pcap_flows_reporter", pcap_flows_reporter)


    builder.add_edge(START, "log_reporter")
    builder.add_edge("log_reporter", "pcap_flows_reporter")
    builder.add_edge("pcap_flows_reporter", "main_agent")

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

    return builder.compile(checkpointer=memory, store=store)


__all__ = ["build_graph"]