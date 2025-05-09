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
from multi_agent.common.global_state import State_global

load_dotenv()


def calculate_f1_mcc(conf_matrix):
    """
    Given a multi-class confusion matrix, compute macro F1-score and Matthews Correlation Coefficient (MCC).
    """
    num_classes = conf_matrix.shape[0]
    f1_scores = []
    
    for i in range(num_classes):
        TP = conf_matrix[i, i]
        FP = conf_matrix[:, i].sum() - TP
        FN = conf_matrix[i, :].sum() - TP
        # TN = sum of everything else
        TN = conf_matrix.sum() - (TP + FP + FN)
        
        # Precision and recall for class i
        precision = TP / (TP + FP) if (TP + FP) != 0 else 0
        recall    = TP / (TP + FN) if (TP + FN) != 0 else 0
        
        # F1-score for class i
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) != 0 else 0
        f1_scores.append(f1)
    
    # Macro F1 = mean of F1-scores
    f1_macro = np.mean(f1_scores)
    
    # Now compute MCC for multi-class
    t_sum = conf_matrix.sum(axis=1)  # row sums
    p_sum = conf_matrix.sum(axis=0)  # column sums
    n = conf_matrix.sum()
    
    c = np.trace(conf_matrix)  # sum of diagonal (correct predictions)
    s = 0
    for i in range(num_classes):
        s += t_sum[i] * p_sum[i]
    
    mcc_numerator = c * n - s
    mcc_denominator = np.sqrt((n**2 - (p_sum**2).sum()) * (n**2 - (t_sum**2).sum()))
    mcc = mcc_numerator / mcc_denominator if mcc_denominator != 0 else 0

    return f1_macro, mcc

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
    Given a task entry from data.json, returns string paths to the associated pcap file and log files directory.
    """
    event_id = entry["event"]
    event_pcap_files = [f for f in os.listdir(f'data/raw/eventID_{event_id}') if f.endswith('.pcap')]
    base_dir = f'data/raw/eventID_{event_id}'
    return {
        "log_dir": base_dir + "/", #directory of the log files
        "pcap_path": base_dir + "/" + event_pcap_files[0],
    }


async def run_forensic_example(
    graph,
    event_id: int,
    pcap_path: str,
    log_dir: str,
    max_steps: int = 25
):
    #Initial state
    state = State_global(
        pcap_path=pcap_path,
        log_dir=log_dir,
        messages=[],  
        steps=max_steps,
        event_id=event_id,
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
    done = state["done"]
    #Print on a file the sequence of messages (steps of the agent)
    with open(f"log_steps/steps_event{event_id}.txt", "w", encoding="utf-8") as f:
        f.write(f"[Task {event_id}]\n")
        for i, message in enumerate(state["messages"]):
            f.write(f"Step {i+1}: {message.content}\n")
    return (done,answer.content, state["steps"], state["inputTokens"],state["outputTokens"])


async def main():
    pcaps = load_data()
    counters = [0] * 4  # CVE, service name, vulnerable, attack success
    confusion_matrix_vulnerable = np.zeros((2, 2), dtype=int)
    confusion_matrix_success = np.zeros((2, 2), dtype=int)

    with open("result.txt", "w") as f:
        f.write("")

    os.makedirs("log_steps", exist_ok=True) #trace agent's steps

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

        done, answer, steps,inTokens,outTokens = await run_forensic_example(
            event_id=i,
            graph=graph,
            pcap_path=paths["pcap_path"],
            log_dir=paths["log_dir"],
        )

        with open("result.txt", "a", encoding="utf-8") as f:
            f.write(f"[Task {i}]\n{answer}\n\nNumber of steps: {25-steps}\n\n")
            f.write(f"Input tokens written: {inTokens}, output tokens: {outTokens}\n\n\n")

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
    f1_macro_vulnerable, mcc_vulnerable = calculate_f1_mcc(confusion_matrix_vulnerable)
    f1_macro_success, mcc_success = calculate_f1_mcc(confusion_matrix_success)
    print(f"f1_macro for vulnerability: {f1_macro_vulnerable:.2f}, MCC: {mcc_vulnerable:.2f}")
    print(f"f1_macro for attack success: {f1_macro_success:.2f}, MCC: {mcc_success:.2f}")
    print("Finished running all tasks.")
    

if __name__ == "__main__":
    asyncio.run(main())
    