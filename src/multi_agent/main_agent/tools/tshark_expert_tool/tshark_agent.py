from pydantic import BaseModel
from langchain_core.tools import Tool

from multi_agent.common.tshark_expert_state import State
from multi_agent.tshark_expert import build_graph

import uuid
import os
import json

class TsharkExpertArgs(BaseModel):
    task: str

def tshark_expert_func(
    task: str,
    pcap_path: str,
    event_id: int,
    call_number: int,
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
     
    # Save the conversation logs
    log_dir = f"subagent_logs/event_{event_id}"
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, f"subagent_call_{call_number}.txt")

    with open(log_file_path, "w", encoding="utf-8") as f:
        for msg in final_state.get("messages", []):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                f.write("TOOL CALL:\n")
                for call in msg.tool_calls:
                    f.write(f"- tool name: {call['name']}\n")
                    f.write(f"- args: {json.dumps(call['args'], indent=2)}\n")
            else:
                f.write(f"{msg.content}\n")
            f.write("\n---\n\n")

    answer = "TsharkExpert analysis did not complete successfully."
    input_tokens_count = final_state["inputTokens"]
    output_tokens_count = final_state["outputTokens"]
    # Check if the analysis completed successfully
    if final_state.get("done", False):
        answer = final_state["messages"][-1].content
        return (answer,input_tokens_count,output_tokens_count)
    else:
        return (answer,input_tokens_count,output_tokens_count)

# Define the LangChain Tool

tshark_expert = Tool(
    name="tshark_expert",
    description="""
    A specialized sub-agent for executing tshark commands on PCAP files.
    Input requirements:
    - A precise technical goal (e.g., extract fields, decode payloads, filter sessions,extract TCP traffic on port x).
    This has to be provided in the form:
    Description of the analysis objective: <description>

    Behavior:
    - The Tshark Expert attempts to execute a tshark command to accomplish the task assigned.
    - If the command is malformed or the output is not useful, it tries to autonomously correct or adjust the query.
    - If the analysis fails to complete after adjustments, it returns an error message.
    Guidelines for using the tshark_expert:
    - Provide clear, high-level objectives in your request (e.g., "Extract HTTP requests and their headers", "Find all TCP retransmissions").
    - If the task is related to a specific CVE, you must translate the CVE impact into a network behavior or observable pattern (e.g., "Look for signs of remote code execution attempts").
    - Avoid asking the tshark_expert to identify CVEs, exploits, vulnerabilities, or application-specific logic, he doesn’t know about those details.
    - The sub-agent expects technical goals (such as "extract fields", "filter packets matching condition X") expressed in network analysis terms.
    Important:
    - This agent can optimize tshark commands but cannot independently infer complex forensic conclusions (e.g., exploitation detection must be guided by specific data extraction instructions).
    - DO NOT ASK FOR SIGN OF EXPLOITATION OF SPECIFIC SERVICES OR CVES, THE SUBAGENT IS ONLY AN EXPERT IN TSHARK COMMANDS.
    """,
    args_schema=TsharkExpertArgs,
    func=tshark_expert_func,
)

__all__ = ["tshark_expert", "tshark_expert_func"]
