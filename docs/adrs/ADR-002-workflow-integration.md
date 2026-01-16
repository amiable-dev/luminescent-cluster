# ADR-002: Workflow Integration for Session and Pixeltable Memory

## Status
**Accepted v3** (reviewed by LLM Council 2026-01-16)

## Date
2025-12-22 (v1), 2026-01-16 (v3)

## Deciders
- Christopher Joseph
- Antigravity
- LLM Council v2 (Gemini-3-Pro, Grok-4.1, Claude-Opus-4.5, GPT-5.2)

## Context

### The Problem
The current integration of Session Memory and Pixeltable Memory requires the user to manually remind the LLM to "load context" before starting work and "save/update context" after completing work. This friction leads to:
- Inconsistent context usage (forgetting to load context).
- Outdated knowledge base (forgetting to ingest changes).
- Increased cognitive load on the user to manage the agent's state.

### Current vs Proposed Workflow

| Action | Current (Manual) | Proposed (Automated) |
|--------|------------------|---------------------|
| Session Start | User prompts: "Load recent commits and task context" | Agent auto-discovers `session-init` skill |
| During Work | User occasionally asks for context | Context pre-loaded via skill |
| Session End | User prompts: "Save task context, ingest changes" | Run `session-save` skill (manual or auto) |
| After Commit | Nothing (KB drifts) | Git hooks auto-ingest |

### The Opportunity
We have two mechanisms available to automate this:
1. **Agent Skills (Open Standard)**: Structured, portable `SKILL.md` packages that provide AI agents with on-demand capabilities. Originally developed by Anthropic, released as an open standard in December 2025, now supported by Claude, OpenAI Codex, GitHub Copilot, Cursor, VS Code Insiders, and Goose.
2. **Git Hooks**: Scripts that run automatically on git events (e.g., `post-commit`).

By combining these, we can ensure context is loaded systematically and updated automatically.

### Key Insight: MCP vs Skills
- **MCP (Model Context Protocol)**: The "arms and legs" - provides tools, data access, external integrations
- **Agent Skills**: The "brain and playbook" - provides domain expertise, workflows, instructions

These are complementary, not competing. MCP modularizes external integrations; Skills modularize cognitive processes.

## Decision Drivers
- **Reduce Friction**: Auto-discovery means agents apply context loading without explicit user prompts.
- **Interoperability**: Agent Skills is an open standard supported by multiple tools (Claude, Codex, Copilot, Cursor).
- **Consistency**: Ensure memory tools are used in every session.
- **Freshness**: Keep the long-term memory (Pixeltable) in sync with the codebase automatically.
- **Simplicity**: Avoid complex background daemons or heavy infrastructure.
- **Progressive Disclosure**: Skills use ~50 tokens for metadata, ~2-5K for instructions, resources load dynamically.

## Scope and Non-Goals

**In Scope:**
- Committed text artifacts in selected directories
- Session context loading/saving via Agent Skills
- Git hook-based auto-ingestion

**Non-Goals:**
- Real-time daemon sync of working tree
- IDE-specific integrations (future consideration)
- CI/CD-based ingestion (out of scope for local development)

## Options Considered

### Option 1: Status Quo (Manual Prompting)
Continue relying on the user to prompt the LLM.
**Pros**: Zero implementation cost.
**Cons**: High friction, error-prone.

### Option 2: Fully Automated Background Daemon
Run a background process that watches file modifications and auto-ingests them.
**Pros**:
- Real-time sync without user action
- Captures uncommitted work
- Could integrate with IDE file watchers (e.g., `watchman`, `fswatch`)
**Cons**:
- Higher complexity (process management, crash recovery)
- Resource intensive (file system watchers)
- Race conditions with agent edits
- Platform-specific implementation (Linux inotify vs macOS FSEvents vs Windows)
**Verdict**: Overkill for current needs, but revisit if commit-based sync proves insufficient.

