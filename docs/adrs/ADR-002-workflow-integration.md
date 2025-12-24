# ADR-002: Workflow Integration for Session and Pixeltable Memory

## Status
**Proposed v2** (reviewed by LLM Council 2025-12-22)

## Date
2025-12-22

## Deciders
- Christopher Joseph
- Antigravity
- LLM Council (Gemini-3-Pro, Grok-4, Claude-Opus-4.5, GPT-5.2-Pro)

## Context

### The Problem
The current integration of Session Memory and Pixeltable Memory requires the user to manually remind the LLM to "load context" before starting work and "save/update context" after completing work. This friction leads to:
- Inconsistent context usage (forgetting to load context).
- Outdated knowledge base (forgetting to ingest changes).
- Increased cognitive load on the user to manage the agent's state.

### Current vs Proposed Workflow

| Action | Current (Manual) | Proposed (Automated) |
|--------|------------------|---------------------|
| Session Start | User prompts: "Load recent commits and task context" | Run `load-context` workflow |
| During Work | User occasionally asks for context | Context pre-loaded |
| Session End | User prompts: "Save task context, ingest changes" | Run `save-context` workflow |
| After Commit | Nothing (KB drifts) | Git hooks auto-ingest |

### The Opportunity
We have two mechanisms available to automate this:
1. **Antigravity Workflows**: Structured, reproducible sequences of actions defined in `.agent/workflows`.
2. **Git Hooks**: Scripts that run automatically on git events (e.g., `post-commit`).

By combining these, we can ensure context is loaded systematically and updated automatically.

## Decision Drivers
- **Reduce Friction**: Standardize context operations to a single workflow command.
- **Consistency**: Ensure memory tools are used in every session.
- **Freshness**: Keep the long-term memory (Pixeltable) in sync with the codebase automatically.
- **Simplicity**: Avoid complex background daemons or heavy infrastructure.

## Scope and Non-Goals

**In Scope:**
- Committed text artifacts in selected directories
- Session context loading/saving via workflows
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

### Option 3: Workflow + Git Hook Integration (Recommended)
Define explicit workflows for "Load Context" and "Save Context" and use git hooks for auto-ingestion.
**Pros**:
- **Workflows** provide a standard "entry point" for the agent.
- **Git Hooks** capture the natural "save point" of a developer's workflow (the commit).
- Low complexity and resource usage.
**Cons**:
- Requires user to run the specific workflow or commit changes.
- Misses updates from rebase/amend unless additional hooks are added.

### Option 4: IDE Integration (Not Evaluated)
Use VS Code tasks, JetBrains run configurations, or similar to trigger workflows.
**Why not evaluated**: Adds IDE dependency; workflows should be IDE-agnostic.

## Decision

**Adopt Option 3: Workflow + Git Hook Integration.**

## Detailed Design

### 1. Workflow Definitions

#### `.agent/workflows/load-context.md`
```yaml
name: Load Session Context
description: Initialize agent with relevant context at session start
trigger: manual  # Future: on_session_start

steps:
  - name: Verify Hook Installation
    action: check
    condition: file_exists(".git/hooks/post-commit")
    on_failure: "warn: Git hooks not installed. Run scripts/install_hooks.sh"

  - name: Get Recent Activity
    tool: session_memory.get_recent_commits
    params:
      limit: 10

  - name: Load Task Context
    tool: session_memory.get_task_context

  - name: Check Working State
    tool: session_memory.get_current_diff

  - name: Query Relevant Knowledge
    tool: pixeltable_memory.search_organizational_memory
    params:
      query: "{{current_task_description}}"
      limit: 5

  - name: Check Memory Freshness
    action: compare
    sources: [last_ingest_sha, HEAD]
    on_mismatch: "warn: Knowledge base may be out of date. Last ingested: {{last_ingest_sha}}"

output: |
  Summarize loaded context and identify:
  1. What was I working on?
  2. What's the current state?
  3. What are the open questions/blockers?
```

