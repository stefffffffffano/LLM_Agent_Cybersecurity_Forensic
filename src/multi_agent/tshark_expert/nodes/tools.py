from multi_agent.tshark_expert.tools.pcap import commandExecutor_func
from multi_agent.tshark_expert.tools.tshark_manual import manualSearch_func
from multi_agent.common.tshark_expert_state import State
from multi_agent.tshark_expert.tools.report import finalAnswerFormatter_func

def tools(state: State) -> dict:
    """
    Executes the tools called by the LLM.
    """

    tool_calls = state.messages[-1].tool_calls
    
    if not tool_calls:
        raise ValueError("No tool calls found.")

    results = []

    # Handles manual search -> the LLM passes one single argument: searchString
    manual_search_calls = [tc for tc in tool_calls if tc["name"] == "manual_search"]

    if manual_search_calls:
        manual_content = [
            manualSearch_func(**tc["args"])
            for tc in manual_search_calls
        ]
        results.extend([
            {
                "role": "tool",
                "content": f"{content}",
                "tool_call_id": tc["id"],
            }
            for tc, content in zip(manual_search_calls, manual_content)
        ])

    # Handles command execution -> the LLM passes one single argument: tshark_command
    command_executor_calls = [tc for tc in tool_calls if tc["name"] == "command_executor"]

    if command_executor_calls:
        command_content = [
            commandExecutor_func(**tc["args"], pcap_file=state.pcap_path)
            for tc in command_executor_calls
        ]
        results.extend([
            {
                "role": "tool",
                "content": f"\nResult of command {tc['args']}:  {content}",
                "tool_call_id": tc["id"],
            }
            for tc, content in zip(command_executor_calls, command_content)
        ])

    #Handles final answer formatter
    final_answer_calls = [tc for tc in tool_calls if tc["name"] == "final_answer_formatter"]
    final_answer_call = final_answer_calls[0] if final_answer_calls else None
    if final_answer_calls:
        final_answer_content = finalAnswerFormatter_func(**final_answer_call["args"],pcap_file=state.pcap_path)
        
        results.extend([
            {
                "role": "tool",
                "content": f"{final_answer_content}",
                "tool_call_id": final_answer_call["id"],
            }
        ])
        return {
            "messages": results,
            "steps": state.steps - 1,
            "done": True,
        }
    
    return {
        "messages": results,
        "steps": state.steps - 1,
    }


__all__ = ["tools"]