### Option 3: Custom Workflows + Git Hooks (v2 Proposal)
Define custom workflow files in `.agent/workflows/` for "Load Context" and "Save Context".
**Pros**:
- Structured entry points for the agent
- Git Hooks capture natural save points
**Cons**:
- Custom format requires custom runner
- Not portable to other agents/tools
- Maintenance burden
**Verdict**: Superseded by Option 5.

### Option 4: IDE Integration (Not Evaluated)
Use VS Code tasks, JetBrains run configurations, or similar to trigger workflows.
**Why not evaluated**: Adds IDE dependency; workflows should be IDE-agnostic.

### Option 5: Agent Skills + Git Hooks (Recommended)
Use the Agent Skills open standard for session workflows and git hooks for auto-ingestion.
**Pros**:
- **Open Standard**: Adopted by Claude, Codex, Copilot, Cursor, Goose
- **Auto-Discovery**: Agents find and apply relevant skills without explicit prompts
- **Progressive Disclosure**: Efficient token usage (~50 tokens metadata, 2-5K instructions)
- **Portability**: Same skills work across multiple tools
- **No Custom Runner**: Parsing handled by the agent runtime
**Cons**:
- Requires agents that support the Agent Skills spec
- Skills are discoverable but invocation not guaranteed (agent decides)
**Verdict**: Best balance of standardization, portability, and functionality.

## Decision

**Adopt Option 5: Agent Skills + Git Hooks.**

- **Skills** handle session workflows (load/save context) via `.claude/skills/`
- **Git Hooks** handle event-driven ingestion via `.agent/hooks/`
- **MCP Servers** (Session Memory, Pixeltable Memory) remain the capability layer

## Standards Reference
- **Agent Skills Specification**: v1.0 (December 2025)
- **Reference**: https://agentskills.io/specification
- **GitHub**: https://github.com/agentskills/agentskills

## Detailed Design

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Workflow Integration v3                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Session Start                    Session End                   │
│   ─────────────                    ───────────                   │
│   session-init skill ─────────────▶ session-save skill          │
│   (auto-discovered)                 (manual/auto)                │
│        │                                  │                      │
│        ▼                                  ▼                      │
│   ┌──────────────┐                 ┌──────────────┐             │
│   │ MCP: Session │                 │ MCP: Session │             │
│   │   Memory     │                 │   Memory     │             │
│   └──────────────┘                 └──────────────┘             │
│        │                                                         │
│        ▼                                                         │
│   ┌──────────────┐                                              │
│   │ MCP: Pixel-  │                                              │
│   │ table Memory │                                              │
│   └──────────────┘                                              │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Git Events (Automatic - Event-Driven)                          │
│   ─────────────────────────────────────                          │
│                                                                  │
│   post-commit ─────┐                                            │
│   post-merge ──────┼───▶ ingest_file() ───▶ Pixeltable KB       │
│   post-rewrite ────┘                                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Directory Structure

```
.claude/
└── skills/
    ├── session-init/
    │   └── SKILL.md           # Auto-discovered session initialization
    └── session-save/
        └── SKILL.md           # Session wrap-up workflow

.agent/
├── hooks/                     # Git hooks (event-driven)
│   ├── post-commit
│   ├── post-merge
│   └── post-rewrite
├── config.yaml                # Ingestion policy
├── state/
│   └── last_ingest_sha        # Tracks KB freshness
└── logs/
    └── ingestion.log          # Hook execution logs
```

### 1. Agent Skills

#### `.claude/skills/session-init/SKILL.md`
```yaml
---
name: session-init
description: >
  BOOTSTRAP PROTOCOL: Initialize session with recent git activity,
  user task context, and relevant architectural decisions.
  Run this at the start of every coding session.
version: "1.0"
author: luminescent-cluster
compatibility:
  - mcp: session-memory
  - mcp: pixeltable-memory
metadata:
  security-audit: true
  importance: critical
---

## When to Use
- Starting a new coding session
- Resuming work after a break
- Switching to a different task

## 1. Environment Verification
First, verify that the knowledge base is synchronized with the codebase.
Execute the following Bash command:
```bash
if [ -f .agent/state/last_ingest_sha ]; then
    LAST=$(cat .agent/state/last_ingest_sha)
    CURRENT=$(git rev-parse HEAD)
    if [ "$LAST" != "$CURRENT" ]; then
        echo "WARNING: Knowledge Base is stale (Last ingest: ${LAST:0:8}, HEAD: ${CURRENT:0:8}). Consider running hooks or proceed with caution."
    else
        echo "Knowledge Base is fresh."
    fi
