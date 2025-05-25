from pydantic import BaseModel

from langchain_core.tools import Tool

class Log_analyzer(BaseModel):
    task: str


log_analyzer = Tool(
    name="log_analyzer",
    description="""When you want to search for evidences of command execution whose injection has been noticed from 
    the pcap file, you can ask for evidences of such commands through this tool.
    Formalize what you want to know through a task to be executed by a subagent called log_analyzer.
    The log_analyzer can only be called once per step.
    Args:
        task: The task to be executed by the log analyzer.
    Returns:
        The report for the task required based on log contents.
    """,
    args_schema=Log_analyzer,
)

__all__ = ["log_analyzer"]