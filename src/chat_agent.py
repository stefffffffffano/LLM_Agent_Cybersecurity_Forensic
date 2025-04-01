from langchain_core.messages import HumanMessage, AIMessage
import uuid
from typing import Optional

class ChatAgent:
    def __init__(self, graph, thread_id: Optional[str] = None):
        self.graph = graph
        self.thread_id = thread_id or str(uuid.uuid4())

    async def __call__(self, user_input: str) -> str:
        input_state = {"messages": [HumanMessage(content=user_input)]}

       
        state = await self.graph.ainvoke(
            input_state,
            config={"configurable": {"thread_id": self.thread_id}}
        )
        returned_answer = ""
        for msg in reversed(state["messages"]):
            if isinstance(msg, AIMessage):
                returned_answer = msg.content + "\n" + returned_answer
            else:
                break  

        return returned_answer.strip() or "[No answer]"