"""Embedding service using OpenAI API."""

import hashlib
import json
from pathlib import Path

import structlog
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger()


class EmbeddingService:
    """Generate embeddings using OpenAI API."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        batch_size: int = 100,
        cache_path: Path | None = None,
    ):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.batch_size = batch_size
        self.cache_path = cache_path
        self._cache: dict[str, list[float]] = {}

        if cache_path:
            self._load_cache()

    def _load_cache(self) -> None:
        """Load embedding cache from disk."""
        if self.cache_path and self.cache_path.exists():
            try:
                with open(self.cache_path, encoding="utf-8") as f:
                    self._cache = json.load(f)
                logger.info("embedding_cache_loaded", count=len(self._cache))
            except Exception as e:
                logger.warning("embedding_cache_load_failed", error=str(e))
                self._cache = {}

    def _save_cache(self) -> None:
        """Save embedding cache to disk."""
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f)

    def _cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        return hashlib.sha256(f"{self.model}:{text}".encode()).hexdigest()[:32]

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    def _call_api(self, texts: list[str]) -> list[list[float]]:
        """Call OpenAI embedding API with retry."""
        response = self.client.embeddings.create(
            model=self.model,
            input=texts,
        )
        return [item.embedding for item in response.data]

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        if not texts:
            return []

        results: list[list[float]] = []
        uncached_texts: list[str] = []
        uncached_indices: list[int] = []

        # Check cache
        for i, text in enumerate(texts):
            key = self._cache_key(text)
            if key in self._cache:
                results.append(self._cache[key])
            else:
                results.append([])  # placeholder
                uncached_texts.append(text)
                uncached_indices.append(i)

        # Fetch uncached embeddings in batches
        if uncached_texts:
            logger.debug("fetching_embeddings", count=len(uncached_texts))
            for batch_start in range(0, len(uncached_texts), self.batch_size):
                batch = uncached_texts[batch_start : batch_start + self.batch_size]
                embeddings = self._call_api(batch)

                for j, emb in enumerate(embeddings):
                    idx = uncached_indices[batch_start + j]
                    results[idx] = emb
                    # Cache the result
                    key = self._cache_key(texts[idx])
                    self._cache[key] = emb

            # Save cache
            self._save_cache()

        return results

    def embed_single(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        return self.embed([text])[0]
