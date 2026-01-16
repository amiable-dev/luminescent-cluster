# Memory Provider Extension Guide

This guide explains how to implement custom `MemoryProvider` implementations following the protocol defined in ADR-003 and ADR-007.

## Protocol Definition

The `MemoryProvider` protocol is defined in `src/memory/protocols.py`:

```python
from typing import Any, Optional, Protocol, List, runtime_checkable

@runtime_checkable
class MemoryProvider(Protocol):
    """Protocol for memory storage providers."""

    async def store(self, memory: Memory, context: dict[str, Any]) -> str:
        """Store a memory and return its ID."""
        ...

    async def retrieve(self, query: str, user_id: str, limit: int = 5) -> List[Memory]:
        """Retrieve memories matching a query for a user."""
        ...

    async def get_by_id(self, memory_id: str) -> Optional[Memory]:
        """Get a specific memory by ID."""
        ...

    async def delete(self, memory_id: str) -> bool:
        """Delete a memory, return True if deleted."""
        ...

    async def search(self, user_id: str, filters: dict[str, Any], limit: int = 10) -> List[Memory]:
        """Search memories with filters."""
        ...
```

## Dual Repository Pattern

Following ADR-005, memory providers are split across repositories:

| Repository | Provider | Purpose |
|------------|----------|---------|
| luminescent-cluster (OSS) | `LocalMemoryProvider` | In-memory storage for testing/dev |
| luminescent-cloud (Private) | `CloudMemoryProvider` | Tenant-isolated Pixeltable storage |

## Implementing a Custom Provider

### Step 1: Create the Provider Class

```python
# src/memory/providers/my_provider.py

from typing import Any, List, Optional
from src.memory.schemas import Memory

class MyCustomProvider:
    """Custom memory provider implementation."""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self._client = None

    async def store(self, memory: Memory, context: dict[str, Any]) -> str:
        """Store memory in custom backend."""
        # Generate unique ID
        memory_id = self._generate_id()

        # Store with user isolation
        await self._client.insert({
            "id": memory_id,
            "user_id": memory.user_id,
            "content": memory.content,
            "memory_type": memory.memory_type.value,
            "confidence": memory.confidence,
            "created_at": memory.created_at,
            # ... other fields
        })

        return memory_id

    async def retrieve(self, query: str, user_id: str, limit: int = 5) -> List[Memory]:
        """Retrieve memories with semantic search."""
        # CRITICAL: Always filter by user_id for isolation
        results = await self._client.search(
            query=query,
            filter={"user_id": user_id},
            limit=limit,
        )

        return [self._to_memory(r) for r in results]

    async def get_by_id(self, memory_id: str) -> Optional[Memory]:
        """Get memory by ID."""
        result = await self._client.get(memory_id)
        return self._to_memory(result) if result else None

    async def delete(self, memory_id: str) -> bool:
        """Delete memory."""
        return await self._client.delete(memory_id)

    async def search(self, user_id: str, filters: dict[str, Any], limit: int = 10) -> List[Memory]:
        """Search with filters."""
        # CRITICAL: Always include user_id in filter
        query_filter = {"user_id": user_id}
        query_filter.update(filters)

        results = await self._client.find(query_filter, limit=limit)
        return [self._to_memory(r) for r in results]
```

### Step 2: Write Protocol Compliance Tests

Create tests following the three-layer pattern:

```python
# tests/memory/test_my_provider_compliance.py

import pytest
from src.memory.providers.my_provider import MyCustomProvider

class TestProtocolDefinition:
    """Layer 1: Verify protocol interface."""

    def test_implements_required_methods(self):
        provider = MyCustomProvider("connection_string")
        assert hasattr(provider, 'store')
        assert hasattr(provider, 'retrieve')
        assert hasattr(provider, 'get_by_id')
        assert hasattr(provider, 'delete')
        assert hasattr(provider, 'search')

class TestBehavior:
    """Layer 2: Verify expected behaviors."""

    @pytest.mark.asyncio
    async def test_store_returns_id(self):
        provider = MyCustomProvider("test")
        memory_id = await provider.store(sample_memory, {})
        assert isinstance(memory_id, str)
        assert len(memory_id) > 0

class TestCompliance:
    """Layer 3: Full CRUD workflow."""

    @pytest.mark.asyncio
    async def test_complete_crud_workflow(self):
        provider = MyCustomProvider("test")

        # Create
        memory_id = await provider.store(sample_memory, {})

        # Read
        retrieved = await provider.get_by_id(memory_id)
        assert retrieved.content == sample_memory.content

        # Delete
        deleted = await provider.delete(memory_id)
        assert deleted is True
```

### Step 3: Add Security Tests

Memory isolation is a critical exit criteria:

```python
# tests/memory/security/test_my_provider_isolation.py

class TestMemoryIsolation:
    """Verify zero cross-user leakage."""

    @pytest.mark.asyncio
    async def test_users_cannot_access_each_others_memories(self):
        provider = MyCustomProvider("test")

        # Store for user-1
        await provider.store(user1_memory, {})

        # Search as user-2
        results = await provider.search("user-2", {}, limit=100)

        # Should find nothing
        for memory in results:
            assert memory.user_id != "user-1"
```

### Step 4: Register with Extension Registry

For cloud providers, register via the Extension Registry (ADR-005):

```python
# In luminescent-cloud initialization

from src.extensions import ExtensionRegistry
from cloud.memory import CloudMemoryProvider

registry = ExtensionRegistry.get()
registry.memory_provider = CloudMemoryProvider(
    pixeltable_config=config,
    tenant_provider=registry.tenant_provider,
)
```

## Cloud Provider Requirements

When implementing `CloudMemoryProvider` for luminescent-cloud:

1. **Tenant Isolation**: Use `TenantProvider.get_tenant_filter()` for all queries
2. **Quota Enforcement**: Check `UsageTracker.check_quota()` before operations
3. **Audit Logging**: Log via `AuditLogger` for compliance
4. **GDPR Compliance**: Implement `GDPRService` integration for data deletion

```python
# Example CloudMemoryProvider structure

class CloudMemoryProvider:
    def __init__(self, pixeltable_config, tenant_provider, audit_logger):
        self.tenant_provider = tenant_provider
        self.audit_logger = audit_logger

    async def store(self, memory: Memory, context: dict) -> str:
        tenant_id = self.tenant_provider.get_tenant_id(context)

        # Log operation
        await self.audit_logger.log({
            "operation": "memory.store",
            "tenant_id": tenant_id,
            "user_id": memory.user_id,
        })

        # Store with tenant isolation
        return await self._pixeltable_store(memory, tenant_id)
```

## Performance Guidelines

| Operation | Target Latency | Notes |
|-----------|---------------|-------|
| Store | <10ms | In-memory index update |
| Retrieve | <50ms p95 | Hot memory tier |
| Search | <200ms p95 | With semantic search |
| Delete | <10ms | Soft delete preferred |

## Related Documentation

- [Memory Architecture](../architecture/memory-tiers.md)
- [ADR-003: Memory Architecture](../adrs/ADR-003-project-intent-persistent-context.md)
- [ADR-005: Repository Organization](../adrs/ADR-005-repository-organization-strategy.md)
- [ADR-007: Protocol Consolidation](../adrs/ADR-007-cross-adr-integration-guide.md)
