from langchain_core.tools import Tool, InjectedToolArg
from langgraph.store.base import BaseStore
from typing import Annotated, Optional
from pydantic import BaseModel
import uuid

# Pydantic schema for arguments

class UpsertMemoryArgs(BaseModel):
    content: str
    context: str
    memory_id: Optional[str] = None

# Function
async def upsert_memory_func(
    content: str,
    context: str,
    memory_id: Optional[str] = None,
    *,
    store: BaseStore, 
) -> str:
    mem_id = memory_id or str(uuid.uuid4())
    embedding_text = content

    await store.aput(
        "memories",
        key=mem_id,
        value={"text": embedding_text, "content": content, "context": context}
    )
    return f"Stored memory {mem_id}"

# Description that is later used to bind 
upsert_memory = Tool(
    name="upsert_memory",
    description="""Upsert a memory in the database.
        If you find something relevant to remember, you can store it in the memory.
        The messages are contained in a queue of limited length, thus, it is important you
        remember details (be specific) of the task you are facing and of what is returned 
        by other tools.
        
        If a memory conflicts with an existing one, then just UPDATE the
        existing one by passing in memory_id - don't create two memories
        that are the same. If the user corrects a memory, UPDATE it.

        Args:
            content: The main content of the memory. For example:
                "User expressed interest in learning about French."
            context: Additional context for the memory. For example:
                "This was mentioned while discussing career options in Europe."
            memory_id: ONLY PROVIDE IF UPDATING AN EXISTING MEMORY.
            The memory to overwrite.
        """,
    args_schema=UpsertMemoryArgs,
    func=upsert_memory_func
)


__all__ = ["upsert_memory,upsert_memory_func"]