"""Intelligence layer - embeddings, retrieval, and LLM integration."""

from brain.intelligence.claude_client import ClaudeClient
from brain.intelligence.context_builder import ContextBuilder
from brain.intelligence.embeddings import EmbeddingService
from brain.intelligence.retriever import HybridRetriever

__all__ = [
    "EmbeddingService",
    "HybridRetriever",
    "ClaudeClient",
    "ContextBuilder",
]
