# CLAUDE.md - Project Instructions for Claude Code

This file provides context and instructions for Claude Code when working on this project.

## Project Overview

Luminescent Cluster is a context-aware AI development system with:
- **Session Memory**: Short-term context persistence via MCP server
- **Pixeltable Memory**: Long-term organizational knowledge base
- **MCP Servers**: Model Context Protocol integration for Claude

## Session Management

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
| `src/` | Core source code |
| `integrations/` | MCP server implementations |
| `tests/` | Test suite (pytest) |
| `spec/` | Requirements ledger and validation |
| `docs/adrs/` | Architecture Decision Records |
| `.claude/skills/` | Agent skills for session management |

## MCP Servers

This project provides two MCP servers:

1. **session-memory** - Task context, git integration, user memories
2. **pixeltable-memory** - Long-term organizational knowledge, ADRs, code search

## Commit Guidelines

Use conventional commits:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `refactor:` Code refactoring
- `test:` Test changes

Always include `Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>` when Claude contributes.

## Testing

```bash
# Run all tests
pytest tests/ -v --ignore=tests/test_pixeltable_mcp_server.py

# Run spec reconciliation
python spec/validation/reconcile.py

# Run specific domain tests
pytest tests/memory/ -v
pytest tests/chatbot/ -v
```
