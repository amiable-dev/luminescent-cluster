# Memory as a Service (MaaS)

ADR-003 Phase 4.2 Implementation Guide

## Overview

MaaS (Memory as a Service) enables multi-agent collaboration by providing:

- **Agent Registry**: Track agents, capabilities, and sessions
- **Shared Memory Pools**: Named pools with access control
- **Agent Handoff**: Context transfer between specialized agents
- **Security**: MEXTRA defense, audit logging, isolation guarantees

## Architecture

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

## Quick Start

### Register an Agent

```python
from src.memory.maas import AgentRegistry, AgentType

registry = AgentRegistry.get()

agent_id = registry.register_agent(
    agent_type=AgentType.CLAUDE_CODE,
    owner_id="user-123",
)
```

### Create a Shared Pool

```python
from src.memory.maas import PoolRegistry, SharedScope, PermissionModel

pool_registry = PoolRegistry.get()

pool_id = pool_registry.create_pool(
    name="project-memories",
    owner_id="user-123",
    scope=SharedScope.PROJECT,
)

# Join an agent to the pool
pool_registry.join_pool(pool_id, agent_id, PermissionModel.WRITE)

# Share a memory
pool_registry.share_memory(pool_id, "mem-123", agent_id, SharedScope.PROJECT)
```

### Initiate a Handoff

```python
from src.memory.maas import HandoffManager, HandoffContext

manager = HandoffManager.get()

context = HandoffContext(
    task_description="Complete the authentication flow",
    current_state={"step": 2, "total_steps": 5},
    relevant_memories=["mem-1", "mem-2"],
    relevant_files=["auth.py", "config.yaml"],
)

handoff_id = manager.initiate_handoff(
    source_agent_id=source_id,
    target_agent_id=target_id,
    context=context,
)

# Target agent accepts
manager.accept_handoff(handoff_id, target_id)

# Target agent completes
manager.complete_handoff(handoff_id, target_id, result={"status": "success"})
```

## Core Components

### Agent Types

| Type | Description | Default Capabilities |
|------|-------------|---------------------|
| `CLAUDE_CODE` | Anthropic's Claude Code | Full (read, write, search, handoff) |
| `GPT_AGENT` | OpenAI GPT agents | Full (read, write, search, handoff) |
| `CUSTOM_PIPELINE` | User-defined automation | Limited (read, search) |
| `HUMAN` | Human operators | Full + delete |

### Agent Capabilities

| Capability | Description |
|------------|-------------|
| `MEMORY_READ` | Read memories from pools |
| `MEMORY_WRITE` | Write memories to pools |
| `MEMORY_DELETE` | Delete memories (admin) |
| `KB_SEARCH` | Search knowledge bases |
| `DECISION_READ` | Read ADRs and decisions |
| `INCIDENT_READ` | Read incident history |
| `HANDOFF_INITIATE` | Start a handoff |
| `HANDOFF_RECEIVE` | Accept a handoff |

### Scope Hierarchy

```
AGENT_PRIVATE < USER < PROJECT < TEAM < GLOBAL
```

An agent with scope X can read memories with scope <= X.

### Permission Levels

| Permission | Includes |
|------------|----------|
| `READ` | Query and retrieve |
| `WRITE` | READ + add/update |
| `ADMIN` | WRITE + manage membership |

## MCP Tools

MaaS exposes 15 MCP tools for external integration:

### Agent Management
- `register_agent(agent_type, owner_id)`
- `get_agent_info(agent_id)`
- `get_agents_for_user(user_id)`

### Handoff
- `initiate_handoff(source_id, target_id, context)`
- `accept_handoff(handoff_id, agent_id)`
- `complete_handoff(handoff_id, agent_id, result)`
- `get_pending_handoffs(agent_id)`

### Pool Management
- `create_pool(name, owner_id, scope)`
- `join_pool(pool_id, agent_id, permission)`
- `leave_pool(pool_id, agent_id)`
- `share_memory_to_scope(pool_id, memory_id, agent_id, scope)`
- `query_shared(pool_id, agent_id, max_scope)`

### Knowledge Base Search
- `search_code_kb(query, service_filter, limit)`
- `search_decisions(query, topic_filter, limit)`
- `search_incidents(query, service_filter, limit)`

## Security Model

### MEXTRA Attack Mitigations

1. **Input Sanitization**: Detect SQL injection, XSS, prompt injection
2. **Output Filtering**: Mask sensitive data, limit results
3. **Query Analysis**: Score queries for anomalous patterns
4. **Rate Limiting**: Per-agent, per-session limits

### Audit Logging

All security-relevant events are logged:
- `AGENT_AUTH`: Agent registration, authentication
- `CROSS_AGENT_READ`: Cross-agent memory access
- `PERMISSION_DENIED`: Failed access attempts

### Usage

```python
from src.memory.maas import MEXTRAValidator, MemoryPoisoningDefense

# Validate input
validator = MEXTRAValidator()
if validator.is_suspicious(user_input):
    # Block or sanitize
    safe_input = validator.sanitize(user_input)

# Filter output
defense = MemoryPoisoningDefense(max_results=100)
safe_results = defense.filter_output(raw_results)
```

## Exit Criteria

| Metric | Target | Achieved |
|--------|--------|----------|
| Sync latency | <500ms p95 | <1ms |
| Handoff latency | <2s p95 | <1ms |
| Registry lookup | <50ms | <0.01ms |
| Pool query latency | <200ms p95 | <1ms |
| Concurrent writers | 10+ agents | 15+ |
| Cross-agent isolation | Zero unauthorized | Verified |

## Testing

```bash
# Run all MaaS tests
pytest tests/memory/maas/ -v

# Run security tests
pytest tests/memory/security/test_maas_isolation.py -v

# Run benchmarks
pytest tests/memory/benchmarks/test_maas_exit_criteria.py -v

# Full suite
pytest tests/memory/ -v
```

## Related

- **ADR-003**: Memory Architecture (Phase 4.2)
- **GitHub Issues**: #132-167 (36 issues)
