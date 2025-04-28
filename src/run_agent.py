import asyncio
import re
import uuid
import json
import os
import numpy as np

from langgraph.store.memory import InMemoryStore
from langchain.embeddings import init_embeddings
from dotenv import load_dotenv

from multi_agent.main_agent.graph import build_graph 
from multi_agent.common.main_agent_state import State

load_dotenv()


def calculate_f1_mcc(conf_matrix):
    """
      TN  FP
      FN  TP
      Given confusion matrices, compute f1 score and Matthews Correlation Coefficient (MCC).
    """
    TN, FP = conf_matrix[0]
    FN, TP = conf_matrix[1]

    # Avoid division by zero
    precision = TP / (TP + FP) if (TP + FP) != 0 else 0
    recall    = TP / (TP + FN) if (TP + FN) != 0 else 0

    # F1-score
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) != 0 else 0

    # MCC
    numerator   = (TP * TN) - (FP * FN)
    denominator = np.sqrt((TP + FP)*(TP + FN)*(TN + FP)*(TN + FN))
    mcc = numerator / denominator if denominator != 0 else 0

    return f1, mcc

def check_correctness(answers: list[str], expected_answer: list[str]) -> list[bool]:
    """
    Given a list of answers and an expected answer, checks if the answers are correct.
    """
    correctness = [False]*len(expected_answer)
    # Check if the answers are correct
    for i in range(len(answers)):
        if str(expected_answer[i]).lower() in str(answers[i]).lower() or str(answers[i]).lower() in str(expected_answer[i]).lower():
            correctness[i] = True
    
    return correctness



def get_occurrences(input_string, start_substring='', end_substring='\n'):
    # Create a regular expression pattern based on the provided start and end substrings
    try:
        if end_substring=='':
            index = input_string.find(start_substring)
            if index == -1:
                return ""
            return input_string[index + len(start_substring):]
        else:
            pattern = re.escape(start_substring) + r'(.*?)' + re.escape(end_substring)
            # Find all occurrences of text between the start and end substrings
            matches = re.findall(pattern, input_string)
            return matches[0].strip()  # Return a list of all occurrences
    except Exception as e:
        return "No Answer"
    
def load_data():
    """Load the tasks information needed by the driver

    Returns:
        list: collection of tasks
    """
    with open('data/tasks/data.json', 'r') as file: 
        games = json.loads(file.read())
    return games['tasks']

def init_store() -> InMemoryStore:
    return InMemoryStore(
        index={
            "embed": init_embeddings("openai:text-embedding-3-small"),
            "dims": 1536,
        }
    )

def get_artifact_paths(entry: dict) -> dict:
    """
    Given a task entry from data.json, returns string paths to the associated log and pcap files.
    """
    event_id = entry["event"]
    event_pcap_files = [f for f in os.listdir(f'data/raw/eventID_{event_id}') if f.endswith('.pcap')]
    #Just get the first one for now
    event_log_file = [f for f in os.listdir(f'data/raw/eventID_{event_id}') if f.endswith('.log')][0]
    base_dir = f'data/raw/eventID_{event_id}'
    return {
        "log_path": base_dir + "/" + event_log_file,
        "pcap_path": base_dir + "/" + event_pcap_files[0],
    }


async def run_forensic_example(
    graph,
    pcap_path: str,
    log_path: str,
    max_steps: int = 50
):
    #Initial state
    state = State(
        pcap_path=pcap_path,
        log_path=log_path,
        messages=[],  
        steps=max_steps
    )
    thread_id = str(uuid.uuid4())
    #Call the graph
    state = await graph.ainvoke(
            state,
            config={
                "configurable": {"thread_id": thread_id},
                "recursion_limit": 100,}
    )
    
    answer = state["messages"][-1]
    print(f"\n\n\n\n\n\n\nAnswer: {answer}\n\n\n\n\n\n\n")
    done = state["done"]
    return (done,answer.content, state["steps"])


async def main():
    pcaps = load_data()
    counters = [0] * 4  # CVE, service name, vulnerable, attack success
    confusion_matrix_vulnerable = np.zeros((2, 2), dtype=int)
    confusion_matrix_success = np.zeros((2, 2), dtype=int)

    with open("result.txt", "w") as f:
        f.write("")

    for i, game in enumerate(pcaps):
        paths = get_artifact_paths(game)
        store = init_store()
        graph = build_graph(store)

        expected_answer = [
            game["cve"],       # index 0
            game["service"],   # index 1
            game["vulnerable"],# index 2
            game["success"],   # index 3
        ]

        is_vulnerable = game["vulnerable"]
        is_success = game["success"]

        done, answer, steps = await run_forensic_example(
            graph=graph,
            pcap_path=paths["pcap_path"],
            log_path=paths["log_path"],
        )

        with open("result.txt", "a", encoding="utf-8") as f:
            f.write(f"[Task {i+1}]\n{answer}\n\nNumber of steps: {50-steps}\n\n")

        if done:
            # Extract answers from the formatted response
            answers = [
                get_occurrences(answer, "Identified CVE: "),
                get_occurrences(answer, "Affected Service: "),
                get_occurrences(answer, "Is Service Vulnerable: "),   # boolean string
                get_occurrences(answer, "Attack succeeded: "),        # boolean string
            ]

            # Check correctness and update counters
            correct = check_correctness(answers, expected_answer)
            for j, is_correct in enumerate(correct):
                if is_correct:
                    counters[j] += 1

            # Update confusion matrices
            pred_vulnerable = answers[2].lower() == "true"
            pred_success = answers[3].lower() == "true"

            # Riga = atteso (0 = falso, 1 = vero), Colonna = predetto
            confusion_matrix_vulnerable[int(is_vulnerable)][int(pred_vulnerable)] += 1
            confusion_matrix_success[int(is_success)][int(pred_success)] += 1
    #At the end, print statistics
    print("Statistics:")
    print(f"Percentage of identified CVE: {counters[0]/len(pcaps)*100:.2f}%")
    print(f"Percentage of identified affected service: {counters[1]/len(pcaps)*100:.2f}%")
    print(f"Percentage of identified vulnerability: {counters[2]/len(pcaps)*100:.2f}%")
    print(f"Percentage of identified attack success: {counters[3]/len(pcaps)*100:.2f}%")
    """
    For what concerns vulnerability and attack success, since it's about a binary classification problem, 
    accuracy can be misleading (we could get 50% predicting by chance), or, since the dataset is unbalanced,
    we could get 75% by predicting always true (15/20 are successful as attacks).
    I decided to compute both F1 score anche MCC (Matthews Correlation Coefficient) for each confusion matrix.
    F1 score: The F1-score is useful when you want to find an optimal balance between false positives and false negatives.
    It ranges from 0 (worst) to 1 (perfect classification).

    MCC score: The Matthews Correlation Coefficient (MCC) is a more comprehensive metric for evaluating binary classification. It takes into account all four values of the confusion matrix: TP, TN, FP, FN.
    (+1 perfect prediction, 0 random prediction, -1 inverse prediction->total disagreement).
    """
    f1_vulnerable, mcc_vulnerable = calculate_f1_mcc(confusion_matrix_vulnerable)
    f1_success, mcc_success = calculate_f1_mcc(confusion_matrix_success)
    print(f"f1 score for vulnerability: {f1_vulnerable:.2f}, MCC: {mcc_vulnerable:.2f}")
    print(f"f1 score for attack success: {f1_success:.2f}, MCC: {mcc_success:.2f}")
    print("Finished running all tasks.")
    

if __name__ == "__main__":
    asyncio.run(main())
    