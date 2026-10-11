
from functools import lru_cache

import os


@lru_cache(maxsize=1)
def get_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        "sentence-transformers/all-MiniLM-L6-v2"
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    if os.getenv("EMBEDDING_PROVIDER", "local").lower() == "huggingface":
        token = os.getenv("HF_TOKEN")
        if not token:
            raise RuntimeError("HF_TOKEN is required for hosted embeddings.")

        from huggingface_hub import InferenceClient

        client = InferenceClient(
            token=token,
            provider="hf-inference",
        )
        vectors = client.feature_extraction(
            texts,
            model=os.getenv(
                "EMBEDDING_MODEL",
                "sentence-transformers/all-MiniLM-L6-v2",
            ),
            normalize=True,
            truncate=True,
        )
        return vectors.tolist()

    vectors = get_model().encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )

    return vectors.tolist()
