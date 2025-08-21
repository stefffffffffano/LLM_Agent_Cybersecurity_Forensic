import numpy as np
from typing import List
from openai import OpenAI


class ChunkingHandler:
    def __init__(self, embedder="openai", batch_size=100, verbose=False):
        self.verbose = verbose
        self.embedder = embedder
        self.batch_size = batch_size
        self.embedding_model = None

        if embedder != "openai":
            raise RuntimeError("Sentence Transformer not supported")

    def chunk_text(self, text: str, window_size=512, step_size=256) -> List[str]:
        return [
            text[i:i + window_size]
            for i in range(0, len(text), step_size)
            if text[i:i + window_size].strip()
        ]

    def get_openai_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        client = OpenAI()
        all_embeddings = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            try:
                response = client.embeddings.create(
                    input=batch,
                    model="text-embedding-3-small"
                )
                sorted_data = sorted(response.data, key=lambda x: x.index)
                batch_embeddings = [np.array(r.embedding) for r in sorted_data]
                all_embeddings.extend(batch_embeddings)
            except Exception as e:
                if self.verbose:
                    print(f"[EMBED ERROR] Batch {i}: {e}")
        return all_embeddings

    def cosine_similarity(self, a, b):
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    def embedd_and_rank_text(self, query: str, chunks: List[str], context_length: int) -> List[str]:
        if self.embedder == "openai":
            embeddings = self.get_openai_embeddings([query] + chunks)
            query_embedding = embeddings[0]
            chunk_embeddings = embeddings[1:]
        else:
            query_embedding = self.embedding_model.encode(query)
            chunk_embeddings = self.embedding_model.encode(chunks)

        similarities = [
            self.cosine_similarity(query_embedding, emb) for emb in chunk_embeddings
        ]
        ranked_chunks = [
            chunk for _, chunk in sorted(zip(similarities, chunks), key=lambda x: x[0], reverse=True)
        ]
        return ranked_chunks[:context_length]