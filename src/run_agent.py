import asyncio
import re
import uuid
import json
import os

from langgraph.store.memory import InMemoryStore
from langchain.embeddings import init_embeddings
from dotenv import load_dotenv

from agent.graph import build_graph 
from agent.state import State

load_dotenv()


def check_correctness(answers: list[str], expected_answer: list[str]) -> list[bool]:
    """
    Given a list of answers and an expected answer, checks if the answers are correct.
    """
    correctness = [False]*len(expected_answer)
    # Check if the answers are correct
    for i in range(len(answers)):
        if str(answers[i]).lower() == str(expected_answer[i]).lower():
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
    counters = [0]*4 #counters for each of the four answers
    with open("result.txt", "w") as f:
        f.write("")

    for i in range(len(pcaps)): #len(pcaps)
        game = pcaps[i] 
        paths = get_artifact_paths(game)

        store = init_store()
        graph = build_graph(store)

        expected_answer = []
    
        expected_answer.append(game["cve"])
        expected_answer.append(game["service"])
        expected_answer.append(game["vulnerable"])
        expected_answer.append(game["success"])

        (done,answer,steps) = await run_forensic_example(
            graph=graph,
            pcap_path=paths["pcap_path"],
            log_path=paths["log_path"],
        )
        with open("result.txt", "a", encoding="utf-8") as f:
                f.write(f"[Task {i+1}]\n{answer}\n\nNumber of steps: {50-steps}\n\n")
        if(done):
            #If done, update statistics, otherwise no
            answers = []
            answers.append(get_occurrences(answer, "Identified CVE: "))
            answers.append(get_occurrences(answer, "Affected Service: "))
            answers.append(get_occurrences(answer, "Is Service Vulnerable: "))
            answers.append(get_occurrences(answer, "Attack succeeded: "))
            correct = check_correctness(answers, expected_answer)
            for j in range(len(correct)):
                if correct[j]:
                    counters[j] += 1
    #At the end, print statistics
    print("Statistics:")
    print(f"Percentage of identified CVE: {counters[0]/len(pcaps)*100:.2f}%")
    print(f"Percentage of identified affected service: {counters[1]/len(pcaps)*100:.2f}%")
    print(f"Percentage of identified vulnerability: {counters[2]/len(pcaps)*100:.2f}%")
    print(f"Percentage of identified attack success: {counters[3]/len(pcaps)*100:.2f}%")
    print("Finished running all tasks.")
    

if __name__ == "__main__":
    asyncio.run(main())
    