import asyncio
import re
import uuid
import json
import os

from langgraph.store.memory import InMemoryStore
from langchain.embeddings import init_embeddings
from dotenv import load_dotenv

from llm_as_a_judge import build_graph 
from llm_as_a_judge.state import State

load_dotenv()
    
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


async def run_judge(
    graph,
    event_id: int,
    max_steps: int = 15,
    ground_truth: str = "",
    report: str = "",
):
    #Initial state
    state = State(
        messages=[],  
        steps=max_steps,
        event_id=event_id,
        ground_truth=ground_truth,
        report=report,
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
    with open(f"log_judge/steps_event{event_id}.txt", "w", encoding="utf-8") as f:
        f.write(f"[Task {event_id}]\n")
        for i, message in enumerate(state["messages"]):
            f.write(f"Step {i+1}: {message.content}\n")
    return (done,answer.content, state["steps"], state["inputTokens"],state["outputTokens"])


async def main():
    pcaps = load_data()
    
    os.makedirs("log_judge", exist_ok=True) #trace judge's steps

    for i, game in enumerate(pcaps):
        graph = build_graph()
        
        ground_truth = (
        f"Report: {game['report']}\n"
        f"CVE: {game['cve']}\n"
        f"Affected service: {game['service']}\n"
        f"Vulnerable: {game['vulnerable']}\n"
        f"Attack successful: {game['success']}\n"
        )

        with open("result.txt", "r", encoding="utf-8") as f:
            content = f.read()
            match = re.search(
            rf"\[Task {i}]\s*FINAL REPORT:\s*(.*?)(?:\n)?REPORT SUMMARY:\s*Identified CVE: (.*?)\s*"
            r"Affected Service: (.*?)\s*Is Service Vulnerable: (.*?)\s*Attack succeeded: (True|False)",
            content, re.DOTALL
            )

            if match:
                report_text = match.group(1).strip()
                cve = match.group(2).strip()
                service = match.group(3).strip()
                vulnerable = match.group(4).strip()
                success = match.group(5).strip()
                agent_report = (
                    f"Report: {report_text}\n"
                    f"CVE: {cve}\n"
                    f"Affected service: {service}\n"
                    f"Vulnerable: {vulnerable}\n"
                    f"Attack successful: {success}"
                )
            else:
                agent_report = "Report: NOT FOUND"

            print(f"{ground_truth}\n\n {agent_report}\n\n")
        """
        done, answer, steps,inTokens,outTokens = await run_judge(
            event_id=i,
            graph=graph,
            ground_truth=ground_truth,
            report=agent_report,
        )

        with open("result_judge.txt", "a", encoding="utf-8") as f:
            if done:
                f.write(f"[Task {i}]\n{answer}\n\nNumber of steps: {15-steps}\n\n")
                f.write(f"Input tokens written: {inTokens}, output tokens: {outTokens}\n\n\n")
            else:
                f.write(f"[Task {i}]\n Not completed\n\n")
        """

if __name__ == "__main__":
    asyncio.run(main())
    