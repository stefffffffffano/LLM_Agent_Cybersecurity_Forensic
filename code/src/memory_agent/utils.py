"""Utility functions used in our graph."""
import tiktoken

def split_model_and_provider(fully_specified_name: str) -> dict:
    """Initialize the configured chat model."""
    if "/" in fully_specified_name:
        provider, model = fully_specified_name.split("/", maxsplit=1)
    else:
        provider = None
        model = fully_specified_name
    return {"model": model, "provider": provider}


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