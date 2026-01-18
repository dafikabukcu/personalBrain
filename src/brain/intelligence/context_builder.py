"""Context builder for managing LLM context windows."""

import structlog

from brain.core.models import SearchResult

logger = structlog.get_logger()


class ContextBuilder:
    """Build optimized context for LLM prompts."""

    def __init__(
        self,
        max_tokens: int = 8000,
        chars_per_token: float = 4.0,
    ):
        self.max_tokens = max_tokens
        self.chars_per_token = chars_per_token
        self.max_chars = int(max_tokens * chars_per_token)

    def build(
        self,
        results: list[SearchResult],
        query: str | None = None,
        include_metadata: bool = True,
    ) -> str:
        """Build context string from search results."""
        if not results:
            return ""

        context_parts: list[str] = []
        current_chars = 0

        # Group by document for better organization
        doc_chunks: dict[str, list[SearchResult]] = {}
        for result in results:
            doc_path = result.chunk.document_path
            if doc_path not in doc_chunks:
                doc_chunks[doc_path] = []
            doc_chunks[doc_path].append(result)

        # Build context, respecting token limit
        for doc_path, chunks in doc_chunks.items():
            doc_section = f"\n--- From: {doc_path} ---\n"
            section_chars = len(doc_section)

            chunk_texts: list[str] = []
            for result in sorted(chunks, key=lambda x: x.chunk.chunk_index):
                chunk = result.chunk

                if include_metadata and chunk.header_path:
                    text = f"[{chunk.header_path}]\n{chunk.content}"
                else:
                    text = chunk.content

                # Check if we can add this chunk
                if current_chars + section_chars + len(text) + 2 > self.max_chars:
                    # Truncate or skip
                    remaining = self.max_chars - current_chars - section_chars - 10
                    if remaining > 100:
                        text = text[:remaining] + "..."
                        chunk_texts.append(text)
                    break

                chunk_texts.append(text)
                current_chars += len(text) + 2

            if chunk_texts:
                context_parts.append(doc_section + "\n\n".join(chunk_texts))
                current_chars += section_chars

            if current_chars >= self.max_chars:
                break

        context = "\n".join(context_parts)

        logger.debug(
            "context_built",
            result_count=len(results),
            doc_count=len(doc_chunks),
            char_count=len(context),
            estimated_tokens=len(context) / self.chars_per_token,
        )

        return context

    def build_with_expansion(
        self,
        results: list[SearchResult],
        link_chunks: dict[str, list[SearchResult]],
        expansion_hops: int = 1,
    ) -> str:
        """Build context with linked note expansion."""
        # Get all links from result chunks
        all_links: set[str] = set()
        for result in results:
            all_links.update(result.chunk.links)

        # Add linked chunks
        expanded_results = list(results)
        for link in all_links:
            if link in link_chunks:
                # Add top chunks from linked document
                for linked_result in link_chunks[link][:2]:
                    if linked_result not in expanded_results:
                        expanded_results.append(linked_result)

        # Sort by relevance score
        expanded_results.sort(key=lambda x: x.score, reverse=True)

        return self.build(expanded_results)

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        return int(len(text) / self.chars_per_token)
