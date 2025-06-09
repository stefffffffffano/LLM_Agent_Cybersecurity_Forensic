from pydantic import BaseModel

from langchain_core.tools import Tool

from multi_agent.tshark_expert.tools.pcap import commandExecutor_func

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
    Don't make forensic conclusions on the output of the command, this is up to the forensic
    analyst with which you are collaborating.
    Args: 
        report: A brief report of your analysis, mainly focusing on the adjustments you have made to the command (If any).
        executed_command: The tshark command you have executed in the following format:
           - Provide only tshark options and arguments, excluding the '-r' option.
           Examples:
            - '-q -z conv,ip'
            - '-Y "http.request" -T fields -e ip.src -e http.host'
            - '-T fields -e frame.number -e frame.time'
    Returns:
        The final report of the attack to be returned before ending
    """,
    args_schema=FinalAnswerArgs,
    func=finalAnswerFormatter_func,
)

__all__ = ["finalAnswerFormatter", "finalAnswerFormatter_func"]