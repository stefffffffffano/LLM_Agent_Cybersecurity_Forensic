from pydantic import BaseModel
import subprocess

from langchain_core.tools import Tool
import shlex

from agent.utils import count_tokens

    

def commandExecutor_func(tshark_command: str, pcap_file: str) -> str:
    """
    Execute a tshark command on the pcap file in the terminal and return the output.
    Args:
        command: the tshark command
        pcap_file: the path to the pcap file.
    Returns:
        The output of the command.
    """
    try:
        try:
            parsed_args = shlex.split(tshark_command)
        except ValueError as ve:
            return f"Error parsing tshark_command: {ve}"

        pcap_command = ['tshark', '-r', pcap_file] + parsed_args
        
        result = subprocess.run(
            pcap_command,
            capture_output=True,
            text=True,
            check=True
        )
        out = result.stdout
        if(count_tokens(out) > 100000):
            out = "Output too long, please refine your command."
    except subprocess.CalledProcessError as e:
        out = f"Error: {e}"
    if len(out.strip()) == 0:
        out = "No output found for the given command."
    return out


#Pydantic schema for arguments
class PCAPCommand(BaseModel):
    tshark_command: str


commandExecutor = Tool(
    name="command_executor",
    description="""Execute a tshark command on a PCAP file and return the output.

    The PCAP file is predefined and does not need to be specified.

    Args:
        tshark_command: Only the tshark arguments (excluding -r). For example:
            -q -z conv,ip
            -Y "http.request" -T fields -e ip.src -e http.host
    """,
    args_schema=PCAPCommand,
    func=commandExecutor_func,
)


__all__ = ["commandExecutor", "commandExecutor_func"]