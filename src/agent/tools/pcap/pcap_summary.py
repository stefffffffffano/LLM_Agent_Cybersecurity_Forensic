"""
Executes the command tshark -r <pcap_file> -q -z conv,ip on the pcap file and returns the output.
It is used to be placed in the prompt, it's not a tool.
It shows a table of IP conversations, with columns like:

    -Source IP ↔ Destination IP

    -Number of packets and bytes sent in each direction

    -Total packets and bytes

    -Duration of each conversation

This is useful for identifying the main endpoints communicating in a capture and the amount of data exchanged.
"""

import subprocess

def generate_summary(pcap_file: str) -> str:
    """
    Execute tshark -r <pcap_file> -q -z conv,ip on the pcap file in the terminal and return the output.
    Args:
        pcap_file: the path to the pcap file.
    Returns:
        The output of the command.
    """
    try:
        pcap_command = ['tshark', '-r', pcap_file, '-q', '-z', 'conv,ip']

        result = subprocess.run(
            pcap_command,
            capture_output=True,
            text=True,
            check=True
        )
        out = result.stdout
    except subprocess.CalledProcessError as e:
        out = f"Error: {e}"
    if len(out.strip()) == 0:
        out = "No output found for the given command."
    return out


__all__ = ["generate_summary"]