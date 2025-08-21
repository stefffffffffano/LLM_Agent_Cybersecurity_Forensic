"""Utility functions used in our graph."""
import tiktoken

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
    encoding = tiktoken.get_encoding("cl100k_base")
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