#### `.agent/workflows/save-context.md`
```yaml
name: Save Session Context
description: Persist session state and prepare for commit
trigger: manual

steps:
  - name: Summarize Session
    action: prompt
    content: "Summarize what was accomplished this session"

  - name: Update Task Context
    tool: session_memory.set_task_context
    params:
      task: "{{session_summary}}"
      details:
        completed_at: "{{timestamp}}"
        files_modified: "{{modified_files}}"

  - name: Identify New Documents
    action: find_files
    params:
      patterns: ["*.md", "docs/**"]
      modified_since: "session_start"

post_action: |
  Ready to commit. Run `git commit` to trigger auto-ingestion.
  Or run `git add -A && git commit -m "your message"` to commit all changes.
```

### 2. Git Automation

#### Git Hooks Required

| Hook | Trigger | Purpose |
|------|---------|---------|
| `post-commit` | After local commit | Ingest changed files |
| `post-merge` | After merge/pull | Ingest incoming changes |
| `post-rewrite` | After rebase/amend | Re-sync rewritten history |

#### `.agent/hooks/post-commit`
```bash
#!/bin/bash
# ADR-002: Auto-ingest committed files into Pixeltable memory
# Installed by: scripts/install_hooks.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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

FILES_TO_INGEST=$(echo "$CHANGED_FILES" | \
    grep -E "$INGESTIBLE_PATTERNS" | \
    grep -vE "$EXCLUDED_PATTERNS" || true)

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
    echo "$FILES_TO_INGEST" | while read -r file; do
        if [ -f "$file" ]; then
            "$PYTHON" -c "
from pixeltable_setup import ingest_file
ingest_file('$file', commit_sha='$COMMIT_SHA')
" >> "$LOG_FILE" 2>&1 || true
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

echo "[post-rewrite] History rewritten, updating ingestion state..."
echo "$(date -Iseconds) | REWRITE | Clearing last_ingest_sha" >> "$LOG_FILE"

# Clear last ingest SHA to force re-check on next load-context
rm -f "$STATE_DIR/last_ingest_sha"

echo "[post-rewrite] Run 'load-context' workflow to re-sync if needed."
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
    from pixeltable_setup import ingest_codebase

    print("Bootstrapping knowledge base...")

    # Ingest docs directory
    docs_dir = PROJECT_ROOT / "docs"
    if docs_dir.exists():
        ingest_codebase(str(docs_dir), service_name="luminescent-cluster")

    # Ingest ADRs
    adr_dir = PROJECT_ROOT / "docs" / "adrs"
    if adr_dir.exists():
        for adr in adr_dir.glob("ADR-*.md"):
            print(f"  Ingesting {adr.name}")
            # Use existing ingest function

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

#### Default Allowlist
```yaml
# .agent/config.yaml
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
  max_file_size_kb: 500
  skip_binary: true
```

#### Metadata Stored
Each ingested file includes:
- `path`: File path relative to repo root
- `commit_sha`: Git commit SHA when ingested
- `branch`: Branch name
- `timestamp`: Ingestion timestamp
- `author`: Commit author
- `content_hash`: SHA256 of file content (for idempotency)

## Consequences

### Positive
- **Automatic Sync**: The Knowledge Base will be automatically updated whenever code is committed.
- **Standardized Context**: The agent will consistently start with the right information.
- **Reduced Friction**: User only needs to run one workflow command per session.
- **Multi-event Coverage**: post-merge and post-rewrite ensure KB stays in sync.

### Negative
- **Setup Requirement**: User must run `scripts/install_hooks.sh` once.
- **Commit Latency**: The `post-commit` hook adds a small delay (async mitigates this).
- **Bootstrap Required**: Fresh clones need `scripts/init_memory.py` for initial KB population.

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Hook fails silently | Medium | High (KB drift) | Log all failures; `load-context` checks freshness |
| Ingestion blocks commit | Low | Medium (UX) | Run ingestion async (backgrounded) |
| Large commit slow | Medium | Low | Batch processing; skip if >50 files |
| Partial ingestion | Medium | Medium | Idempotent ingestion with content hash |
| Hook not installed | High | High (unused) | `load-context` warns if hooks missing |
| Secrets accidentally ingested | Medium | Critical | Strict exclude patterns; skip `.env`, keys |
| Venv not found | Medium | Medium | Fallback to system Python; warn user |
| Database locking | Low | Medium | Retry logic in ingestion tool |
| KB drift on rebase | Medium | Medium | `post-rewrite` clears last_ingest_sha |

### Specific Mitigations

**Secrets Protection:**
```bash
# In hook, additional safety check
if echo "$file" | grep -qE '\.env|secret|key|password|token'; then
    echo "[post-commit] SKIPPED sensitive file: $file" >> "$LOG_FILE"
    continue
