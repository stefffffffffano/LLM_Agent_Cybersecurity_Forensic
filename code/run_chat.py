
from src.memory_agent import graph
print(graph)



"""
import asyncio
import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.store.memory import InMemoryStore
from langchain_core.runnables import RunnableConfig
#from haystack.document_stores.in_memory import InMemoryDocumentStore



from memory_agent.graph import create_graph
from memory_agent.state import State
from memory_agent.configuration import Configuration

# Carica variabili d'ambiente da .env
load_dotenv()

# Setup del memory store e graph
store = InMemoryStore()
graph = create_graph(store)
print(f"Graph: {graph}")


# Configurazione da .env tramite runnable_config
config = RunnableConfig(configurable={
    "model": os.getenv("MODEL", "openai/gpt-4o"),
    "max_fifo_tokens": os.getenv("MAX_FIFO_TOKENS", 6000),
    "max_working_context_tokens": os.getenv("MAX_WORKING_CONTEXT_TOKENS", 1500)
})

# Stato iniziale con lista vuota di messaggi
state = State(messages=[])

# Loop asincrono per la chat
async def chat():
    global state
    print("💬 MemoryAgent attivo. Scrivi 'exit' per uscire.")
    while True:
        user_input = input("\n👤 Tu: ")
        if user_input.strip().lower() in {"exit", "quit"}:
            print("👋 Fine della sessione.")
            break

        # Aggiunge messaggio utente allo stato
        state = State(messages=state.messages + [HumanMessage(content=user_input)])

        # Esegue il grafo
        state = await graph.ainvoke(state, config)

        # Prende il messaggio AI più recente e lo stampa
        last = state.messages[-1]
        if isinstance(last, AIMessage):
            print(f"\n🤖 AI: {last.content}")
        else:
            print(f"\n⚠️ Output non previsto: {last}")

if __name__ == "__main__":
    asyncio.run(chat())
"""