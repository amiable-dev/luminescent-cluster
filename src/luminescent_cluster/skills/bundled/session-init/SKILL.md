---
name: session-init
description: >
  BOOTSTRAP PROTOCOL: Initialize session with recent git activity,
  user task context, and relevant architectural decisions.
  Run this at the start of every coding session.
license: Apache-2.0
compatibility: "luminescent-cluster >= 0.4.0"
metadata:
  category: session-management
  domain: development
  author: amiable-dev
  repository: https://github.com/amiable-dev/luminescent-cluster
  security-audit: true
  importance: critical
allowed-tools: "Bash Read mcp:session-memory mcp:pixeltable-memory"
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
