from pydantic import BaseModel
import subprocess
import os 

from langchain_core.tools import Tool

    
def frameDataExpander_func(frame_number: int, pcap_file: str) -> str:
    """
    Given the pcap file and the frame number, this function extracts the data contained in the frame.
    Args:
        frame_number: the number of the frame in the pcap file.
        pcap_file: the path to the pcap file.
    Returns:
        The data contained in the frame.
    """
    try:
        result = subprocess.run(
            ['tshark', '-r', pcap_file, '-Y', f"frame.number=={frame_number}", '-T', 'fields', '-e', 'data'],
            capture_output=True,
            text=True,
            check=True
        )
        out = result.stdout
    except subprocess.CalledProcessError as e:
        out = f"Error: {e}"
    if len(out.strip())==0:
        out = "The frame does not contain DATA."
    return out

def frameDataExtractor_func(frame_number: int, pcap_file: str) -> str:
    """
    Extract the complete verbose information of a specific frame from a .pcap file.
    Args: 
        frame_number: the number of the frame in the pcap file.
        pcap_file: the path to the pcap file.
    Returns:
        The complete verbose information of the frame.
    """
    try:
        result = subprocess.run(
            ['tshark', '-r', pcap_file, '-Y', f"frame.number=={frame_number}", '-V'],
            capture_output=True,
            text=True,
            check=True
        )
        out = result.stdout
    except subprocess.CalledProcessError as e:
        out = f"Error: {e}"
    if len(out.strip()) == 0:
        out = "No information found for the given frame number."
    return out


#Pydantic schema for arguments
class FrameData(BaseModel):
    frame_number: int

#Tool used for binding
frameDataExpander = Tool(
    name="frame_data_expander",
    description="""Show the paylod contained in a frame.
    Args:
        frame_number: the number of the frame in the pcap file. 
    """,
    args_schema=FrameData,
    func=frameDataExpander_func,
)

frameDataExtractor = Tool(
    name="frame_data_extractor",
    description="""Extract the complete verbose information of a specific frame from a .pcap file.
        This tool uses tshark to retrieve detailed, human-readable protocol-level information about a single frame, 
        including all layers (e.g., Ethernet, IP, TCP/UDP, etc.).
        Use this when you need to inspect the structure and metadata of a packet, not just the raw payload.
        Args:
            frame_number: the number of the frame in the pcap file. 
    """,
    args_schema=FrameData,
    func=frameDataExtractor_func,
)


__all__ = ["frameDataExpander", "frameDataExpander_func","frameDataExtractor", "frameDataExtractor_func"]