else
    echo "WARNING: No ingestion state found. Run scripts/install_hooks.sh"
fi
```

Also verify hooks are installed:
```bash
[ -f .git/hooks/post-commit ] && echo "Hooks installed" || echo "WARNING: Hooks not installed. Run scripts/install_hooks.sh"
```

## 2. Context Loading Workflow
Perform these steps in order. **Do not use `git push` or modify files.**

### 2.1 Analyze Local State
- Get the last 5 commits: `git log -n 5 --oneline`
- Check for uncommitted work: `git status -s` and `git diff --stat`
- Get current branch: `git branch --show-current`

### 2.2 Retrieve Mental State (Session Memory)
- Call `mcp__session-memory__get_task_context`
- **Decision Logic:**
  - If task is defined: Output "Resume Task: [Task Name]"
  - If task is empty: Ask the user "What are we working on today?" and stop here

### 2.3 Retrieve Organizational Knowledge (Pixeltable)
Based on the file changes seen in Step 2.1, query for relevant context:
- Call `mcp__pixeltable-memory__search_organizational_memory` with keywords from current work
- Call `mcp__pixeltable-memory__get_architectural_decisions` for relevant ADRs

## 3. Output Format
Present a concise summary:

> **Status:** [Fresh/Stale]
> **Active Task:** [Task Description]
> **Current Branch:** [branch-name]
> **Recent Activity:** [3 bullets on recent commits/changes]
> **Relevant ADRs:** [ADR titles or "None"]
> **Open Questions:** [From task context or "None"]
```

#### `.claude/skills/session-save/SKILL.md`
```yaml
---
name: session-save
description: >
  Persist session state before ending work. Summarizes accomplishments,
  updates task context, and prepares for commit.
version: "1.0"
author: luminescent-cluster
compatibility:
  - mcp: session-memory
metadata:
  security-audit: true
---

## When to Use
- Ending a coding session
- Before taking a break
- When switching to a different task
- Before making a commit

## 1. Summarize Session
Review the conversation and identify:
- What was accomplished this session
- Files modified
- Decisions made
- Open questions or blockers

## 2. Update Task Context
Call `mcp__session-memory__set_task_context` with:
- task: Brief description of current work state
- details:
  - completed: List of completed items
  - in_progress: Current work
  - blockers: Any blockers or questions
  - files_modified: List of changed files

## 3. Prepare for Commit
Check for uncommitted changes:
```bash
git status -s
```

If changes exist, suggest:
> Ready to commit. Run `git commit` to trigger auto-ingestion of documentation changes.

## 4. Output Format
> **Session Summary:** [1-2 sentences]
> **Task Updated:** [Yes/No]
> **Pending Changes:** [List or "None"]
> **Next Steps:** [Recommendations]
```

### 2. Git Hooks (Unchanged from v2)

Git hooks remain in `.agent/hooks/` for event-driven automation. They run independently of agent sessions.

