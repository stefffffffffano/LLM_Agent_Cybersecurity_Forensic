import asyncio
import re
import uuid
import json
import os
import numpy as np
from pathlib import Path
import shutil

from langgraph.store.memory import InMemoryStore
from langchain.embeddings import init_embeddings

from dotenv import load_dotenv

from multi_agent.main_agent.graph import build_graph
from multi_agent.common.main_agent_state import State


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
RESULTS_BASE_DIR = BASE_DIR.parent / "results"
RESULTS_BASE_DIR.mkdir(parents=True, exist_ok=True)


DATASET_DIR = BASE_DIR.parent / "data" 
GROUNDTRUTH_FILE = DATASET_DIR / "tasks" / "data.json"
RAW_DIR = DATASET_DIR / "raw"


def get_number_of_executions(default: int = 3) -> int:
    raw = os.getenv("NUMBER_OF_EXECUTIONS", str(default))
    try:
        value = int(raw)
        if value < 1:
            raise ValueError
        return value
    except Exception:
        print(f"[WARN] Invalid NUMBER_OF_EXECUTIONS='{raw}', falling back to {default}")
        return default


NUMBER_OF_EXECUTIONS = get_number_of_executions()

NOT_GIVEN_ANSWER = (
    "\nFINAL REPORT:\n"
    "No answer given by the agent.\n"
    "REPORT SUMMARY:\n"
    "Identified CVE: -\n"
    "Affected Service: -\n"
    "Is Service Vulnerable: -\n"
    "Attack succeeded: -\n"
)




def calculate_f1_mcc(conf_matrix: np.ndarray):
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
    mcc = mcc_numerator / mcc_denominator if mcc_denominator != 0 else 0

    return f1_macro, float(mcc)


def check_correctness(answers: list[str], expected_answer: list[str]) -> list[bool]:
    return [
        str(expected_answer[i]).lower() in str(answers[i]).lower() or str(answers[i]).lower() in str(expected_answer[i]).lower()
        for i in range(len(expected_answer))
    ]


def get_occurrences(input_string: str, start_substring: str = '', end_substring: str = '\n') -> str:
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


def load_data():
    with open(GROUNDTRUTH_FILE, 'r', encoding='utf-8') as file:
        games = json.load(file)
    return games['tasks']


def init_store() -> InMemoryStore:
    return InMemoryStore(
        index={
            "embed": init_embeddings("openai:text-embedding-3-small"),
            "dims": 1536,
        }
    )


def get_artifact_paths(entry: dict) -> dict:
    event_id = entry["event"]
    event_dir = RAW_DIR / f"eventID_{event_id}"
    pcap_files = list(event_dir.glob("*.pcap"))
    if not pcap_files:
        raise FileNotFoundError(f"No .pcap found in {event_dir}")
    return {
        "log_dir": str(event_dir),
        "pcap_path": str(pcap_files[0]),
    }



async def run_forensic_example(
    graph,
    execution_number: int,
    event_id: int,
    run_number: int,
    pcap_path: str,
    log_dir: str,
    max_steps: int = 25,
):
    state = State(
        pcap_path=pcap_path,
        log_path=log_dir,
        messages=[],
        steps=max_steps,
        event_id=event_id,
    #   strategy=strategy,
        run_number = run_number,
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

    # Persist steps under the proper run directory
    steps_dir = RESULTS_BASE_DIR / f"run{execution_number}" / "log_steps"
    steps_dir.mkdir(parents=True, exist_ok=True)
    steps_path = steps_dir / f"steps_event{event_id}.txt"
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
    if RESULTS_BASE_DIR.exists() and RESULTS_BASE_DIR.is_dir():
        shutil.rmtree(RESULTS_BASE_DIR)
    RESULTS_BASE_DIR.mkdir(parents=True, exist_ok=True)

    pcaps = load_data()

    for execution_number in range(1, NUMBER_OF_EXECUTIONS + 1):
        run_dir = RESULTS_BASE_DIR / f"run{execution_number}"
        run_dir.mkdir(parents=True, exist_ok=True)
        result_file = run_dir / "result.txt"

        counters = [0] * 4  # CVE, service name, vulnerable, attack success
        confusion_matrix_vulnerable = np.zeros((2, 2), dtype=int)
        confusion_matrix_success = np.zeros((2, 2), dtype=int)

        with result_file.open("w", encoding="utf-8") as f:
            for i, game in enumerate(pcaps):
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
                    graph=graph,
                    execution_number=execution_number,
                    event_id=i,
                    run_number = execution_number,
                    pcap_path=paths["pcap_path"],
                    log_dir=paths["log_dir"],
                )

                if done:
                    f.write(f"[Task {i}]\n{answer}\n\nNumber of steps: {25 - steps}\n\n")
                else:
                    f.write(f"[Task {i}]\n{NOT_GIVEN_ANSWER}\n\nNumber of steps: {25 - steps}\n\n")
                f.write(f"Input tokens written: {inTokens}, output tokens: {outTokens}\n\n\n")

                if done:
                    answers = [
                        get_occurrences(answer, "Identified CVE: "),
                        get_occurrences(answer, "Affected Service: "),
                        get_occurrences(answer, "Is Service Vulnerable: "),
                        get_occurrences(answer, "Attack succeeded: "),
                    ]

                    correct = check_correctness(answers, expected_answer)
                    for j, is_correct in enumerate(correct):
                        if is_correct:
                            counters[j] += 1

                    pred_vulnerable = answers[2].lower() == "true"
                    pred_success = answers[3].lower() == "true"

                    confusion_matrix_vulnerable[int(is_vulnerable)][int(pred_vulnerable)] += 1
                    confusion_matrix_success[int(is_success)][int(pred_success)] += 1

            f.write("\n\n\nStatistics:\n")
            f.write(f"Percentage of identified CVE: {counters[0]/len(pcaps)*100:.2f}%\n")
            f.write(f"Percentage of identified affected service: {counters[1]/len(pcaps)*100:.2f}%\n")
            f.write(f"Percentage of identified vulnerability: {counters[2]/len(pcaps)*100:.2f}%\n")
            f.write(f"Percentage of identified attack success: {counters[3]/len(pcaps)*100:.2f}%\n")

            f1_macro_vulnerable, mcc_vulnerable = calculate_f1_mcc(confusion_matrix_vulnerable)
            f1_macro_success, mcc_success = calculate_f1_mcc(confusion_matrix_success)
            f.write(f"f1_macro for vulnerability: {f1_macro_vulnerable:.2f}, MCC: {mcc_vulnerable:.2f}\n")
            f.write(f"f1_macro for attack success: {f1_macro_success:.2f}, MCC: {mcc_success:.2f}\n")
            f.write("Finished running all tasks.\n")


if __name__ == "__main__":
    asyncio.run(main())
