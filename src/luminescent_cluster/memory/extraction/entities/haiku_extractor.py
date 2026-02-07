# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Claude Haiku-based entity extractor.

Uses Claude Haiku for entity extraction with temperature=0 for determinism.

Related GitHub Issues:
- #120: Implement HaikuEntityExtractor for LLM extraction

ADR Reference: ADR-003 Memory Architecture, Phase 3 (Entity Extraction)
"""

import json
import re
from typing import Any, List, Optional

from luminescent_cluster.memory.extraction.entities.prompts import (
    ENTITY_EXTRACTION_SYSTEM_PROMPT,
    ENTITY_EXTRACTION_USER_TEMPLATE,
)
from luminescent_cluster.memory.extraction.entities.types import Entity, EntityType


class HaikuEntityExtractor:
    """Claude Haiku-based entity extractor.

    Uses Claude Haiku model with temperature=0 for deterministic
    entity extraction from text content.

    Attributes:
        model: Model identifier.
        temperature: Model temperature (0.0 for determinism).
        max_tokens: Maximum tokens for response.

    Example:
        >>> extractor = HaikuEntityExtractor()
        >>> entities = await extractor.extract("The auth-service uses PostgreSQL")
        >>> print([e.name for e in entities])
        ['auth-service', 'PostgreSQL']
    """

    def __init__(
        self,
        model: str = "claude-3-haiku-20240307",
        temperature: float = 0.0,
        max_tokens: int = 1024,
        api_key: Optional[str] = None,
    ):
        """Initialize the Haiku entity extractor.

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

    async def extract(self, content: str, memory_id: Optional[str] = None) -> List[Entity]:
        """Extract entities from text using Claude Haiku.

        Args:
            content: The text content to extract entities from.
            memory_id: Optional ID of the source memory for tracking.

        Returns:
            List of extracted Entity objects.
        """
        try:
            response = await self._call_api(content)
            return self._parse_response(response, memory_id)
        except Exception as e:
            # Log error and return empty
            print(f"Entity extraction error: {e}")
            return []

    async def _call_api(self, content: str) -> List[dict[str, Any]]:
        """Call the Claude API for entity extraction.

        Args:
            content: Text to analyze.

        Returns:
            Parsed JSON response as list of dicts.
        """
        try:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=self._api_key)

            user_prompt = ENTITY_EXTRACTION_USER_TEMPLATE.format(content=content)

            message = await client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=ENTITY_EXTRACTION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )

            # Parse JSON from response
            response_text = message.content[0].text
            return self._extract_json(response_text)

        except ImportError:
            # Anthropic not installed - return empty
            return []
        except Exception as e:
            # Log error and re-raise
            print(f"Entity extraction API error: {e}")
            raise

    def _extract_json(self, text: str) -> List[dict[str, Any]]:
        """Extract JSON array from response text.

        Args:
            text: Response text potentially containing JSON.

        Returns:
            Parsed JSON as list of dicts.
        """
        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to find JSON array in text
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        return []

    def _parse_response(
        self, response: List[dict[str, Any]], memory_id: Optional[str]
    ) -> List[Entity]:
        """Parse API response into Entity objects.

        Args:
            response: Parsed JSON response.
            memory_id: Optional memory ID for tracking.

        Returns:
            List of Entity objects.
        """
        entities = []

        for item in response:
            try:
                # Validate required fields
                name = item.get("name")
                entity_type_str = item.get("entity_type")
                confidence = item.get("confidence", 0.7)

                if not name or not entity_type_str:
                    continue

                # Map string to EntityType
                entity_type = self._map_entity_type(entity_type_str)
                if entity_type is None:
                    continue

                entity = Entity(
                    name=name,
                    entity_type=entity_type,
                    confidence=float(confidence),
                    source_memory_id=memory_id,
                    mentions=[name],
                )
                entities.append(entity)

            except (KeyError, ValueError) as e:
                # Skip malformed items
                print(f"Skipping malformed entity: {e}")
                continue

        return entities

    def _map_entity_type(self, type_str: str) -> Optional[EntityType]:
        """Map string to EntityType enum.

        Args:
            type_str: String representation of entity type.

        Returns:
            EntityType enum value or None if invalid.
        """
        type_map = {
            "service": EntityType.SERVICE,
            "dependency": EntityType.DEPENDENCY,
            "api": EntityType.API,
            "pattern": EntityType.PATTERN,
            "framework": EntityType.FRAMEWORK,
            "config": EntityType.CONFIG,
        }
        return type_map.get(type_str.lower())
