import subprocess
from typing import List
from multi_agent.common.utils import count_tokens
import tiktoken

def get_flow(pcap_file: str, stream: int,context_window_size) -> List[str]:
    """
    Executes the tshark command required to extract the flow from a pcap file.
    The flow is extracted using the follow TCP command and is returned as a list of strings.
    Each string in the list represents a block of text that is less than 50,000 tokens.
    """
    cmd = ["tshark", "-r", pcap_file, "-q", "-z", f"follow,tcp,ascii,{stream}"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    raw_text = result.stdout
    total_tokens = count_tokens(raw_text)
    #The number of tokens in which the text is split is computed as a proportion of the context window size
    #The maximum has to be 75% of the context window size, while the overlap is 10% of the max size
    max_tokens = int(context_window_size * 0.75)
    overlap = int(max_tokens * 0.1)
    if total_tokens > 50000:
        return split_text_by_tokens(raw_text, max_tokens=max_tokens,overlap=overlap)
    else:
        return [raw_text]

def split_text_by_tokens(text: str, max_tokens: int, overlap: int) -> List[str]:
    """
    Divides a text into chunks based on a maximum number of tokens with overlapping context.
    """
    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)
    chunks = []

    start = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text = encoding.decode(chunk_tokens)
        chunks.append(chunk_text)

        # Advance with overlap
        start += max_tokens - overlap

    return chunks