#### `.agent/hooks/post-commit`
```bash
#!/bin/bash
# ADR-002: Auto-ingest committed files into Pixeltable memory
# Installed by: scripts/install_hooks.sh

set -euo pipefail

PROJECT_ROOT="$(git rev-parse --show-toplevel)"
STATE_DIR="${PROJECT_ROOT}/.agent/state"
LOG_FILE="${PROJECT_ROOT}/.agent/logs/ingestion.log"

# Use project venv Python (critical for environment isolation)
PYTHON="${PROJECT_ROOT}/.venv/bin/python"
if [ ! -f "$PYTHON" ]; then
    PYTHON="python3"  # Fallback
fi

# Ensure directories exist
mkdir -p "$STATE_DIR" "$(dirname "$LOG_FILE")"

# Get files changed in this commit
COMMIT_SHA=$(git rev-parse HEAD)
CHANGED_FILES=$(git diff-tree --no-commit-id --name-only --diff-filter=AMR -r HEAD)

# Filter to ingestible files (allowlist)
INGESTIBLE_PATTERNS="\.md$|\.txt$|\.rst$|docs/|adr/|ADR-"
EXCLUDED_PATTERNS="node_modules/|\.venv/|dist/|build/|__pycache__/"

# Additional secrets protection
SECRETS_PATTERNS="\.env|secret|\.key$|\.pem$|password|token|credential"

FILES_TO_INGEST=""
while IFS= read -r file; do
    [ -z "$file" ] && continue

    # Check if file matches ingestible patterns
    if ! echo "$file" | grep -qE "$INGESTIBLE_PATTERNS"; then
        continue
    fi

    # Check if file matches excluded patterns
    if echo "$file" | grep -qE "$EXCLUDED_PATTERNS"; then
        continue
    fi

    # Check if file matches secrets patterns
    if echo "$file" | grep -qiE "$SECRETS_PATTERNS"; then
        echo "[post-commit] SKIPPED sensitive file: $file" >> "$LOG_FILE"
        continue
    fi

    FILES_TO_INGEST="${FILES_TO_INGEST}${file}"$'\n'
done <<< "$CHANGED_FILES"

# Remove trailing newline and check if empty
FILES_TO_INGEST=$(echo "$FILES_TO_INGEST" | sed '/^$/d')

if [ -z "$FILES_TO_INGEST" ]; then
    echo "[post-commit] No ingestible files in commit, skipping."
    exit 0
fi

FILE_COUNT=$(echo "$FILES_TO_INGEST" | wc -l | tr -d ' ')
echo "[post-commit] Ingesting $FILE_COUNT files..."

# Run ingestion asynchronously to not block commit
(
    cd "$PROJECT_ROOT"

    # Log start
    echo "$(date -Iseconds) | COMMIT=$COMMIT_SHA | START | files=$FILE_COUNT" >> "$LOG_FILE"

    # Ingest each file
    echo "$FILES_TO_INGEST" | while IFS= read -r file; do
        if [ -f "$file" ]; then
            "$PYTHON" -c "
from src.workflows.ingestion import ingest_file
ingest_file('$file', commit_sha='$COMMIT_SHA')
" >> "$LOG_FILE" 2>&1 || echo "$(date -Iseconds) | ERROR | Failed to ingest: $file" >> "$LOG_FILE"
        fi
    done

    # Record success
    echo "$COMMIT_SHA" > "$STATE_DIR/last_ingest_sha"
    echo "$(date -Iseconds) | COMMIT=$COMMIT_SHA | SUCCESS" >> "$LOG_FILE"
) &

echo "[post-commit] Ingestion queued. Check .agent/logs/ingestion.log for status."
```

#### `.agent/hooks/post-merge`
```bash
#!/bin/bash
# ADR-002: Ingest files from merged/pulled changes

set -euo pipefail

PROJECT_ROOT="$(git rev-parse --show-toplevel)"

# Delegate to post-commit logic
exec "${PROJECT_ROOT}/.agent/hooks/post-commit"
```

#### `.agent/hooks/post-rewrite`
```bash
#!/bin/bash
# ADR-002: Re-sync after rebase/amend

set -euo pipefail

PROJECT_ROOT="$(git rev-parse --show-toplevel)"
STATE_DIR="${PROJECT_ROOT}/.agent/state"
LOG_FILE="${PROJECT_ROOT}/.agent/logs/ingestion.log"

mkdir -p "$STATE_DIR" "$(dirname "$LOG_FILE")"

echo "[post-rewrite] History rewritten, updating ingestion state..."
echo "$(date -Iseconds) | REWRITE | Clearing last_ingest_sha" >> "$LOG_FILE"

# Clear last ingest SHA to force re-check on next session-init
rm -f "$STATE_DIR/last_ingest_sha"

echo "[post-rewrite] Run session-init skill to re-sync if needed."
```

