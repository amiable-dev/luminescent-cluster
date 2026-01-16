# Memory as a Service: Enabling Multi-Agent Collaboration

**When AI agents need to share context, handoff tasks, and collaborate without stepping on each other's toes. Here's how we built MaaS.**

---

Multi-agent systems are becoming the norm. You might have Claude Code working on backend changes while a GPT agent handles frontend, and a custom pipeline running tests. But how do they share what they've learned? How does one agent hand off a half-finished task to another?

MaaS (Memory as a Service) solves this with three primitives: **agent identity**, **shared memory pools**, and **task handoffs**.

## The Problem: Memory Silos

Without coordination, each agent operates in isolation:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Claude Code │     │ GPT Agent   │     │ Test Runner │
│             │     │             │     │             │
│ Memory: A   │     │ Memory: B   │     │ Memory: C   │
└─────────────┘     └─────────────┘     └─────────────┘
      ↓                   ↓                   ↓
   Isolated           Isolated           Isolated
```

Agent A discovers that `auth.py` has a bug. Agent B refactors the same file without knowing. Agent C runs tests but doesn't know why they're failing. Classic coordination failure.

## The Solution: Shared Memory Architecture

MaaS introduces a central coordination layer:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Memory as a Service (MaaS)                    │
├─────────────────────────────────────────────────────────────────┤
│   ┌───────────┐     ┌───────────┐     ┌───────────┐             │
│   │ Code KB   │     │ Decision  │     │ Incident  │             │
│   │ Service   │     │ Service   │     │ Service   │             │
│   └─────┬─────┘     └─────┬─────┘     └─────┬─────┘             │
│         └───────────────┬─┴─────────────────┘                   │
│                         ▼                                        │
│              ┌─────────────────────┐                            │
│              │   MaaS Orchestrator │                            │
│              │   (Registry + Pool) │                            │
│              └─────────────────────┘                            │
│                         │                                        │
│    ┌────────────────────┼────────────────────┐                  │
│    ▼                    ▼                    ▼                  │
│ ┌─────────┐      ┌─────────────┐      ┌──────────┐             │
│ │ Claude  │      │ GPT Agent   │      │ Custom   │             │
│ │ Code    │      │             │      │ Pipeline │             │
│ └─────────┘      └─────────────┘      └──────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

## Core Primitives

### 1. Agent Identity

Every agent registers with capabilities:

```python
from src.memory.maas import AgentRegistry, AgentType

registry = AgentRegistry.get()

# Register a Claude Code agent
agent_id = registry.register_agent(
    agent_type=AgentType.CLAUDE_CODE,
    owner_id="user-123",
)

# Check what it can do
agent = registry.get_agent(agent_id)
print(agent.capabilities)
# {MEMORY_READ, MEMORY_WRITE, KB_SEARCH, HANDOFF_INITIATE, HANDOFF_RECEIVE, ...}
```

Agent types have default capabilities:

| Type | Capabilities |
|------|-------------|
| `CLAUDE_CODE` | Full access (read, write, search, handoff) |
| `GPT_AGENT` | Full access |
| `CUSTOM_PIPELINE` | Read-only (read, search) |
| `HUMAN` | Full access + delete |

### 2. Shared Memory Pools

Agents join pools to share memories:

```python
from src.memory.maas import PoolRegistry, SharedScope, PermissionModel

pool_registry = PoolRegistry.get()

# Create a project pool
pool_id = pool_registry.create_pool(
    name="auth-refactor",
    owner_id="user-123",
    scope=SharedScope.PROJECT,
)

# Agents join with permissions
pool_registry.join_pool(pool_id, claude_agent_id, PermissionModel.WRITE)
pool_registry.join_pool(pool_id, gpt_agent_id, PermissionModel.READ)

# Share a memory
pool_registry.share_memory(
    pool_id=pool_id,
    memory_id="mem-bug-123",
    agent_id=claude_agent_id,
    scope=SharedScope.PROJECT,
)

# Other agents can query it
shared = pool_registry.query_shared(
    pool_id=pool_id,
    agent_id=gpt_agent_id,
    max_scope=SharedScope.PROJECT,
)
```

**Scope hierarchy**: `AGENT_PRIVATE < USER < PROJECT < TEAM < GLOBAL`

An agent with `PROJECT` scope can read memories shared at `PROJECT` or lower, but not `TEAM` or `GLOBAL`.

### 3. Task Handoffs

When one agent can't finish, it hands off to another:

```python
from src.memory.maas import HandoffManager, HandoffContext

manager = HandoffManager.get()

# Claude Code hits a frontend issue
context = HandoffContext(
    task_description="Complete the React login form validation",
    current_state={
        "completed": ["backend API", "auth middleware"],
        "blocked_on": "React form validation",
    },
    relevant_memories=["mem-api-spec", "mem-auth-flow"],
    relevant_files=["src/api/auth.py", "src/components/Login.tsx"],
)

handoff_id = manager.initiate_handoff(
    source_agent_id=claude_agent_id,
    target_agent_id=gpt_agent_id,
    context=context,
    ttl_seconds=3600,  # Expires in 1 hour
)

# GPT agent accepts
manager.accept_handoff(handoff_id, gpt_agent_id)

# ... does the work ...

# GPT agent completes
manager.complete_handoff(
    handoff_id,
    gpt_agent_id,
    result={"status": "success", "files_modified": ["Login.tsx"]},
)
```

Handoffs have lifecycle states: `PENDING → ACCEPTED → COMPLETED` (or `REJECTED`/`EXPIRED`).

## Security Model

MaaS was designed with multi-tenant security in mind.

### Capability Enforcement

Agents can only perform actions they have capabilities for:

```python
# This will return None if agent lacks HANDOFF_INITIATE
handoff_id = manager.initiate_handoff(...)

