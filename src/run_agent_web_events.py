import asyncio
import re
import uuid
import os

from langgraph.store.memory import InMemoryStore
from langchain.embeddings import init_embeddings
from langchain_community.embeddings import HuggingFaceEmbeddings
from dotenv import load_dotenv

from multi_agent.main_agent.graph import build_graph 
from multi_agent.common.global_state import State_global

load_dotenv()

NOT_GIVEN_ANSWER = """
FINAL REPORT:
No answer given by the agent.
REPORT SUMMARY:
Identified CVE: -
Affected Service: -
Is Service Vulnerable: -
Attack succeeded: -
"""

DATA_DIR = "../data/web_browsing_traffic/raw"

EXECUTION = os.getenv("EXECUTION_MODE", "API")


os.environ["DATASET"] = "web_browsing_events"


RESULTS_DIR = "../results"
LOG_STEPS_DIR = os.path.join(RESULTS_DIR, "log_steps")
RESULTS_FILE = os.path.join(RESULTS_DIR, "result.txt")


def get_occurrences(input_string, start_substring='', end_substring='\n'):
    try:
        if end_substring == '':
            index = input_string.find(start_substring)
            return "" if index == -1 else input_string[index + len(start_substring):]
        else:
            pattern = re.escape(start_substring) + r'(.*?)' + re.escape(end_substring)
            matches = re.findall(pattern, input_string)
            return matches[0].strip() if matches else "No Answer"
    except Exception:
        return "No Answer"


def init_store() -> InMemoryStore:
    if EXECUTION == "LOCAL":
        return InMemoryStore(
            index={
                "embed": HuggingFaceEmbeddings(model_name="BAAI/bge-small-en"),
                "dims": 384,
            }
        )
    else:
        return InMemoryStore(
            index={
                "embed": init_embeddings("openai:text-embedding-3-small"),
                "dims": 1536,
            }
        )


def list_event_ids():
    ids = []
    try:
        for name in os.listdir(DATA_DIR):
            full = os.path.join(DATA_DIR, name)
            if os.path.isdir(full):
                m = re.match(r"^eventID_(\d+)$", name)
                if m:
                    ids.append(int(m.group(1)))
    except FileNotFoundError:
        raise FileNotFoundError(f"DATA_DIR not found: {DATA_DIR}")
    return sorted(ids)


def get_artifact_paths(event_id: int) -> dict:
    base_dir = f'{DATA_DIR}/eventID_{event_id}'
    event_pcap_files = [f for f in os.listdir(base_dir) if f.endswith('.pcapng')]
    event_pcap_files.sort()
    if not event_pcap_files:
        raise FileNotFoundError(f"No .pcapng found in: {base_dir}")
    return {
        "log_dir": base_dir + "/",
        "pcap_path": base_dir + "/" + event_pcap_files[0],
    }


async def run_forensic_example(
    graph,
    event_id: int,
    pcap_path: str,
    log_dir: str,
    max_steps: int = 25,
    strategy: str = "LLM_summary",
):
    state = State_global(
        pcap_path=pcap_path,
        log_dir=log_dir,
        messages=[],  
        steps=max_steps,
        event_id=event_id,
        strategy=strategy,
    )
    thread_id = str(uuid.uuid4())
    state = await graph.ainvoke(
        state,
        config={
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 100,
        }
    )

    answer = state["messages"][-1]
    done = state["done"]

    with open(os.path.join(LOG_STEPS_DIR, f"steps_event{event_id}.txt"), "w", encoding="utf-8") as f:
        f.write(f"[Task {event_id}]\n")
        for i, message in enumerate(state["messages"]):
            f.write(f"Step {i+1}: {message.content}\n")

    return (done, answer.content, state["steps"], state["inputTokens"], state["outputTokens"])


async def main():
    os.makedirs(LOG_STEPS_DIR, exist_ok=True)
    with open(RESULTS_FILE, "w", encoding="utf-8") as _:
        pass

    event_ids = list_event_ids()
    for event_id in event_ids:
        paths = get_artifact_paths(event_id)
        store = init_store()
        graph = build_graph(store)

        done, answer, steps, inTokens, outTokens = await run_forensic_example(
            event_id=event_id,
            graph=graph,
            pcap_path=paths["pcap_path"],
            log_dir=paths["log_dir"],
        )

        with open(RESULTS_FILE, "a", encoding="utf-8") as f:
            if done:
                f.write(f"[Task {event_id}]\n{answer}\n\nNumber of steps: {25 - steps}\n\n")
            else:
                f.write(f"[Task {event_id}]\n{NOT_GIVEN_ANSWER}\n\nNumber of steps: {25 - steps}\n\n")
            f.write(f"Input tokens written: {inTokens}, output tokens: {outTokens}\n\n\n")


if __name__ == "__main__":
    asyncio.run(main())