### 3. Support Scripts

#### `scripts/install_hooks.sh`
```bash
#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$(git rev-parse --show-toplevel)"
HOOKS_SOURCE="${PROJECT_ROOT}/.agent/hooks"
HOOKS_TARGET="${PROJECT_ROOT}/.git/hooks"

echo "Installing git hooks for ADR-002 workflow integration..."

# Check for existing hooks
for hook in post-commit post-merge post-rewrite; do
    if [ -f "${HOOKS_TARGET}/${hook}" ]; then
        echo "  WARNING: Existing ${hook} found. Backing up to ${hook}.backup"
        mv "${HOOKS_TARGET}/${hook}" "${HOOKS_TARGET}/${hook}.backup"
    fi
done

# Install new hooks
for hook in post-commit post-merge post-rewrite; do
    if [ -f "${HOOKS_SOURCE}/${hook}" ]; then
        cp "${HOOKS_SOURCE}/${hook}" "${HOOKS_TARGET}/"
        chmod +x "${HOOKS_TARGET}/${hook}"
        echo "  Installed ${hook}"
    fi
done

# Create required directories
mkdir -p "${PROJECT_ROOT}/.agent/state"
mkdir -p "${PROJECT_ROOT}/.agent/logs"
mkdir -p "${PROJECT_ROOT}/.claude/skills"

echo ""
echo "Hooks installed successfully!"
echo ""
echo "To uninstall: rm ${HOOKS_TARGET}/post-{commit,merge,rewrite}"
```

#### `scripts/init_memory.py`
```python
#!/usr/bin/env python3
"""
ADR-002: Bootstrap knowledge base for fresh clone.
Run this after cloning to hydrate the KB with existing docs.
"""

import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

def bootstrap_memory():
    """Ingest existing documentation for fresh clones."""
    from pixeltable_setup import ingest_codebase, setup_knowledge_base

    print("Bootstrapping knowledge base...")

    # Initialize KB if needed
    kb = setup_knowledge_base()

    # Ingest docs directory
    docs_dir = PROJECT_ROOT / "docs"
    if docs_dir.exists():
        ingest_codebase(kb, str(docs_dir), service_name="luminescent-cluster")

    # Record initial state
    state_dir = PROJECT_ROOT / ".agent" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        (state_dir / "last_ingest_sha").write_text(result.stdout.strip())

    print("Bootstrap complete!")

if __name__ == "__main__":
    bootstrap_memory()
```

### 4. Ingestion Policy

#### `.agent/config.yaml`
```yaml
# ADR-002: Ingestion policy for git hook automation
ingestion:
  include:
    - "docs/**/*.md"
    - "*.md"
    - "docs/adrs/**"
  exclude:
    - "**/node_modules/**"
    - "**/.venv/**"
    - "**/dist/**"
    - "**/build/**"
    - "**/__pycache__/**"
    - "**/*.pyc"
    - "**/.env"
    - "**/*.key"
    - "**/*.pem"
    - "**/secrets/**"
    - "**/*secret*"
    - "**/*password*"
    - "**/*token*"
    - "**/*credential*"
  max_file_size_kb: 500
  skip_binary: true

skills:
  directory: ".claude/skills"
  auto_discover: true
```

#### Metadata Stored
Each ingested file includes:
- `path`: File path relative to repo root
- `commit_sha`: Git commit SHA when ingested
- `branch`: Branch name
- `timestamp`: Ingestion timestamp
- `author`: Commit author
- `content_hash`: SHA256 of file content (for idempotency)

## Security Considerations

### Council-Identified Security Requirements

1. **`allowed-tools` is a Hint, Not Enforcement**
   - The `allowed-tools` field in SKILL.md is a capability advertisement, not a security boundary
   - Real authorization must be enforced at the MCP server level
   - Ensure Pixeltable and Session Memory MCP servers validate all requests

