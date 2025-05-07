from pydantic import BaseModel
from pathlib import Path

from langchain_core.tools import Tool
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings


def manualSearch_func(searchString: str, threshold: float = 0.0) -> str:
    """
    Search the vector database containing the TShark and Wireshark-filter manuals
    for relevant information about a specific command, filter, option, or error.

    Args:
        searchString (str): The search query provided by the user, typically a command name,
                            a filter expression, an option, a flag, or an error message.

    Returns:
        str: A synthesized text containing the most relevant information extracted from the manuals.
             If no relevant information is found, a default message is returned.

    Notes:
        - The function uses a FAISS index stored locally in the 'faiss_network_manuals_openai' folder.
        - Embeddings are based on OpenAI models.
        - Covers both TShark command-line options and Wireshark display filter syntax.
    """
    # Relative path to the FAISS index folder
    db_path = Path(__file__).parent / "faiss_network_manuals_openai"

    # Load vector store
    vectorstore = FAISS.load_local(str(db_path), OpenAIEmbeddings(), allow_dangerous_deserialization=True)

    # Semantic search
    results_with_score = vectorstore.similarity_search_with_score(searchString, k=3)

    # Filter by threshold
    filtered = [(doc, score) for doc, score in results_with_score if score >= threshold]

    if not filtered:
        return "No relevant information found in the manuals (similarity too low with respect to the query)."

    output = []
    for doc, score in filtered:
        output.append(f"**Similarity: {score:.2f}**\n{doc.page_content.strip()}")

    return "\n\n---\n\n".join(output)


# Pydantic schema for arguments
class ManualSearch(BaseModel):
    searchString: str


manualSearch = Tool(
    name="manual_search",
    description="""
    Search the TShark and Wireshark-filter manuals to retrieve detailed information about:
    - TShark command-line options, flags, and syntax
    - Wireshark display filter syntax and field names

    Use this tool when:
    - You need to understand a specific TShark command or option.
    - You need to fix a tshark command or understand an error.
    - You need to understand how to build a correct Wireshark display filter.
    - You want examples of usage or syntax for tshark commands or filters.

    The search is performed over a vector database built from the official manuals.
    """,
    args_schema=ManualSearch,
    func=manualSearch_func,
)

__all__ = ["manualSearch", "manualSearch_func"]