fi
```

**Memory Freshness Check (in load-context):**
```yaml
- name: Check Memory Freshness
  action: script
  code: |
    last_sha = read_file(".agent/state/last_ingest_sha")
    head_sha = git_rev_parse("HEAD")
    if last_sha != head_sha:
      warn(f"KB may be stale. Last ingested: {last_sha[:8]}, HEAD: {head_sha[:8]}")
      suggest("Run: git commit --allow-empty -m 'sync' to trigger re-ingestion")
```

## Testing Strategy

### Unit Tests
- `tests/test_post_commit_hook.py` - Mock git, verify correct files identified
- `tests/test_ingestion_idempotency.py` - Same file twice = no duplicates

### Integration Tests
- `tests/test_full_workflow.py` - Create commit, verify ingestion, query KB

### Manual Verification
```bash
# After implementing, verify with:
echo "# Test Doc" > test-doc.md
git add test-doc.md && git commit -m "test ingestion"

# Check log
cat .agent/logs/ingestion.log

# Query KB
python -c "from pixeltable_setup import search_knowledge; print(search_knowledge('test doc'))"
```

## Rollback Plan

If this integration causes issues:

1. **Disable hooks**: `rm .git/hooks/post-{commit,merge,rewrite}`
2. **Clear bad ingestion**: `python scripts/agent_tools.py clear --since <date>`
3. **Revert to manual**: Remove workflow files, document manual commands

**Rollback criteria:**
- Commit time increases >5 seconds average
- Ingestion failures >10% of commits
- User reports workflow friction exceeds manual prompting

## Acceptance Criteria

This ADR is successfully implemented when:

1. [ ] `scripts/install_hooks.sh` exists and installs all three hooks
2. [ ] `.agent/workflows/load-context.md` exists with all specified tool calls
3. [ ] `.agent/workflows/save-context.md` exists with wrap-up logic
4. [ ] After running install script, committing a `.md` file triggers ingestion
5. [ ] Ingestion completes in <3 seconds for typical commits (<10 files)
6. [ ] Hook failures are logged but don't block commits
7. [ ] `load-context` workflow warns if hooks not installed
8. [ ] `load-context` workflow warns if KB is stale
9. [ ] Secrets/sensitive files are never ingested
10. [ ] Documentation updated with setup instructions

## References
- ADR-001: Python Version Requirement for MCP Servers
- Tools: `session_memory_server.py`, `pixeltable_mcp_server.py`, `pixeltable_setup.py`

## Changelog
- **2025-12-22 v1**: Initial proposal with basic workflow + post-commit hook
- **2025-12-22 v2**: LLM Council review (Gemini-3-Pro, Grok-4, Claude-Opus-4.5, GPT-5.2-Pro):
  - **CRITICAL**: Added `post-merge` and `post-rewrite` hooks for complete coverage
  - **CRITICAL**: Added workflow file content with YAML structure
  - **CRITICAL**: Added ingestion scope policy with allowlist/denylist
  - **CRITICAL**: Added secrets protection (exclude .env, keys, passwords)
  - Fixed `load-context` to include Pixeltable queries (was missing despite title)
  - Added venv environment handling in hooks (fcntl vs global shell issue)
  - Added `scripts/init_memory.py` for bootstrapping fresh clones
  - Added memory freshness check in load-context workflow
  - Added metadata schema for ingested files (idempotency via content_hash)
  - Added detailed risk/mitigation table
  - Added testing strategy
  - Added rollback plan
  - Added acceptance criteria
  - Expanded Option 2 (daemon) analysis for fairness
  - Added Option 4 (IDE integration) as "not evaluated"
