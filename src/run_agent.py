import asyncio
from langgraph.store.memory import InMemoryStore
from langchain.embeddings import init_embeddings

from agent import build_graph
from chat_agent import ChatAgent  

from dotenv import load_dotenv
load_dotenv()  

def init_store() -> InMemoryStore:
    return InMemoryStore(
        index={
            "embed": init_embeddings("openai:text-embedding-3-small"),
            "dims": 1536,
        }
    )


def init_agent():
    store = init_store()
    graph = build_graph(store)
    return ChatAgent(graph) 


async def interactive_loop(agent: ChatAgent):
    print("Chat started. Type 'exit','quit' or 'q' to stop.\n")
    while True:
        user_input = input("User: ")
        if user_input.lower() in {"exit", "quit", "q"}:
            print("Goodbye!")
            break
        try:
            response = await agent(user_input)
            print("Assistant:", response)
        except Exception as e:
            print("Error during interaction:", e)


def main():
    agent = init_agent()
    asyncio.run(interactive_loop(agent))


if __name__ == "__main__":
    main()
