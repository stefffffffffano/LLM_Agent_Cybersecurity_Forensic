import asyncio
import re
import uuid
import json
import os
import shutil
from pathlib import Path
import numpy as np

from langgraph.store.memory import InMemoryStore
from langchain.embeddings import init_embeddings
from dotenv import load_dotenv

from multi_agent.main_agent.graph import build_graph
from multi_agent.common.main_agent_state import State


load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = (ROOT_DIR.parent / "data").resolve()        # ../data
TASKS_DIR = DATA_DIR / "tasks"
RAW_DIR = DATA_DIR / "raw"

RESULTS_DIR = (ROOT_DIR.parent / "results").resolve()  # ../results
LOG_STEPS_DIR = RESULTS_DIR / "log_steps"
RESULT_FILE = RESULTS_DIR / "result.txt"

# Clean results/ at every run
if RESULTS_DIR.exists():
    shutil.rmtree(RESULTS_DIR)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
LOG_STEPS_DIR.mkdir(parents=True, exist_ok=True)




def calculate_f1_mcc(conf_matrix: np.ndarray):
    """Given a multi-class confusion matrix, compute macro F1-score and MCC."""
    num_classes = conf_matrix.shape[0]
    f1_scores = []
    for i in range(num_classes):
        TP = conf_matrix[i, i]
        FP = conf_matrix[:, i].sum() - TP
        FN = conf_matrix[i, :].sum() - TP
        TN = conf_matrix.sum() - (TP + FP + FN)
        precision = TP / (TP + FP) if (TP + FP) != 0 else 0
        recall = TP / (TP + FN) if (TP + FN) != 0 else 0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) != 0 else 0
        f1_scores.append(f1)
    f1_macro = float(np.mean(f1_scores))

    t_sum = conf_matrix.sum(axis=1)
    p_sum = conf_matrix.sum(axis=0)
    n = conf_matrix.sum()
    c = np.trace(conf_matrix)
    s = sum(int(t_sum[i]) * int(p_sum[i]) for i in range(num_classes))
    mcc_numerator = c * n - s
    mcc_denominator = np.sqrt((n**2 - (p_sum**2).sum()) * (n**2 - (t_sum**2).sum()))
    mcc = (mcc_numerator / mcc_denominator) if mcc_denominator != 0 else 0
    return f1_macro, float(mcc)


def check_correctness(answers: list[str], expected_answer: list[str]) -> list[bool]:
    """Given a list of answers and an expected answer, checks if the answers are correct."""
    correctness = [False] * len(expected_answer)
    for i in range(len(answers)):
        a = str(answers[i]).lower()
        e = str(expected_answer[i]).lower()
        if e in a or a in e:
            correctness[i] = True
    return correctness


def get_occurrences(input_string: str, start_substring: str = "", end_substring: str = "\n") -> str:
    try:
        if end_substring == "":
            index = input_string.find(start_substring)
            if index == -1:
                return ""
            return input_string[index + len(start_substring) :]
        pattern = re.escape(start_substring) + r"(.*?)" + re.escape(end_substring)
        matches = re.findall(pattern, input_string)
        return matches[0].strip() if matches else "No Answer"
    except Exception:
        return "No Answer"




def load_data() -> list:
    """Load the tasks information needed by the driver."""
    tasks_path = TASKS_DIR / "data.json"
    with tasks_path.open("r", encoding="utf-8") as file:
        games = json.loads(file.read())
    return games["tasks"]


def init_store() -> InMemoryStore:
    return InMemoryStore(index={
        "embed": init_embeddings("openai:text-embedding-3-small"),
        "dims": 1536,
    })


def get_artifact_paths(entry: dict) -> dict:
    """Return paths to the associated log and pcap files for a task entry."""
    event_id = entry["event"]
    base_dir = RAW_DIR / f"eventID_{event_id}"
    if not base_dir.exists():
        raise FileNotFoundError(f"Artifacts folder not found: {base_dir}")
    pcap_files = sorted(base_dir.glob("*.pcap"))
    log_files = sorted(base_dir.glob("*.log"))
    if not pcap_files:
        raise FileNotFoundError(f"No .pcap file found in {base_dir}")
    if not log_files:
        raise FileNotFoundError(f"No .log file found in {base_dir}")
    return {
        "log_path": str(log_files[0]),
        "pcap_path": str(pcap_files[0]),
    }


