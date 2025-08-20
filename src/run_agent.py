import asyncio
import re
import uuid
import json
import os
import numpy as np

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

EXECUTION = os.getenv("EXECUTION_MODE", "API")


def get_dataset() -> str:
    dataset_map = {
        "CFA": "CFA-benchmark",
        "test": "TestSet_benchmark",
    }
    dataset = os.getenv("DATASET", "CFA")
    try:
        return dataset_map[dataset]
    except KeyError:
        raise ValueError(f"Unknown dataset '{dataset}'. Allowed values: {list(dataset_map)}")

GROUNDTRUTH_DIR = os.path.join("..", "data", get_dataset(), "tasks","data.json")
DATA_DIR = os.path.join("..", "data", get_dataset(), "raw")

def get_number_of_executions(default: int = 3) -> int:
    raw = os.getenv("NUMBER_OF_EXECUTIONS", str(default))
    try:
        value = int(raw)
        if value < 1:
            raise ValueError("NUMBER_OF_EXECUTIONS must be >= 1")
        return value
    except ValueError:
        print(f"[WARN] Invalid NUMBER_OF_EXECUTIONS='{raw}', falling back to {default}")
        return default

NUMBER_OF_EXECUTIONS = get_number_of_executions()


def calculate_f1_mcc(conf_matrix):
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

    f1_macro = np.mean(f1_scores)

    t_sum = conf_matrix.sum(axis=1)
    p_sum = conf_matrix.sum(axis=0)
    n = conf_matrix.sum()

    c = np.trace(conf_matrix)
    s = sum(t_sum[i] * p_sum[i] for i in range(num_classes))

    mcc_numerator = c * n - s
    mcc_denominator = np.sqrt((n**2 - (p_sum**2).sum()) * (n**2 - (t_sum**2).sum()))
    mcc = mcc_numerator / mcc_denominator if mcc_denominator != 0 else 0

    return f1_macro, mcc


def check_correctness(answers: list[str], expected_answer: list[str]) -> list[bool]:
    return [
        str(expected_answer[i]).lower() in str(answers[i]).lower() or str(answers[i]).lower() in str(expected_answer[i]).lower()
        for i in range(len(expected_answer))
    ]


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


def load_data():
    with open(GROUNDTRUTH_DIR, 'r') as file: 
        games = json.loads(file.read())
    return games['tasks']


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


def get_artifact_paths(entry: dict) -> dict:
    event_id = entry["event"]
    event_pcap_files = [f for f in os.listdir(f'{DATA_DIR}/eventID_{event_id}') if f.endswith('.pcap')]
    base_dir = f'{DATA_DIR}/eventID_{event_id}'
    return {
        "log_dir": base_dir + "/",
        "pcap_path": base_dir + "/" + event_pcap_files[0],
    }


async def run_forensic_example(
    graph,
    execution_number: int,
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

    # --- write per-step log into results/run{n}/log_steps/ ---
    steps_dir = os.path.join("results", f"run{execution_number}", "log_steps")
    os.makedirs(steps_dir, exist_ok=True)
    steps_path = os.path.join(steps_dir, f"steps_event{event_id}.txt")
    with open(steps_path, "w", encoding="utf-8") as f:
        f.write(f"[Task {event_id}]\n")
        for i, message in enumerate(state["messages"]):
            f.write(f"Step {i+1}: {message.content}\n")

    return (done, answer.content, state["steps"], state["inputTokens"], state["outputTokens"])


async def main():
    pcaps = load_data()

    for execution_number in range(NUMBER_OF_EXECUTIONS):
        # --- create results/run{n}/ and result.txt there ---
        run_idx = execution_number + 1
        run_dir = os.path.join("results", f"run{run_idx}")
        os.makedirs(run_dir, exist_ok=True)
        result_file = os.path.join(run_dir, "result.txt")

        counters = [0] * 4
        confusion_matrix_vulnerable = np.zeros((2, 2), dtype=int)
        confusion_matrix_success = np.zeros((2, 2), dtype=int)

        with open(result_file, "w", encoding="utf-8") as f:
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
                    execution_number=run_idx,
                    event_id=i,
                    graph=graph,
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

            f.write("\n\n\n")
            f.write("Statistics:\n")
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
