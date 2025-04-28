from langgraph.graph import END
from langchain_core.messages import AIMessage

from multi_agent.common.tshark_expert_state import State


def route_message(state: State):
    """Determine the next step based on the presence of tool calls."""
    msg = state.messages[-1]
    if state.done or state.steps <= 0:
        # If the task is done or no steps left, return END
        return END
    if isinstance(msg, AIMessage) and msg.tool_calls:
        # If there are tool calls
        return "tools"
     
    return "tshark_expert"


