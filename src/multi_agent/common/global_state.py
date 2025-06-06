from __future__ import annotations

from dataclasses import dataclass

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from typing_extensions import Annotated


@dataclass(kw_only=True)
class State_global:
    """Main graph state."""
    messages: Annotated[list[AnyMessage], add_messages] #messages in the conversation
    steps: int #Maximum number of steps for the autonomous agent
    pcap_path: str #Path to the pcap file
    log_dir: str #Path to the directory where the logs are saved
    done: bool = False #Flag to indicate if the agent has finished its task providing an answer
    event_id: int #Event ID for the task
    call_number: int = 0 #Number of calls to the subagent
    inputTokens: int = 0 #counter for the input tokens
    outputTokens: int = 0 #counter for the output tokens
    strategy: str = "LLM_summary" #Strategy used for the web search
    next_step: str = "" #Next step to be executed by the agent when routing goes to log_reporter
    task: str = "" #Task to be executed by the log_reporter when the main agent calls it