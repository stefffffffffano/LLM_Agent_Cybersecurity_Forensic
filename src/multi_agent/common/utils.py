"""Utility functions used in our graph."""
import tiktoken
import subprocess

# This encoding is used for token counting by most of the providers
encoding = tiktoken.get_encoding("cl100k_base")

def split_model_and_provider(full_name: str) -> dict:
    
    if "/" in full_name:
        if len(full_name.split("/")) > 2:
            provider,model = full_name.split("/")[0], "/".join(full_name.split("/")[1:])  
        else: 
            provider,model = full_name.split("/", maxsplit=1)
    else:
        # Default fallback
        provider = "openai"
        model = "gpt-4o"

    return {"model": model,"model_provider":provider}


def count_tokens(message) -> int:
    """
    Count tokens in a message (BaseMessage), memory (SearchItem), or raw string.
    """
    num_tokens = 4  # overhead base

    if hasattr(message, "content"):  # BaseMessage
        text = message.content
    elif hasattr(message, "value"):  # SearchItem (memoria semantica)
        text = message.value
    elif isinstance(message, str):
        text = message
    else:
        raise TypeError(f"Unsupported type for token counting: {type(message)}")

    num_tokens += len(encoding.encode(text))
    num_tokens += 2  # priming
    return num_tokens

def truncate_flow(flow_text: str, tokens_budget: int,context_window: int=128000)-> str:
    #If the token budget overcome the context window, we set it to 90% of the context window
    if tokens_budget > context_window:
        tokens_budget = context_window*0.90
    half_budget = tokens_budget // 2
    tokens = encoding.encode(flow_text)
    
    # Safety: can't take more tokens than available
    first_half = tokens[:half_budget]
    second_half = tokens[-half_budget:]
    
    # Decode token sequences back to text
    part1 = encoding.decode(first_half)
    part2 = encoding.decode(second_half)
    
    return "Beginning of the tcp flow: \n" + part1 + "\n--- final part of the flow ---\n" + part2

def count_flows(pcap_file: str) -> int:
    """
    Executes the command:
    tshark -r .\CVE-2020-11981_fail.pcap -T fields -e tcp.stream | Sort-Object | Get-Unique | Measure-Object | Select-Object -ExpandProperty Count
    in order to get the number of distinct tcp flows in the pcap file.
    Returns the number of distinct tcp flows in the pcap file.
    """
    cmd = ["tshark", "-r", pcap_file, "-T", "fields", "-e", "tcp.stream"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Split the output into lines and filter out empty lines
    streams = [line for line in result.stdout.splitlines() if line.strip()]
    
    # Use a set to get unique streams
    unique_streams = set(streams)
    
    return len(unique_streams)


def get_flow(pcap_file: str, stream: int) -> str:
    """
    Executes the tshark command required to extract the flow from a pcap file.
    The flow is extracted using the follow TCP command and is returned as a list of strings.
    Each string in the list represents a block of text that is less than 50,000 tokens.
    """
    cmd = ["tshark", "-r", pcap_file, "-q", "-z", f"follow,tcp,ascii,{stream}"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    raw_text = result.stdout
    return raw_text 