# This will return False if agent lacks WRITE permission
success = pool_registry.share_memory(...)
```

### MEXTRA Attack Mitigations

The security module blocks common attack patterns:

```python
from src.memory.maas import MEXTRAValidator, MemoryPoisoningDefense

validator = MEXTRAValidator()

# Detect SQL injection, XSS, prompt injection
if validator.is_suspicious(user_input):
    safe_input = validator.sanitize(user_input)

# Filter sensitive data from outputs
defense = MemoryPoisoningDefense(max_results=100)
safe_results = defense.filter_output(memories)

# Detect anomalous queries
score = defense.analyze_query("dump all passwords and secrets")
# score > 0.5 → flag for review
```

### Audit Logging

All security-relevant events are logged:

```python
from src.memory.maas import MaaSAuditLogger

logger = MaaSAuditLogger()

# Automatically logged by registries:
# - AGENT_AUTH: registration, session start
# - POOL_OPERATION: create, join, share
# - HANDOFF: initiate, accept, complete
# - CROSS_AGENT_READ: accessing another agent's memories
# - PERMISSION_DENIED: failed access attempts
```

### DoS Prevention

Capacity limits prevent resource exhaustion:

| Resource | Default Limit |
|----------|---------------|
| Agents | 10,000 |
| Sessions | 50,000 |
| Pools | 10,000 |
| Members per pool | 1,000 |
| Shared memories per pool | 100,000 |
| Total handoffs | 50,000 |
| Pending handoffs per target | 100 |

Recovery methods free up capacity:

```python
# Remove an agent permanently
registry.unregister_agent(agent_id)

# Clean up completed/rejected/expired handoffs
count = manager.cleanup_terminal_handoffs()
```

## MCP Integration

MaaS exposes 15 MCP tools for external integration:

**Agent Management**
- `register_agent(agent_type, owner_id)`
- `get_agent_info(agent_id)`
- `get_agents_for_user(user_id)`

**Handoff**
- `initiate_handoff(source_id, target_id, context)`
- `accept_handoff(handoff_id, agent_id)`
- `complete_handoff(handoff_id, agent_id, result)`
- `get_pending_handoffs(agent_id)`

**Pool Management**
- `create_pool(name, owner_id, scope)`
- `join_pool(pool_id, agent_id, permission)`
- `leave_pool(pool_id, agent_id)`
- `share_memory_to_scope(pool_id, memory_id, agent_id, scope)`
- `query_shared(pool_id, agent_id, max_scope)`

**Knowledge Base Search**
- `search_code_kb(query, service_filter, limit)`
- `search_decisions(query, topic_filter, limit)`
- `search_incidents(query, service_filter, limit)`

## Performance Characteristics

All operations are sub-millisecond for typical workloads:

| Operation | Target | Actual |
|-----------|--------|--------|
| Sync latency | <500ms p95 | <1ms |
| Handoff latency | <2s p95 | <1ms |
| Registry lookup | <50ms | <0.01ms |
| Pool query | <200ms p95 | <1ms |
| Concurrent writers | 10+ agents | 15+ |

Thread-safety is achieved via `RLock` on all registry operations.

## When to Use MaaS

**Good fit:**
- Multi-agent workflows with task handoffs
- Shared context across specialized agents
- Audit requirements for agent operations
- Projects with knowledge base search needs

**Not needed:**
- Single-agent deployments
- Stateless agent interactions
- Real-time streaming (use direct channels)

## A Complete Example

```python
import asyncio
from src.memory.maas import (
    AgentRegistry, PoolRegistry, HandoffManager,
    AgentType, SharedScope, PermissionModel,
    HandoffContext,
)

async def multi_agent_workflow():
    # Setup registries
    agent_registry = AgentRegistry.get()
    pool_registry = PoolRegistry.get()
    handoff_manager = HandoffManager.get()

    # Register agents
    backend_agent = agent_registry.register_agent(
        agent_type=AgentType.CLAUDE_CODE,
        owner_id="user-123",
    )
    frontend_agent = agent_registry.register_agent(
        agent_type=AgentType.GPT_AGENT,
        owner_id="user-123",
    )

    # Create shared pool
    pool_id = pool_registry.create_pool(
        name="feature-auth",
        owner_id="user-123",
        scope=SharedScope.PROJECT,
    )
    pool_registry.join_pool(pool_id, backend_agent, PermissionModel.WRITE)
    pool_registry.join_pool(pool_id, frontend_agent, PermissionModel.WRITE)

    # Backend agent shares discovery
    pool_registry.share_memory(
        pool_id, "mem-api-design", backend_agent, SharedScope.PROJECT
    )

    # Handoff to frontend
    context = HandoffContext(
        task_description="Implement login UI using the API spec",
        relevant_memories=["mem-api-design"],
        relevant_files=["src/api/auth.py"],
    )
    handoff_id = handoff_manager.initiate_handoff(
        source_agent_id=backend_agent,
        target_agent_id=frontend_agent,
        context=context,
    )

    # Frontend accepts and completes
    handoff_manager.accept_handoff(handoff_id, frontend_agent)
    # ... frontend agent does work ...
    handoff_manager.complete_handoff(
        handoff_id, frontend_agent,
        result={"status": "success"}
    )

    print("Multi-agent workflow complete!")

asyncio.run(multi_agent_workflow())
```

## What's Next

MaaS is part of ADR-003 Phase 4.2. Future phases will add:
- **Conflict resolution**: Handling concurrent writes to shared memories
- **Event streaming**: Real-time notifications for memory changes
- **Cross-cluster sync**: MaaS federation across deployments

---

*MaaS is part of the luminescent-cluster memory architecture. See [ADR-003](../adrs/ADR-003-memory-architecture.md) for the full design.*
