"""Top-k retrieval over the deputation embeddings."""


def top_k_deputations(
    neighborhood: str,
    project_description_text: str,
    k: int = 10,
) -> list[dict]:
    """Retrieve the k most similar past deputations.

    TODO:
    1. Embed the project_description_text with the same sentence-transformers model
       used in embed.py.
    2. SELECT FROM deputation_embeddings WHERE neighborhood = $1
         ORDER BY embedding <=> $2 LIMIT $3
       (or rerank with a broader retrieval if neighborhood is too restrictive).
    3. Join with deputations table to return text + concerns + group metadata.
    """
    raise NotImplementedError("Wire up pgvector query.")
