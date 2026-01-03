# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Haiku-based memory extractor.

Uses Claude Haiku for memory extraction with temperature=0 for determinism.

Related GitHub Issues:
- #92: extract_memory_facts() UDF

ADR Reference: ADR-003 Memory Architecture, Phase 1b (Async Extraction)
"""

import json
from typing import Any, List, Optional

from src.memory.extraction.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    EXTRACTION_USER_PROMPT_TEMPLATE,
)
from src.memory.extraction.types import ExtractionResult


class HaikuExtractor:
    """Claude Haiku-based memory extractor.

    Uses Claude Haiku model with temperature=0 for deterministic
    memory extraction from conversations.

    Attributes:
        temperature: Model temperature (0.0 for determinism).
        model: Model identifier.
        max_tokens: Maximum tokens for response.

    Example:
        >>> extractor = HaikuExtractor()
        >>> results = await extractor.extract("I prefer tabs over spaces")
    """

    def __init__(
        self,
        model: str = "claude-3-haiku-20240307",
        temperature: float = 0.0,
        max_tokens: int = 1024,
        api_key: Optional[str] = None,
    ):
        """Initialize the Haiku extractor.

        Args:
            model: Claude model to use.
            temperature: Temperature for generation (0.0 for determinism).
            max_tokens: Maximum tokens in response.
            api_key: Anthropic API key (optional, uses env var if not provided).
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._api_key = api_key

    async def extract(self, text: str) -> List[ExtractionResult]:
        """Extract memories from text using Claude Haiku.

        Args:
            text: Conversation text to analyze.

        Returns:
            List of ExtractionResult objects.
        """
        response = await self._call_api(text)
        return self._parse_response(response, text)

    async def _call_api(self, text: str) -> List[dict[str, Any]]:
        """Call the Claude API for extraction.

        Args:
            text: Text to analyze.

        Returns:
            Parsed JSON response as list of dicts.
        """
        try:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=self._api_key)

            user_prompt = EXTRACTION_USER_PROMPT_TEMPLATE.format(conversation=text)

            message = await client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=EXTRACTION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )

            # Parse JSON from response
            content = message.content[0].text
            return self._extract_json(content)

        except ImportError:
            # Anthropic not installed - return empty
            return []
        except Exception as e:
            # Log error and return empty
            print(f"Extraction API error: {e}")
            return []

    def _extract_json(self, text: str) -> List[dict[str, Any]]:
        """Extract JSON array from response text.

        Args:
            text: Response text potentially containing JSON.

        Returns:
            Parsed JSON as list of dicts.
        """
        # Try to find JSON array in response
        try:
            # First, try direct parse
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to find JSON array in text
        import re

        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        return []

    def _parse_response(
        self, response: List[dict[str, Any]], source_text: str
    ) -> List[ExtractionResult]:
        """Parse API response into ExtractionResult objects.

        Args:
            response: Parsed JSON response.
            source_text: Original source text.

        Returns:
            List of ExtractionResult objects.
        """
        results = []

        for item in response:
            try:
                result = ExtractionResult(
                    content=item.get("content", ""),
                    memory_type=item.get("memory_type", "fact"),
                    confidence=float(item.get("confidence", 0.7)),
                    raw_source=item.get("raw_source", source_text),
                )
                results.append(result)
            except (KeyError, ValueError) as e:
                # Skip malformed items
                print(f"Skipping malformed extraction: {e}")
                continue

        return results
