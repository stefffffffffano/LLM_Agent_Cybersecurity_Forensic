from langgraph.graph import END
from langchain_core.messages import AIMessage

from multi_agent.common.tshark_expert_state import State_tshark_expert


def route_message(state: State_tshark_expert):
    """Determine the next step based on the presence of tool calls."""
    if len(state.messages) == 0:
        #return the initial node if there are no messages
        return "tshark_expert"
    msg = state.messages[-1]
    if state.done or state.steps <= 0:
        # If the task is done or no steps left, return END
        return END
    if isinstance(msg, AIMessage) and msg.tool_calls:
        # If there are tool calls
        return "tools"
     
    return "tshark_expert"


