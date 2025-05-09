from __future__ import annotations

from dataclasses import dataclass

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from typing_extensions import Annotated


@dataclass(kw_only=True)
class State_tshark_expert:
    """Tshark expert graph state."""
    messages: Annotated[list[AnyMessage], add_messages] #messages in the conversation
    steps: int #Maximum number of steps for the autonomous agent
    pcap_path: str #Path to the pcap file
    task: str #Task to be performed
    done: bool=False #Done flag
    inputTokens: int = 0
    outputTokens: int = 0