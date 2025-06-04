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
Identified CVE: unknown
Affected Service: unknown
Is Service Vulnerable: unknwon
Attack succeeded: unknwon
"""
EXECUTION = os.getenv("EXECUTION_MODE", "API")

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
    with open('data/tasks/data.json', 'r') as file: 
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
    event_pcap_files = [f for f in os.listdir(f'data/raw/eventID_{event_id}') if f.endswith('.pcap')]
    base_dir = f'data/raw/eventID_{event_id}'
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

    with open(f"log_steps/steps_event{event_id}.txt", "w", encoding="utf-8") as f:
        f.write(f"[Task {event_id}]\n")
        for i, message in enumerate(state["messages"]):
            f.write(f"Step {i+1}: {message.content}\n")

    return (done, answer.content, state["steps"], state["inputTokens"], state["outputTokens"])

async def main():
    pcaps = load_data()
    counters = [0] * 4  # CVE, service name, vulnerable, attack success
    unknown_counts = [0] * 4
    confusion_matrix_vulnerable = np.zeros((2, 2), dtype=int)
    confusion_matrix_success = np.zeros((2, 2), dtype=int)

    with open("result.txt", "w") as f:
        f.write("")

    os.makedirs("log_steps", exist_ok=True)
    total_tested = 18

    for i in range(total_tested):
        game = pcaps[i] 
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
            log_dir=paths["log_dir"],
        )

        with open("result.txt", "a", encoding="utf-8") as f:
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

            for j, a in enumerate(answers):
                if a.lower().strip() == "unknown":
                    unknown_counts[j] += 1
                elif j in (2, 3) and a.lower().strip() in ("true", "false"):
                    pred = a.lower().strip() == "true"
                    expected = expected_answer[j] == True
                    if pred == expected:
                        counters[j] += 1
                elif correct[j]:
                    counters[j] += 1

            if answers[2].lower().strip() in ("true", "false"):
                pred_vuln = answers[2].lower().strip() == "true"
                confusion_matrix_vulnerable[int(is_vulnerable)][int(pred_vuln)] += 1
            if answers[3].lower().strip() in ("true", "false"):
                pred_succ = answers[3].lower().strip() == "true"
                confusion_matrix_success[int(is_success)][int(pred_succ)] += 1

    total = total_tested
    print("Accuracy (over provided answers only):")
    labels = ["CVE", "Service", "Vulnerable", "Success"]
    for i, label in enumerate(labels):
        known = total - unknown_counts[i]
        correct = counters[i]
        if known == 0:
            print(f"{label}: No answers provided.")
        else:
            print(f"{label}: {correct}/{known} ({correct/known*100:.2f}%)")

    print("\nCoverage (provided answers, excluding 'unknown'):")
    labels = ["CVE", "Service", "Vulnerable", "Success"]
    for i, label in enumerate(labels):
        known = total - unknown_counts[i]
        print(f"{label}: {known}/{total} ({known/total*100:.2f}%)")

    f1_macro_vuln, mcc_vuln = calculate_f1_mcc(confusion_matrix_vulnerable)
    f1_macro_succ, mcc_succ = calculate_f1_mcc(confusion_matrix_success)
    print(f"\nF1_macro Vulnerable: {f1_macro_vuln:.2f}, MCC: {mcc_vuln:.2f}")
    print(f"F1_macro Attack Success: {f1_macro_succ:.2f}, MCC: {mcc_succ:.2f}")
    print("Finished running all tasks.")

if __name__ == "__main__":
    asyncio.run(main())
