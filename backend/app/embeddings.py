
from functools import lru_cache

import os


@lru_cache(maxsize=1)
def get_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        "sentence-transformers/all-MiniLM-L6-v2"
    )


@lru_cache(maxsize=1)
def get_fastembed_model():
    from fastembed import TextEmbedding

    return TextEmbedding(
        model_name=os.getenv(
            "EMBEDDING_MODEL",
            "sentence-transformers/all-MiniLM-L6-v2",
        ),
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    provider = os.getenv("EMBEDDING_PROVIDER", "local").lower()
    if provider == "fastembed":
        vectors = get_fastembed_model().embed(
            texts,
            batch_size=min(8, len(texts)),
            parallel=1,
        )
        return [vector.tolist() for vector in vectors]

    if provider == "huggingface":
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
