from pydantic import BaseModel
from langchain_core.tools import Tool

from multi_agent.common.tshark_expert_state import State
from multi_agent.tshark_expert import build_graph

import uuid

class TsharkExpertArgs(BaseModel):
    task: str

def tshark_expert_func(
    task: str,
    pcap_path: str,
) -> str:
    """
    Run a forensic analysis on a given PCAP file based on a specified task.

    The function builds and invokes the Tshark Expert graph.
    It returns the final answer if the analysis completes correctly.
    If the graph does not complete ('done' not set), it returns an error message.
    """
    # Build the Tshark Expert graph
    graph = build_graph()

    # Prepare the initial state for the sub-agent
    initial_state = State(
        pcap_path=pcap_path,
        task=task,
        messages=[],
        steps=20,  # Default maximum number of steps
        error=False
    )

    # Assign a unique thread ID for the session
    thread_id = str(uuid.uuid4())

    # Invoke the graph
    final_state = graph.invoke(
        initial_state,
        config={"configurable": {"thread_id": thread_id}}
    )

    # Check if the analysis completed successfully
    if getattr(final_state, "done", False):
        answer = final_state["messages"][-1].content
        return answer
    else:
        return "TsharkExpert analysis did not complete successfully."

# Define the LangChain Tool

tshark_expert = Tool(
    name="tshark_expert",
    description="""
    A specialized forensic sub-agent for analyzing network traffic captured in PCAP files.
    
    Input: A detailed forensic task that must include:
    - A high-level description of the analysis objective (e.g., identify protocols etc..).
    - A suggested tshark command to apply (e.g., 'tshark -r <pcap_path> -Y "tcp.port == 4369" -O tcp').
    This has to be provided in the form:
    High level description of the analysis objective: <description>
    Suggested tshark command: <command>

    Behavior:
    - The Tshark Expert attempts to execute the suggested command on the provided PCAP.
    - If the command is malformed or the output is not useful, it tries to autonomously correct or adjust the query.
    - It inspects the filtered traffic, interprets the results, and produces a detailed summary.
    - If the analysis fails to complete after adjustments, it returns an error message.

    Notes:
    - This tool is designed for cybersecurity investigations, forensic workflows, and advanced packet analysis.
    - The input task must guide the Tshark Expert clearly, combining both intent and technical suggestions.
    In the output, the subagent will provide an analysis, the executed command, the output and the keyword 'completed task'.
    """,
    args_schema=TsharkExpertArgs,
    func=tshark_expert_func,
)

__all__ = ["tshark_expert", "tshark_expert_func"]
