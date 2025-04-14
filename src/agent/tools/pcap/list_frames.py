"""
This function is used at the beginning to show the LLM the content of the pcap file.
"""

from pydantic import BaseModel
from scapy.all import rdpcap


class ListFrames(BaseModel):
    """Open the PCAP file and inspect the frames."""

    def run(self, pcap_file):
        pcap = rdpcap(pcap_file)
        out = [f"Frame {i+1}: {pkt.summary()}" for i, pkt in enumerate(pcap)]
        out = '\n'.join(out)

        return out

__all__ = ["ListFrames"]