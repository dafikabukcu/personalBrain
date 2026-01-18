"""Claude API client with structured extraction support."""

from typing import Any, TypeVar

import anthropic
import structlog
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger()

T = TypeVar("T", bound=BaseModel)


class ClaudeClient:
    """Claude API client for chat completion and structured extraction."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    def complete(
        self,
        prompt: str,
        system: str | None = None,
        context: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Generate a completion for the given prompt."""
        messages = []

        if context:
            messages.append({"role": "user", "content": f"Context:\n{context}"})
            messages.append({"role": "assistant", "content": "I understand the context. What would you like to know?"})

        messages.append({"role": "user", "content": prompt})

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens or self.max_tokens,
            temperature=temperature if temperature is not None else self.temperature,
            system=system or "You are a helpful personal knowledge assistant.",
            messages=messages,
        )

        content = response.content[0]
        if content.type == "text":
            return content.text
        return ""

    def complete_stream(
        self,
        prompt: str,
        system: str | None = None,
        context: str | None = None,
    ):
        """Stream a completion for the given prompt."""
        messages = []

        if context:
            messages.append({"role": "user", "content": f"Context:\n{context}"})
            messages.append({"role": "assistant", "content": "I understand the context. What would you like to know?"})

        messages.append({"role": "user", "content": prompt})

        with self.client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system or "You are a helpful personal knowledge assistant.",
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text

    def extract(
        self,
        text: str,
        schema: type[T],
        instructions: str | None = None,
    ) -> T | None:
        """Extract structured data from text using Claude."""
        schema_json = schema.model_json_schema()

        prompt = f"""Extract information from the following text and return it as JSON matching this schema:

Schema:
```json
{schema_json}
```

{f"Instructions: {instructions}" if instructions else ""}

Text to extract from:
```
{text}
```

Return ONLY valid JSON matching the schema, no other text."""

        response = self.complete(
            prompt=prompt,
            system="You are a precise data extraction assistant. Extract information exactly as specified.",
            temperature=0.0,
        )

        # Parse response as JSON
        try:
            import json

            # Try to extract JSON from response
            json_str = response.strip()
            if json_str.startswith("```"):
                # Remove code block markers
                lines = json_str.split("\n")
                json_str = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

            data = json.loads(json_str)
            return schema.model_validate(data)
        except Exception as e:
            logger.warning(
                "extraction_failed",
                error=str(e),
                response_preview=response[:200] if response else None,
            )
            return None

    def summarize(
        self,
        text: str,
        max_length: int = 200,
        focus: str | None = None,
    ) -> str:
        """Summarize text."""
        prompt = f"""Summarize the following text in {max_length} words or less.
{f"Focus on: {focus}" if focus else ""}

Text:
{text}"""

        return self.complete(
            prompt=prompt,
            system="You are a concise summarization assistant.",
            temperature=0.3,
        )

    def answer_question(
        self,
        question: str,
        context: str,
        sources: list[dict[str, Any]] | None = None,
    ) -> str:
        """Answer a question using provided context."""
        system = """You are a personal knowledge assistant. Answer questions based on the provided context from the user's notes.
If the answer is not in the context, say so. Always cite which notes/sections the information comes from.
Be concise but comprehensive."""

        source_info = ""
        if sources:
            source_info = "\n\nSources:\n"
            for i, src in enumerate(sources, 1):
                source_info += f"{i}. {src.get('path', 'Unknown')} - {src.get('header', '')}\n"

        full_context = f"{context}{source_info}"

        return self.complete(
            prompt=question,
            system=system,
            context=full_context,
        )
