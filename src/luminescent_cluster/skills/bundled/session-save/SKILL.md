---
name: session-save
description: >
  Persist session state before ending work. Summarizes accomplishments,
  updates task context, and prepares for commit.
license: Apache-2.0
compatibility: "luminescent-cluster >= 0.4.0"
metadata:
  category: session-management
  domain: development
  author: amiable-dev
  repository: https://github.com/amiable-dev/luminescent-cluster
  security-audit: true
allowed-tools: "Bash Read mcp:session-memory"
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

- **task**: Brief description of current work state
- **details**:
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
