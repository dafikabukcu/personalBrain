"""Hybrid retriever combining vector search and BM25."""

from typing import Any

import structlog
from rank_bm25 import BM25Okapi

from brain.core.models import Chunk, SearchResult
from brain.data.vector_store import VectorStore
from brain.intelligence.embeddings import EmbeddingService

logger = structlog.get_logger()


class HybridRetriever:
    """Combine vector similarity search with BM25 keyword search."""

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_service: EmbeddingService,
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3,
    ):
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight

        # BM25 index (rebuilt on demand)
        self._bm25: BM25Okapi | None = None
        self._bm25_chunks: list[Chunk] = []
        self._bm25_dirty = True

    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenization for BM25."""
        # Lowercase and split on non-alphanumeric
        import re

        return re.findall(r"\w+", text.lower())

    def _build_bm25_index(self, chunks: list[Chunk]) -> None:
        """Build BM25 index from chunks."""
        if not chunks:
            self._bm25 = None
            self._bm25_chunks = []
            return

        tokenized = [self._tokenize(c.content) for c in chunks]
        self._bm25 = BM25Okapi(tokenized)
        self._bm25_chunks = chunks
        self._bm25_dirty = False
        logger.debug("bm25_index_built", count=len(chunks))

    def mark_dirty(self) -> None:
        """Mark BM25 index as needing rebuild."""
        self._bm25_dirty = True

    def retrieve(
        self,
        query: str,
        k: int = 20,
        where: dict[str, Any] | None = None,
        chunks_for_bm25: list[Chunk] | None = None,
    ) -> list[SearchResult]:
        """Retrieve relevant chunks using hybrid search."""
        # Vector search
        query_embedding = self.embedding_service.embed_single(query)
        vector_results = self.vector_store.search(query_embedding, k=k * 2, where=where)

        # BM25 search
        bm25_results: list[SearchResult] = []
        if chunks_for_bm25 or self._bm25_chunks:
            if chunks_for_bm25 and (self._bm25_dirty or chunks_for_bm25 != self._bm25_chunks):
                self._build_bm25_index(chunks_for_bm25)

            if self._bm25 and self._bm25_chunks:
                query_tokens = self._tokenize(query)
                scores = self._bm25.get_scores(query_tokens)

                # Get top results
                scored_chunks = list(zip(self._bm25_chunks, scores))
                scored_chunks.sort(key=lambda x: x[1], reverse=True)

                for chunk, score in scored_chunks[: k * 2]:
                    if score > 0:
                        # Normalize BM25 score to 0-1 range
                        max_score = max(scores) if max(scores) > 0 else 1
                        normalized_score = score / max_score
                        bm25_results.append(
                            SearchResult(chunk=chunk, score=normalized_score, source="bm25")
                        )

        # Merge results using Reciprocal Rank Fusion
        merged = self._reciprocal_rank_fusion(vector_results, bm25_results, k=k)

        logger.debug(
            "retrieval_complete",
            query_length=len(query),
            vector_count=len(vector_results),
            bm25_count=len(bm25_results),
            merged_count=len(merged),
        )

        return merged

    def _reciprocal_rank_fusion(
        self,
        vector_results: list[SearchResult],
        bm25_results: list[SearchResult],
        k: int = 20,
        rrf_k: int = 60,
    ) -> list[SearchResult]:
        """Merge results using Reciprocal Rank Fusion."""
        # Map chunk_id -> (chunk, combined_score)
        scores: dict[str, tuple[Chunk, float]] = {}

        # Add vector results
        for rank, result in enumerate(vector_results):
            chunk_id = result.chunk.id
            rrf_score = self.vector_weight / (rrf_k + rank + 1)
            if chunk_id in scores:
                scores[chunk_id] = (result.chunk, scores[chunk_id][1] + rrf_score)
            else:
                scores[chunk_id] = (result.chunk, rrf_score)

        # Add BM25 results
        for rank, result in enumerate(bm25_results):
            chunk_id = result.chunk.id
            rrf_score = self.bm25_weight / (rrf_k + rank + 1)
            if chunk_id in scores:
                scores[chunk_id] = (result.chunk, scores[chunk_id][1] + rrf_score)
            else:
                scores[chunk_id] = (result.chunk, rrf_score)

        # Sort by combined score
        sorted_results = sorted(scores.values(), key=lambda x: x[1], reverse=True)

        return [
            SearchResult(chunk=chunk, score=score, source="hybrid")
            for chunk, score in sorted_results[:k]
        ]
