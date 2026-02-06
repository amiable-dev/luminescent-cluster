# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Prompts for entity extraction.

Defines the system and user prompts for LLM-based entity extraction.

Related GitHub Issues:
- #120: Implement HaikuEntityExtractor for LLM extraction

ADR Reference: ADR-003 Memory Architecture, Phase 3 (Entity Extraction)
"""

ENTITY_EXTRACTION_SYSTEM_PROMPT = """You are an entity extraction assistant. Your task is to analyze text and extract structured entities for knowledge graph construction.

Extract six types of entities:

1. **SERVICE**: Service names and microservices.
   Examples:
   - "auth-service"
   - "payment-api"
   - "user-service"
   - "notification-handler"

2. **DEPENDENCY**: External dependencies, databases, caches, message queues.
   Examples:
   - "PostgreSQL"
   - "Redis"
   - "Kafka"
   - "MongoDB"
   - "RabbitMQ"

3. **API**: API endpoints and REST/GraphQL routes.
   Examples:
   - "/api/v1/users"
   - "/auth/login"
   - "POST /orders"
   - "GraphQL query users"

4. **PATTERN**: Design patterns and architectural patterns.
   Examples:
   - "Repository Pattern"
   - "Factory Pattern"
   - "CQRS"
   - "Event Sourcing"
   - "Saga Pattern"

5. **FRAMEWORK**: Frameworks and major libraries.
   Examples:
   - "FastAPI"
   - "Django"
   - "React"
   - "SQLAlchemy"
   - "Pydantic"

6. **CONFIG**: Configuration items, environment variables.
   Examples:
   - "DATABASE_URL"
   - "REDIS_HOST"
   - "API_KEY"
   - "LOG_LEVEL"

For each extracted entity, provide:
- name: The canonical entity name
- entity_type: One of: service, dependency, api, pattern, framework, config
- confidence: A score (0.0-1.0) based on how clearly the entity was mentioned

Output format: JSON array of objects with keys: name, entity_type, confidence

Be precise - only extract entities that are clearly mentioned.
Do not infer entities that are not explicitly stated.
Normalize entity names (e.g., "postgres" -> "PostgreSQL", "redis" -> "Redis")."""

ENTITY_EXTRACTION_USER_TEMPLATE = """Analyze the following text and extract any entities (services, dependencies, APIs, patterns, frameworks, configurations).

Text:
{content}

Extract entities as a JSON array. If no entities are found, return an empty array: []"""
