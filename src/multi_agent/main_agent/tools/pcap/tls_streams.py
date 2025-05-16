""""
The following function, given a pcap file (its path), executes the command:
tshark -r file.pcap -Y tls -T fields -e tcp.stream,
removes duplicates from stream numbers and returns a set of tcp flows that contain tls traffic.
"""
import subprocess
from typing import Set

def get_tls_streams(pcap_file: str) -> Set[int]:
    """
    Get the TCP streams that contain TLS traffic from a pcap file.

    Args:
        pcap_file (str): The path to the pcap file.

    Returns:
        Set[int]: A set of TCP stream numbers that contain TLS traffic.
    """
    # Execute the tshark command to get the TCP streams with TLS traffic
    command = ["tshark", "-r", pcap_file, "-Y", "tls", "-T", "fields", "-e", "tcp.stream"]
    result = subprocess.run(command, capture_output=True, text=True)

    # Split the output into lines and convert to a set of integers
    streams = set(int(line.strip()) for line in result.stdout.splitlines() if line.strip().isdigit())

    return streams