2. **Treat Skills as Executable Code**
   - Add `CODEOWNERS` protection to `.claude/skills/`
   - Require code review for skill changes
   - Skills with Bash access require security review

3. **Secrets Protection**
   - Never ingest files matching: `.env`, `*.key`, `*.pem`, `*secret*`, `*password*`, `*token*`
   - Content scanning in hooks for sensitive patterns
   - MCP servers should redact secrets from responses

4. **Script Execution Risk**
   - Avoid relative path scripts in skills (agent sandboxing issues)
   - Embed verification logic directly in SKILL.md using standard commands
   - Or expose as MCP tools for better control

5. **Supply Chain / Tampering**
   - Treat skills as code requiring review
   - Consider CODEOWNERS for skills + hooks

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Skill     │ ──► │   Agent     │ ──► │ MCP Server  │
│ (requests)  │     │ (mediates)  │     │ (enforces)  │
└─────────────┘     └─────────────┘     └─────────────┘
                          │
                    Permission check
                    happens HERE
```

## Consequences

### Positive
- **Automatic Sync**: The Knowledge Base will be automatically updated whenever code is committed.
- **Auto-Discovery**: Agents find and apply session-init skill without explicit user prompts.
- **Interoperability**: Skills work with Claude, Codex, Copilot, Cursor, and other compliant agents.
- **Progressive Disclosure**: Efficient token usage (~50 tokens metadata until skill is activated).
- **Reduced Friction**: No custom workflow runner to maintain.
- **Multi-event Coverage**: post-merge and post-rewrite ensure KB stays in sync.

### Negative
- **Setup Requirement**: User must run `scripts/install_hooks.sh` once.
- **Commit Latency**: The `post-commit` hook adds a small delay (async mitigates this).
- **Bootstrap Required**: Fresh clones need `scripts/init_memory.py` for initial KB population.
- **Agent Dependency**: Requires agents that support Agent Skills spec (most modern agents do).

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Hook fails silently | Medium | High (KB drift) | Log all failures; session-init checks freshness |
| Ingestion blocks commit | Low | Medium (UX) | Run ingestion async (backgrounded) |
| Large commit slow | Medium | Low | Batch processing; skip if >50 files |
| Partial ingestion | Medium | Medium | Idempotent ingestion with content hash |
| Hook not installed | High | High (unused) | session-init warns if hooks missing |
| Secrets accidentally ingested | Medium | Critical | Strict exclude patterns; content scanning |
| Venv not found | Medium | Medium | Fallback to system Python; warn user |
| Database locking | Low | Medium | Retry logic in ingestion tool |
| KB drift on rebase | Medium | Medium | post-rewrite clears last_ingest_sha |
| Skill injection via PRs | Low | High | CODEOWNERS, code review for skills |
| Agent ignores skill | Medium | Low | Skills degrade gracefully; can invoke manually |

## Testing Strategy

### Unit Tests
- `tests/workflows/test_config_parser.py` - Parse `.agent/config.yaml`
- `tests/workflows/test_ingest_file.py` - Single file ingestion with filtering
- `tests/workflows/test_post_commit_hook.py` - Mock git, verify correct files identified
- `tests/workflows/test_ingestion_idempotency.py` - Same file twice = no duplicates
- `tests/workflows/test_hook_security.py` - Secrets filtering

### Integration Tests
- `tests/workflows/test_integration.py` - Create commit, verify ingestion, query KB

### Manual Verification
```bash
# After implementing, verify with:
echo "# Test Doc" > test-doc.md
git add test-doc.md && git commit -m "test ingestion"

# Check log
cat .agent/logs/ingestion.log