def get_num_executions(total_tasks: int) -> int:
    """Read number of executions from ENV (NUM_EXECUTIONS or NUMBER_OF_EXECUTIONS).
    Fallback to total_tasks and cap within [0, total_tasks].
    """
    raw = os.getenv("NUM_EXECUTIONS") or os.getenv("NUMBER_OF_EXECUTIONS")
    try:
        if raw is None:
            return total_tasks
        v = int(raw)
        return max(0, min(v, total_tasks))
    except ValueError:
        return total_tasks



async def run_forensic_example(
    graph,
    event_id: int,
    pcap_path: str,
    log_path: str,
    max_steps: int = 25,
):
    state = State(
        pcap_path=pcap_path,
        log_path=log_path,
        messages=[],
        steps=max_steps,
        event_id=event_id,
    )
    thread_id = str(uuid.uuid4())
    state = await graph.ainvoke(
        state,
        config={
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 100,
        },
    )
    answer = state["messages"][-1]
    done = state["done"]

    # Persist step trace
    steps_path = LOG_STEPS_DIR / f"steps_event{event_id}.txt"
    with steps_path.open("w", encoding="utf-8") as f:
        f.write(f"[Task {event_id}]\n")
        for i, message in enumerate(state["messages"]):
            f.write(f"Step {i+1}: {message.content}\n")

    return (
        done,
        answer.content,
        state.get("steps", max_steps),
        state.get("inputTokens", 0),
        state.get("outputTokens", 0),
    )


async def main():
    pcaps = load_data()
    counters = [0] * 4  # CVE, service name, vulnerable, attack success
    confusion_matrix_vulnerable = np.zeros((2, 2), dtype=int)
    confusion_matrix_success = np.zeros((2, 2), dtype=int)

    with RESULT_FILE.open("w", encoding="utf-8") as f:
        f.write("")

    num_exec = get_num_executions(len(pcaps))

    for i, game in enumerate(pcaps[:num_exec]):
        paths = get_artifact_paths(game)
        store = init_store()
        graph = build_graph(store)

        expected_answer = [
            game["cve"],
            game["service"],
            game["vulnerable"],
            game["success"],
        ]
        is_vulnerable = game["vulnerable"]
        is_success = game["success"]

        done, answer, steps, inTokens, outTokens = await run_forensic_example(
            event_id=i,
            graph=graph,
            pcap_path=paths["pcap_path"],
            log_path=paths["log_path"],
        )

        with RESULT_FILE.open("a", encoding="utf-8") as f:
            f.write(f"[Task {i}]\n{answer}\n\nNumber of steps: {25 - steps}\n\n")
            f.write(f"Input tokens written: {inTokens}, output tokens: {outTokens}\n\n\n")

        if done:
            answers = [
                get_occurrences(answer, "Identified CVE: "),
                get_occurrences(answer, "Affected Service: "),
                get_occurrences(answer, "Is Service Vulnerable: "),
                get_occurrences(answer, "Attack succeeded: "),
            ]

            correct = check_correctness(answers, expected_answer)
            for j, ok in enumerate(correct):
                if ok:
                    counters[j] += 1

            pred_vulnerable = answers[2].lower() == "true"
            pred_success = answers[3].lower() == "true"

            confusion_matrix_vulnerable[int(is_vulnerable)][int(pred_vulnerable)] += 1
            confusion_matrix_success[int(is_success)][int(pred_success)] += 1

    # Stats
    print("Statistics:")
    print(f"Percentage of identified CVE: {counters[0]/len(pcaps)*100:.2f}%")
    print(f"Percentage of identified affected service: {counters[1]/len(pcaps)*100:.2f}%")
    print(f"Percentage of identified vulnerability: {counters[2]/len(pcaps)*100:.2f}%")
    print(f"Percentage of identified attack success: {counters[3]/len(pcaps)*100:.2f}%")
    f1_macro_vulnerable, mcc_vulnerable = calculate_f1_mcc(confusion_matrix_vulnerable)
    f1_macro_success, mcc_success = calculate_f1_mcc(confusion_matrix_success)
    print(f"f1_macro for vulnerability: {f1_macro_vulnerable:.2f}, MCC: {mcc_vulnerable:.2f}")
    print(f"f1_macro for attack success: {f1_macro_success:.2f}, MCC: {mcc_success:.2f}")
    print("Finished running all tasks.")


if __name__ == "__main__":
    asyncio.run(main())
