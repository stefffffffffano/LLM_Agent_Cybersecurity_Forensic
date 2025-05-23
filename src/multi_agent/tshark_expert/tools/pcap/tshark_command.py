from pydantic import BaseModel
import subprocess
import shlex
import os

from langchain_core.tools import Tool

from multi_agent.common.utils import count_tokens


def commandExecutor_func(tshark_command: str, pcap_file: str) -> str:
    """
    Execute a pure tshark command on the given PCAP file. The maximum length of the output is limited to 70000 tokens.

    Args:
        tshark_command: The tshark command arguments (excluding '-r').
        pcap_file: The path to the PCAP file.

    Returns:
        The output of the executed command or an appropriate error message.
    """
    # Normalize path to avoid issues with backslashes
    pcap_file = os.path.abspath(os.path.normpath(pcap_file))

    try:
        parsed_args = shlex.split(tshark_command)
    except ValueError as ve:
        return f"Error parsing tshark_command: {ve}"

    full_command = ["tshark", "-r", pcap_file] + parsed_args

    try:
        result = subprocess.run(
            full_command,
            capture_output=True,
            text=True,
            check=True,
            shell=False,
        )
        out = result.stdout
        if count_tokens(out) > 70000:
            out = "Output too long, please refine your command using additional tshark options like -Y filters."
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.strip()
        # Remove the first line that contains the entire command (plus the name of the file)
        stderr_lines = stderr.splitlines()
        filtered_lines = [
            line for line in stderr_lines
            if not line.startswith("Command")  
        ]
        out = "Error executing tshark command.\n" + ("\n".join(filtered_lines) or "No further details.")

    if len(out.strip()) == 0:
        out = "No output found for the given command."

    return out


# Pydantic schema for arguments
class PCAPCommand(BaseModel):
    tshark_command: str


commandExecutor = Tool(
    name="command_executor",
    description="""
    Execute a pure tshark command on a predefined PCAP file.

    How to use:
        - Provide only tshark options and arguments, excluding the '-r' option (it is added automatically).
        - Do NOT use shell pipes (|) like grep, head, cut, etc.
        - If the output is too large, refine your query using:
            - Display filters with '-Y'
            - Selecting specific fields with '-T fields' and '-e'
            - Another type of command that still respects the high-level task assigned.

    Examples:
        - '-q -z conv,ip'
        - '-Y "http.request" -T fields -e ip.src -e http.host'
        - '-T fields -e frame.number -e frame.time'
    """,
    args_schema=PCAPCommand,
    func=commandExecutor_func,
)

__all__ = ["commandExecutor", "commandExecutor_func"]
