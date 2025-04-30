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
        steps=15,  # Default maximum number of steps
    )

    # Assign a unique thread ID for the session
    thread_id = str(uuid.uuid4())

    # Invoke the graph
    final_state = graph.invoke(
        initial_state,
        config={"configurable": {"thread_id": thread_id}}
    )
    
    # Check if the analysis completed successfully
    if final_state.get("done", False):
        answer = final_state["messages"][-1].content
        return answer
    else:
        return "TsharkExpert analysis did not complete successfully."

# Define the LangChain Tool

tshark_expert = Tool(
    name="tshark_expert",
    description="""
    A specialized sub-agent for executing tshark commands on PCAP files.
    
    Input requirements:
    - A precise technical goal (e.g., extract fields, decode payloads, filter sessions).
    - A suggested tshark command for achieving that goal.
    This has to be provided in the form:
    High level description of the analysis objective: <description>
    Suggested tshark command: <command>

    Behavior:
    - The Tshark Expert attempts to execute the suggested command on the provided PCAP.
    - If the command is malformed or the output is not useful, it tries to autonomously correct or adjust the query.
    - It inspects the filtered traffic and produces a detailed summary.
    - If the analysis fails to complete after adjustments, it returns an error message.
    Guidelines for using the tshark_expert:
    - Provide clear, high-level objectives in your request (e.g., "Extract HTTP requests and their headers", "Find all TCP retransmissions").
    - If the task is related to a specific CVE, you must translate the CVE impact into a network behavior or observable pattern (e.g., "Look for signs of remote code execution attempts").
    - Avoid asking the tshark_expert to identify CVEs, exploits, vulnerabilities, or application-specific logic.
    - The sub-agent expects technical goals (such as "extract fields", "filter packets matching condition X") expressed in network analysis terms.
    Notes:
    - This tool is designed for cybersecurity investigations, forensic workflows, and advanced packet analysis.
    - The input task must guide the Tshark Expert clearly, combining both intent and technical suggestions.
    Important:
    - This agent can optimize tshark commands but cannot independently infer complex forensic conclusions (e.g., exploitation detection must be guided by specific data extraction instructions).
    - DO NOT ASK FOR SIGN OF EXPLOITATION OF SPECIFIC SERVICES OR CVES, THE SUBAGENT IS ONLY AN EXPERT IN TSHARK COMMANDS.
    SUGGEST THE ANALYSIS AND A COMMAND (IF POSSIBLE) AND IT WILL EXECUTE IT (AND CORRECT IT, IF NECESSARY).
    """,
    args_schema=TsharkExpertArgs,
    func=tshark_expert_func,
)

__all__ = ["tshark_expert", "tshark_expert_func"]
