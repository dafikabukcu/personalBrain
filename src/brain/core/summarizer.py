"""Note summarization utilities."""

from brain.intelligence.claude_client import ClaudeClient


class NoteSummarizer:
    """Summarize notes for compression and retrieval."""

    def __init__(self, claude_client: ClaudeClient):
        self.claude_client = claude_client

    def summarize(
        self,
        content: str,
        max_length: int = 200,
        focus: str | None = None,
    ) -> str:
        """Summarize note content."""
        return self.claude_client.summarize(
            text=content,
            max_length=max_length,
            focus=focus,
        )

    def summarize_for_retrieval(self, content: str, title: str = "") -> str:
        """Generate a retrieval-optimized summary."""
        prompt = f"""Create a brief summary optimized for search retrieval.
Include:
- Key topics and concepts
- Any people, places, or things mentioned
- Main actions or decisions
- Important dates or deadlines

Keep it under 100 words and focus on searchable keywords.

Title: {title}
Content:
{content}"""

        return self.claude_client.complete(
            prompt=prompt,
            temperature=0.3,
            max_tokens=150,
        )

    def generate_title(self, content: str) -> str:
        """Generate a title for untitled content."""
        prompt = f"""Generate a concise, descriptive title (5-10 words) for this note:

{content[:500]}

Return only the title, no quotes or punctuation."""

        return self.claude_client.complete(
            prompt=prompt,
            temperature=0.5,
            max_tokens=20,
        ).strip()

    def extract_key_points(self, content: str, max_points: int = 5) -> list[str]:
        """Extract key points from content."""
        prompt = f"""Extract the {max_points} most important points from this text.
Return as a simple list, one point per line, no bullets or numbers.

{content}"""

        response = self.claude_client.complete(
            prompt=prompt,
            temperature=0.3,
        )

        points = [p.strip() for p in response.strip().split("\n") if p.strip()]
        return points[:max_points]
