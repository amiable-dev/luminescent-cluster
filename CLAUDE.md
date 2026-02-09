# CLAUDE.md - Project Instructions for Claude Code

This file provides context and instructions for Claude Code when working on this project.

## Project Overview

Luminescent Cluster is a context-aware AI development system that provides persistent memory and multi-platform chatbot capabilities for AI agents. The system is designed around three core architectural patterns:

1. **Three-Tier Memory Architecture** - Hot session memory → Persistent Pixeltable storage → LLM Council orchestration
2. **Protocol-Based Extension System** - Duck-typed interfaces enabling OSS/Cloud separation
3. **Chatbot Gateway Pattern** - Central router with platform-specific adapters

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Claude Code / Agent                       │
└──────────────────────────────┬──────────────────────────────────┘
                               │ MCP Protocol
         ┌─────────────────────┼─────────────────────┐
         ▼                     ▼                     ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Session Memory │  │Pixeltable Memory│  │   LLM Council   │
│   (Hot State)   │  │  (Persistent)   │  │ (Orchestration) │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               ▼
                    ┌─────────────────────┐
                    │   Chatbot Gateway   │
                    │  (Multi-Platform)   │
                    └─────────────────────┘
                               │
         ┌──────────┬──────────┼──────────┬──────────┐
         ▼          ▼          ▼          ▼          ▼
     Discord     Slack    Telegram   WhatsApp    CLI
```

### Memory Tiers

| Tier | Purpose | Persistence | Location |
|------|---------|-------------|----------|
| **Session** | Task context, git state, recent conversation | Per-session | `src/luminescent_cluster/servers/session_memory.py` |
| **Pixeltable** | ADRs, code embeddings, incident history | Permanent | `src/luminescent_cluster/servers/pixeltable.py` |
| **Council** | Multi-LLM consensus, verification | Per-request | (external: llm-council MCP server) |

### Extension System (ADR-005)

The system uses **protocol-based interfaces** for extensibility:

```python
# src/luminescent_cluster/extensions/protocols.py - Duck-typed extension contracts
class MemoryProvider(Protocol):
    async def store(self, key: str, value: Any) -> None: ...
    async def retrieve(self, key: str) -> Any: ...

class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> list[float]: ...
```

**Key insight**: Extensions are discovered at runtime via entry points, allowing the OSS version to use local embeddings while cloud deployments can swap in proprietary providers.

### MaaS: Memory as a Service (ADR-003)

Multi-agent workflows use **memory pools** with ownership semantics:

- **Agent Handoffs**: Memory transfers between specialized agents
- **Shared Pools**: Concurrent access with locking
- **Provenance Tracking**: Full audit trail for memory mutations

See `src/luminescent_cluster/memory/maas/` for implementation.

## Installation

```bash
# Global install (session memory only - lightweight, recommended for multi-project use)
uv tool install luminescent-cluster

# Global install with Pixeltable long-term memory (~500MB macOS, larger on Linux/CUDA)
uv tool install "luminescent-cluster[pixeltable]"

# Or via pip/pipx
pip install luminescent-cluster
pip install "luminescent-cluster[pixeltable]"

# Development (editable install in this repo)
pip install -e ".[dev]"
```

## CLI Usage

```bash
# Start combined MCP server (default)
luminescent-cluster

# Start specific server
luminescent-cluster session
luminescent-cluster pixeltable

# Run spec validation
luminescent-cluster validate --verbose

# Install bundled skills to .claude/skills
luminescent-cluster install-skills

# Install skills to custom directory
luminescent-cluster install-skills --target path/to/skills

# List available bundled skills
luminescent-cluster install-skills --list

# Overwrite existing skills
luminescent-cluster install-skills --force