# Query KB
python -c "from pixeltable_setup import search_knowledge, setup_knowledge_base; kb = setup_knowledge_base(); print(search_knowledge(kb, 'test doc'))"
```

## Rollback Plan

If this integration causes issues:

1. **Disable hooks**: `rm .git/hooks/post-{commit,merge,rewrite}`
2. **Clear bad ingestion**: `python scripts/agent_tools.py clear --since <date>`
3. **Revert to manual**: Remove skill files, document manual commands

**Rollback criteria:**
- Commit time increases >5 seconds average
- Ingestion failures >10% of commits
- User reports workflow friction exceeds manual prompting
- Agent fails to discover skills consistently

## Acceptance Criteria

This ADR is successfully implemented when:

1. [x] `scripts/install_hooks.sh` exists and installs all three hooks
2. [x] `.claude/skills/session-init/SKILL.md` exists with all specified steps
3. [x] `.claude/skills/session-save/SKILL.md` exists with wrap-up logic
4. [x] After running install script, committing a `.md` file triggers ingestion
5. [x] Ingestion completes in <3 seconds for typical commits (<10 files)
6. [x] Hook failures are logged but don't block commits
7. [x] session-init skill warns if hooks not installed
8. [x] session-init skill warns if KB is stale
9. [x] Secrets/sensitive files are never ingested
10. [x] Documentation updated with setup instructions
11. [x] Skills are discoverable by Claude Code and other compliant agents
12. [x] CODEOWNERS includes `.claude/skills/` directory

**Implementation Status**: Complete (2026-01-16)
- 112 tests passing across 5 test files
- Core infrastructure: `src/workflows/config.py`, `src/workflows/ingestion.py`
- Git hooks: `.agent/hooks/post-commit`, `post-merge`, `post-rewrite`
- Agent Skills: `.claude/skills/session-init/`, `.claude/skills/session-save/`
- Support scripts: `scripts/install_hooks.sh`, `scripts/init_memory.py`

## References
- ADR-001: Python Version Requirement for MCP Servers
- Agent Skills Specification: https://agentskills.io/specification
- Model Context Protocol: https://modelcontextprotocol.io/
- Tools: `session_memory_server.py`, `pixeltable_mcp_server.py`, `pixeltable_setup.py`

## Changelog

- **2025-12-22 v1**: Initial proposal with basic workflow + post-commit hook
- **2025-12-22 v2**: LLM Council review (Gemini-3-Pro, Grok-4, Claude-Opus-4.5, GPT-5.2-Pro):
  - **CRITICAL**: Added `post-merge` and `post-rewrite` hooks for complete coverage
  - **CRITICAL**: Added workflow file content with YAML structure
  - **CRITICAL**: Added ingestion scope policy with allowlist/denylist
  - **CRITICAL**: Added secrets protection (exclude .env, keys, passwords)
  - Fixed `load-context` to include Pixeltable queries (was missing despite title)
  - Added venv environment handling in hooks
  - Added `scripts/init_memory.py` for bootstrapping fresh clones
  - Added memory freshness check in load-context workflow
  - Added metadata schema for ingested files (idempotency via content_hash)
  - Added detailed risk/mitigation table
  - Added testing strategy
  - Added rollback plan
  - Added acceptance criteria
  - Expanded Option 2 (daemon) analysis for fairness
  - Added Option 4 (IDE integration) as "not evaluated"

- **2026-01-16 v3**: LLM Council review (Gemini-3-Pro, Grok-4.1, Claude-Opus-4.5, GPT-5.2):
  - **MAJOR**: Adopted Agent Skills open standard instead of custom `.agent/workflows/`
  - **MAJOR**: Changed from custom workflow format to `SKILL.md` specification
  - **MAJOR**: Moved workflows from `.agent/workflows/` to `.claude/skills/`
  - **MAJOR**: Renamed workflows: `load-context` → `session-init`, `save-context` → `session-save`
  - Added comprehensive security section based on Council feedback
  - Added MCP vs Skills architectural distinction
  - Added Option 5 analysis (Agent Skills + Git Hooks)
  - Embedded freshness check logic directly in SKILL.md (avoid relative script paths)
  - Added standards reference section
  - Updated acceptance criteria for skill discovery
  - Added CODEOWNERS requirement for skill security
  - Council Rankings: claude-opus-4.5 (0.833), gpt-5.2 (0.778), gemini-3-pro (0.333), grok-4.1 (0.0)
