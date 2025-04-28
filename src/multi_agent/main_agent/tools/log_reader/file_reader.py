from pydantic import BaseModel

from langchain_core.tools import Tool


def file_reader_func(path: str) -> str:
    """Reads a file and returns its content as a string.

    Args:
        path (str): The path to the file to be read.

    Returns:
        str: The content of the file.
    """
    try:
        with open(path, "r",encoding='utf-8') as file:
            content = file.read().strip()
    except FileNotFoundError:
        content = f"File not found: {path}"
    except Exception as e:
        content = f"An error occurred while reading the file: {e}"
    return content


#Tool used for binding
file_reader = Tool(
    name="log_reader",
    description="""Read the log file related to the attack. 
    Returns:
        The content of the file as a string.
    """,
    func=file_reader_func,
)

__all__ = ["file_reader", "file_reader_func"]