# Show version
luminescent-cluster --version
```

## Session Management

Skills are bundled in the wheel and can be installed to any project:

```bash
# Install skills to .claude/skills (default target for Claude Code)
luminescent-cluster install-skills
```

Run these skills to maintain context across coding sessions:

- **`/session-init`** - Run at the start of each coding session
  - Loads recent git activity and current branch
  - Retrieves task context from session memory
  - Queries relevant ADRs from organizational knowledge

- **`/session-save`** - Run before ending work or making commits
  - Summarizes session accomplishments
  - Updates task context for next session
  - Prepares pending changes for commit

## Critical: Python Version Constraint

**The Pixeltable database is bound to the Python version that created it.**

Using a different Python minor version will cause a silent segmentation fault. Always verify:

```bash
cat .python-version  # Should show 3.11
python --version     # Must match
```

See ADR-001 for full details on this constraint.

## Requirement Traceability

Tests should be linked to requirements. Run reconciliation to verify coverage:

```bash
python spec/validation/reconcile.py --verbose
```

Use pytest markers for new tests:

```python
@pytest.mark.requirement("REQ-XXX-NNN")
def test_feature():
    pass
```

## Key Directories

| Path | Purpose |
|------|---------|
| `src/luminescent_cluster/` | Core package source code |
| `src/luminescent_cluster/memory/` | Memory system (extraction, evaluation, MaaS) |
| `src/luminescent_cluster/extensions/` | Extension protocols and registry |
| `src/luminescent_cluster/chatbot/` | Chatbot gateway and adapters |
| `src/luminescent_cluster/integrations/` | PAT integrations (GitHub, GitLab) |
| `src/luminescent_cluster/skills/` | Bundled skills and progressive disclosure loader |
| `src/luminescent_cluster/servers/` | MCP server implementations |
| `tests/` | Test suite (pytest) |
| `spec/` | Requirements ledger and validation |
| `spec/ledger.yml` | Requirement-to-test mappings (89 requirements) |
| `docs/adrs/` | Architecture Decision Records |
| `.claude/skills/` | Agent skills for session management |

## Important Files

| File | Purpose |
|------|---------|
| `src/luminescent_cluster/servers/session_memory.py` | Session memory MCP server |
| `src/luminescent_cluster/servers/pixeltable.py` | Pixeltable knowledge base MCP server |
| `src/luminescent_cluster/cli.py` | CLI entry point (includes `install-skills`) |
| `src/luminescent_cluster/skills/loader.py` | SkillLoader with progressive disclosure (Level 1/2/3) |
| `src/luminescent_cluster/version_guard.py` | Python version safety guard (ADR-001) |
| `spec/validation/reconcile.py` | Requirement traceability validation |
| `.spec-baseline.json` | Coverage baseline for ratchet mechanism |

## MCP Servers

This project provides MCP servers via the CLI:

| Command | Purpose | Key Tools |
|---------|---------|-----------|
| `luminescent-cluster session` | Task context, git integration, user memories | `set_task_context`, `get_recent_commits`, `create_user_memory` |
| `luminescent-cluster pixeltable` | Long-term organizational knowledge | `search_organizational_memory`, `get_architectural_decisions`, `ingest_codebase` |

### MCP Configuration

To connect Claude Code to the MCP servers, create a `.mcp.json` in your project root (this file is gitignored — each developer configures their own).

**Session memory only** (recommended default — works with base install):

```json
{
  "mcpServers": {
    "session-memory": {
      "command": "luminescent-cluster",
      "args": ["session"]
    }
  }
}
```

**Session + Pixeltable** (requires `luminescent-cluster[pixeltable]` extra — adds ~500MB on macOS, more on Linux/CUDA):

```json
{
  "mcpServers": {
    "session-memory": {
      "command": "luminescent-cluster",
      "args": ["session"]
    },
    "pixeltable-memory": {
      "command": "luminescent-cluster",
      "args": ["pixeltable"]
    }
  }
}
```

**For local development** (editable install in a venv without PATH):

```json
{
  "mcpServers": {
    "session-memory": {
      "command": "/path/to/your/.venv/bin/luminescent-cluster",
      "args": ["session"]
    }
  }
}
```

**Note:** `.mcp.json` must NOT be committed with absolute paths. It is already in `.gitignore`. The `pixeltable-memory` server requires the `[pixeltable]` extra — if you installed with `uv tool install luminescent-cluster` (no extras), only configure `session-memory`.

For local development with Pixeltable, install with: `pip install -e ".[dev,pixeltable]"`

### Chatbot Gateway (ADR-006)

The chatbot system uses a **gateway pattern** with platform-specific adapters:

```
User Message → Gateway Router → Platform Adapter → Normalized Message → AI Processing
                    ↓
         Rate Limiting, Auth, Routing
