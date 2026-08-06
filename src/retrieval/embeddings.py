from __future__ import annotations

from functools import lru_cache
from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings


@lru_cache(maxsize=4)
def _load_model(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


class ConfiguredEmbeddings(Embeddings):
    """Embedding adapter supporting OpenAI API and optional local MiniLM."""

    def __init__(self, provider: str, model_name: str, openai_api_key: str | None = None):
        self.provider = provider.strip().lower()
        if self.provider == "openai":
            if not openai_api_key:
                raise RuntimeError("OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai.")
            self.model: Any = OpenAIEmbeddings(model=model_name, api_key=openai_api_key)
        elif self.provider in {"local", "minilm", "sentence_transformers"}:
            self.model = _load_model(model_name)
        else:
            raise RuntimeError("Unsupported EMBEDDING_PROVIDER. Expected 'openai' or 'local'.")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if self.provider == "openai":
            return self.model.embed_documents(texts)
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        if self.provider == "openai":
            return self.model.embed_query(text)
        embedding = self.model.encode([text], normalize_embeddings=True)
        return embedding[0].tolist()


# Backward-compatible alias for existing imports outside this project.
MiniLMEmbeddings = ConfiguredEmbeddings
