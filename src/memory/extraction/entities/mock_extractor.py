# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Pattern-based entity extractor for testing.

Uses regular expressions to detect entities without API calls.
Suitable for development and testing environments.

Related GitHub Issues:
- #119: Implement MockEntityExtractor for testing

ADR Reference: ADR-003 Memory Architecture, Phase 3 (Entity Extraction)
"""

import re
from typing import List, Optional

from src.memory.extraction.entities.types import Entity, EntityType


# Service patterns: matches service-name, name-service, name-api patterns
SERVICE_PATTERNS = [
    r"\b([a-z]+-service)\b",  # word-service
    r"\b([a-z]+-api)\b",  # word-api
    r"\b(service-[a-z]+)\b",  # service-word
]

# Dependency patterns: known databases, caches, message queues
KNOWN_DEPENDENCIES = [
    "PostgreSQL",
    "MySQL",
    "MongoDB",
    "Redis",
    "Memcached",
    "Elasticsearch",
    "Kafka",
    "RabbitMQ",
    "NATS",
    "Celery",
    "Docker",
    "Kubernetes",
    "AWS",
    "GCP",
    "Azure",
]

# API patterns: REST endpoints
API_PATTERNS = [
    r"((?:GET|POST|PUT|DELETE|PATCH)?\s*/[a-zA-Z0-9/_-]+)",  # /api/v1/users
    r"\b(/api/[a-zA-Z0-9/_-]+)\b",  # /api/...
]

# Pattern patterns: design patterns
PATTERN_KEYWORDS = [
    "Repository Pattern",
    "Factory Pattern",
    "Singleton Pattern",
    "Observer Pattern",
    "Strategy Pattern",
    "Decorator Pattern",
    "Adapter Pattern",
    "Facade Pattern",
    "Command Pattern",
    "MVC",
    "MVVM",
    "CQRS",
    "Event Sourcing",
]

# Framework patterns: known frameworks
KNOWN_FRAMEWORKS = [
    "FastAPI",
    "Django",
    "Flask",
    "React",
    "Vue",
    "Angular",
    "Next.js",
    "Express",
    "Spring",
    "Rails",
    "Laravel",
    "Pydantic",
    "SQLAlchemy",
    "Prisma",
]

# Config patterns: environment variables (UPPER_CASE_SNAKE)
CONFIG_PATTERNS = [
    r"\b([A-Z][A-Z0-9_]{2,})\b",  # UPPER_CASE_SNAKE_CASE
]


class MockEntityExtractor:
    """Pattern-based entity extractor for testing.

    Uses regular expressions to detect services, dependencies, APIs,
    patterns, frameworks, and configuration items from text.

    Example:
        >>> extractor = MockEntityExtractor()
        >>> entities = await extractor.extract("The auth-service uses PostgreSQL")
        >>> print([e.name for e in entities])
        ['auth-service', 'PostgreSQL']
    """

    async def extract(
        self, content: str, memory_id: Optional[str] = None
    ) -> List[Entity]:
        """Extract entities from text content.

        Args:
            content: The text content to extract entities from.
            memory_id: Optional ID of the source memory for tracking.

        Returns:
            List of extracted Entity objects.
        """
        entities: List[Entity] = []

        # Extract services
        entities.extend(self._extract_services(content, memory_id))

        # Extract dependencies
        entities.extend(self._extract_dependencies(content, memory_id))

        # Extract APIs
        entities.extend(self._extract_apis(content, memory_id))

        # Extract patterns
        entities.extend(self._extract_patterns(content, memory_id))

        # Extract frameworks
        entities.extend(self._extract_frameworks(content, memory_id))

        # Extract configs
        entities.extend(self._extract_configs(content, memory_id))

        return entities

    def _extract_services(
        self, content: str, memory_id: Optional[str]
    ) -> List[Entity]:
        """Extract SERVICE entities from content."""
        entities = []
        content_lower = content.lower()

        for pattern in SERVICE_PATTERNS:
            for match in re.finditer(pattern, content_lower, re.IGNORECASE):
                name = match.group(1)
                entities.append(
                    Entity(
                        name=name,
                        entity_type=EntityType.SERVICE,
                        confidence=0.8,
                        source_memory_id=memory_id,
                        mentions=[name],
                    )
                )

        return entities

    def _extract_dependencies(
        self, content: str, memory_id: Optional[str]
    ) -> List[Entity]:
        """Extract DEPENDENCY entities from content."""
        entities = []

        for dep in KNOWN_DEPENDENCIES:
            # Case-insensitive word boundary match
            pattern = rf"\b{re.escape(dep)}\b"
            if re.search(pattern, content, re.IGNORECASE):
                entities.append(
                    Entity(
                        name=dep,
                        entity_type=EntityType.DEPENDENCY,
                        confidence=0.9,
                        source_memory_id=memory_id,
                        mentions=[dep],
                    )
                )

        return entities

    def _extract_apis(
        self, content: str, memory_id: Optional[str]
    ) -> List[Entity]:
        """Extract API entities from content."""
        entities = []

        for pattern in API_PATTERNS:
            for match in re.finditer(pattern, content):
                name = match.group(1).strip()
                if name and len(name) > 1:  # Skip single /
                    entities.append(
                        Entity(
                            name=name,
                            entity_type=EntityType.API,
                            confidence=0.75,
                            source_memory_id=memory_id,
                            mentions=[name],
                        )
                    )

        return entities

    def _extract_patterns(
        self, content: str, memory_id: Optional[str]
    ) -> List[Entity]:
        """Extract PATTERN entities from content."""
        entities = []

        for pattern_name in PATTERN_KEYWORDS:
            pattern = rf"\b{re.escape(pattern_name)}\b"
            if re.search(pattern, content, re.IGNORECASE):
                entities.append(
                    Entity(
                        name=pattern_name,
                        entity_type=EntityType.PATTERN,
                        confidence=0.85,
                        source_memory_id=memory_id,
                        mentions=[pattern_name],
                    )
                )

        return entities

    def _extract_frameworks(
        self, content: str, memory_id: Optional[str]
    ) -> List[Entity]:
        """Extract FRAMEWORK entities from content."""
        entities = []

        for framework in KNOWN_FRAMEWORKS:
            pattern = rf"\b{re.escape(framework)}\b"
            if re.search(pattern, content, re.IGNORECASE):
                entities.append(
                    Entity(
                        name=framework,
                        entity_type=EntityType.FRAMEWORK,
                        confidence=0.9,
                        source_memory_id=memory_id,
                        mentions=[framework],
                    )
                )

        return entities

    def _extract_configs(
        self, content: str, memory_id: Optional[str]
    ) -> List[Entity]:
        """Extract CONFIG entities from content."""
        entities = []

        # Common config patterns to look for
        config_hints = ["_URL", "_HOST", "_PORT", "_KEY", "_SECRET", "_PATH", "_DIR"]

        for pattern in CONFIG_PATTERNS:
            for match in re.finditer(pattern, content):
                name = match.group(1)
                # Only include if it looks like a config (has underscore or known suffix)
                if "_" in name and any(hint in name for hint in config_hints):
                    entities.append(
                        Entity(
                            name=name,
                            entity_type=EntityType.CONFIG,
                            confidence=0.7,
                            source_memory_id=memory_id,
                            mentions=[name],
                        )
                    )

        return entities