```

**Supported platforms**: Discord, Slack, Telegram, WhatsApp (planned)

Each adapter translates platform-specific events to a common message format, enabling uniform AI processing across all platforms.

## Architecture Decision Records (ADRs)

Key architectural decisions are documented in `docs/adrs/`:

| ADR | Topic | Key Decision |
|-----|-------|--------------|
| ADR-001 | Python Version Guard | Hard exit on version mismatch (no warning mode) |
| ADR-002 | Agent Skills | Slash commands for workflow automation |
| ADR-003 | Memory Architecture | Three-tier system with MaaS multi-agent support |
| ADR-005 | Extension System | Protocol-based interfaces for OSS/Cloud separation |
| ADR-006 | Chatbot Gateway | Platform adapters with rate limiting and routing |
| ADR-007 | Cross-ADR Integration | System-wide consistency requirements |
| ADR-009 | Spec/Ledger Reconciliation | Requirement traceability with pytest markers |

## Common Patterns

### Adding a New MCP Tool

1. Define tool schema in `list_tools()` method
2. Implement handler in `call_tool()` method
3. Add requirement to `spec/ledger.yml`
4. Create test with `@pytest.mark.requirement()` marker
5. Run `python spec/validation/reconcile.py` to verify

### Adding a New Chatbot Adapter

1. Create adapter in `src/luminescent_cluster/chatbot/adapters/`
2. Implement the adapter protocol
3. Register in gateway router
4. Add rate limiting configuration
5. Create integration tests

### Adding a New Bundled Skill

1. Create `src/luminescent_cluster/skills/bundled/<skill-name>/SKILL.md` with YAML frontmatter
2. Add entry to `src/luminescent_cluster/skills/bundled/marketplace.json`
3. Add tests to `tests/test_skills.py` (TestBundledSkillFormat class)
4. Verify with `luminescent-cluster install-skills --list`

### Adding a New Memory Provider

1. Implement protocol from `src/luminescent_cluster/extensions/protocols.py`
2. Register via entry points in `pyproject.toml`
3. Add tests for store/retrieve operations

## Commit Guidelines

Use conventional commits:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `refactor:` Code refactoring
- `test:` Test changes

Always include `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>` when Claude contributes.

## Build & Development Commands

### Environment Setup

```bash
# Verify Python version (CRITICAL - must be 3.11 for existing Pixeltable databases)
cat .python-version && python --version

# Create virtual environment
uv venv --python 3.11
source .venv/bin/activate

# Install dependencies
uv pip install -e ".[dev]"

# Quick start (does all of the above)
./quickstart.sh
```

### Testing

```bash
# Run all tests (121 tests)
pytest tests/ -v --ignore=tests/test_pixeltable_mcp_server.py

# Run a single test file
pytest tests/test_version_guard.py -v

# Run a single test function
pytest tests/test_version_guard.py::test_version_mismatch_exit_code -v

# Run tests by marker
pytest -m "critical" -v           # Critical priority tests
pytest -m "security" -v           # Security tests
pytest -m "requirement" -v        # Tests linked to requirements

# Run with coverage
pytest tests/ -v --cov=luminescent_cluster

# Run spec reconciliation (requirement traceability)
python spec/validation/reconcile.py --verbose
```

### Linting & Formatting

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Fix auto-fixable issues
ruff check --fix .
```

### Build & Publish

```bash
# Build package
uv build

# Publish to Test PyPI
uv publish --repository testpypi

# Publish to PyPI
uv publish
```

### Documentation

```bash
# Serve docs locally
mkdocs serve

# Build docs
mkdocs build
```

### MCP Server Development

```bash
# Run session memory server directly
luminescent-cluster session

# Run pixeltable server directly (requires [pixeltable] extra)
luminescent-cluster pixeltable

# Run MCP server tests
pytest tests/test_session_memory_mcp_server.py -v
```
