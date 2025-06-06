from pydantic import BaseModel

from langchain_core.tools import Tool

from multi_agent.tshark_expert.tools.pcap import commandExecutor_func


"""
When ready to provide the final answer:
- Execute the final command if needed, or summarize your findings.
- You MUST always explicitly state:
    - The executed command (even if it produced no output)
    - A brief explanation if necessary
    - The final output (even if it is "No output found")
- After providing these elements, write "Task completed".

Final output format (always required, even if no output was found):
Executed command: <exact command you executed>
(Optional) Explanation: <brief explanation if needed>
Output: <the actual output from the command (e.g., results, or "No output found for the given command.")>
Remember that, in the 'output' section of the answer, you MUST provide the ACTUAL OUTPUT of the command you executed
even if it is ASCII code (possibly with the corresponding translation)
"""

class FinalAnswerArgs(BaseModel):
    report: str
    executed_command: str

def finalAnswerFormatter_func(
    report: str,
    executed_command: str,
    pcap_file: str,
) -> str:
    """Format the final answer."""
    final_report = f'Final report from the forensic expert:\n'
    final_report += report
    final_report += f'\nExecuted command: {executed_command}\n'
    command_output = commandExecutor_func(executed_command,pcap_file)
    if command_output.startswith("Error:"):
        final_report += f'\nError in the command\n'
    else:
        final_report += f'\nCommand output: {command_output}\n'
    return final_report

finalAnswerFormatter = Tool(
    name="final_answer_formatter",
    description="""Format the final answer when you want to provide it as a solution to the proposed task.
    It is fine if the command provided 'No output found for the given command.' as output, you can return it.
   
    Args: 
        report: A brief report of your analysis, mainly focusing on the adjustments you have made to the command (If any).
        executed_command: The tshark command you have executed.
    Returns:
        The final report of the attack to be returned before ending
    """,
    args_schema=FinalAnswerArgs,
    func=finalAnswerFormatter_func,
)

__all__ = ["finalAnswerFormatter", "finalAnswerFormatter_func"]