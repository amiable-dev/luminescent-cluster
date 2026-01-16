# Automated Context Loading: Teaching AI Agents to Remember

**The friction of "load context" and "save context" prompts is over. Here's how we automated memory management with Agent Skills and Git Hooks.**

---

Every coding session with an AI agent starts the same way: "Load the recent commits," "What were we working on?", "Check the knowledge base for relevant ADRs." And every session ends with: "Save the task context," "Remember these decisions," "Update the KB with these changes."

This manual memory management is tedious and error-prone. Forget to load context, and the agent starts from scratch. Forget to save, and tomorrow's session loses continuity. Forget to ingest changes, and the knowledge base drifts from reality.

ADR-002 solves this with two complementary mechanisms: **Agent Skills** for session workflows and **Git Hooks** for automatic synchronization.

## The Problem: Manual Memory Management

```
┌─────────────────────────────────────────────────────────────────┐
│                    Manual Context Flow                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Session Start                         Session End              │
│   ─────────────                         ───────────              │
│   User: "Load context..."               User: "Save context..."  │
│        │                                      │                  │
│        ▼                                      ▼                  │
│   Agent loads                           Agent saves              │
│   (if user remembers)                   (if user remembers)      │
│                                                                  │
│   After Commit                                                   │
│   ────────────                                                   │
│   Nothing happens                                                │
│   (KB drifts from codebase)                                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

The failure modes are predictable:
- **Stale context**: Agent doesn't know about yesterday's refactor
- **Lost continuity**: Task state evaporates between sessions
- **KB drift**: Documentation changes never reach the knowledge base
- **Cognitive load**: User becomes a memory manager instead of a programmer

## The Solution: Skills + Hooks

```
┌─────────────────────────────────────────────────────────────────┐
│                    Automated Context Flow                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Session Start                         Session End              │
│   ─────────────                         ───────────              │
│   session-init skill                    session-save skill       │
│   (auto-discovered)                     (manual or auto)         │
│        │                                      │                  │
│        ▼                                      ▼                  │
│   ┌──────────────┐                     ┌──────────────┐         │
│   │ MCP: Session │                     │ MCP: Session │         │
│   │   Memory     │                     │   Memory     │         │
│   └──────────────┘                     └──────────────┘         │
│        │                                                         │
│        ▼                                                         │
│   ┌──────────────┐                                              │
│   │ MCP: Pixel-  │◄──────────────────────────────────┐          │
│   │ table Memory │                                    │          │
│   └──────────────┘                                    │          │
│                                                       │          │
│   Git Events (Automatic)                              │          │
│   ──────────────────────                              │          │
│                                                       │          │
│   post-commit ─────┐                                  │          │
│   post-merge ──────┼──── ingest_file() ──────────────┘          │
│   post-rewrite ────┘                                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Agent Skills: The Open Standard

Agent Skills is an open standard (released December 2025) for packaging AI agent capabilities. Think of it as a portable playbook that any compliant agent can discover and execute.

### Why Skills, Not Custom Workflows?

| Approach | Portability | Discovery | Token Efficiency |
|----------|-------------|-----------|------------------|
| Manual prompts | None | User-dependent | High (repeated) |
| Custom workflows | Project-only | Custom runner | Variable |
| **Agent Skills** | Cross-agent | Auto-discovery | ~50 tokens metadata |

Skills are supported by Claude, OpenAI Codex, GitHub Copilot, Cursor, VS Code Insiders, and Goose.

### session-init: Bootstrap Every Session

The `session-init` skill runs at the start of every coding session:

```yaml
---
name: session-init
description: >
  BOOTSTRAP PROTOCOL: Initialize session with recent git activity,
  user task context, and relevant architectural decisions.
version: "1.0"
compatibility:
  - mcp: session-memory
  - mcp: pixeltable-memory
---
```

What it does:
1. **Verify KB freshness** - Compare `last_ingest_sha` with HEAD
2. **Check hook installation** - Warn if git hooks are missing
3. **Load git state** - Recent commits, uncommitted changes, current branch
4. **Retrieve task context** - What were we working on?
5. **Query organizational knowledge** - Relevant ADRs and decisions

Output format:
```
> **Status:** Fresh
> **Active Task:** Implementing user authentication
> **Current Branch:** feature/auth
> **Recent Activity:**
>   - Added login endpoint
>   - Updated session middleware
>   - Fixed CORS configuration
> **Relevant ADRs:** ADR-007 (Authentication Strategy)
```

### session-save: Persist Before Leaving

The `session-save` skill captures state before ending work:

1. **Summarize accomplishments** - What was done this session
2. **Update task context** - Current state, blockers, next steps
3. **Prepare for commit** - Check for uncommitted changes

```python
# What gets saved to Session Memory
{
    "task": "Implementing user authentication",
    "details": {
        "completed": ["login endpoint", "session middleware"],
        "in_progress": "CORS configuration",
        "blockers": ["Need OAuth provider decision"],
        "files_modified": ["src/api/auth.py", "src/middleware/session.py"]
    }
}
```

## Git Hooks: Event-Driven Ingestion

Skills handle session workflows. Git hooks handle codebase synchronization.

### Three Hooks, Three Events

| Hook | Trigger | Action |
|------|---------|--------|
| `post-commit` | After every commit | Ingest changed docs/ADRs |
| `post-merge` | After pull/merge | Sync KB with upstream |
| `post-rewrite` | After rebase/amend | Clear stale ingestion state |

### What Gets Ingested

The hook filters commits to find ingestible files:

```bash
# Allowlist patterns
INGESTIBLE_PATTERNS="\.md$|\.txt$|\.rst$|docs/|adr/|ADR-"

# Denylist patterns
EXCLUDED_PATTERNS="node_modules/|\.venv/|dist/|build/|__pycache__/"

# Secrets protection
SECRETS_PATTERNS="\.env|secret|\.key$|\.pem$|password|token|credential"
```

Each ingested file includes metadata:
- `path`: Relative path in repo
- `commit_sha`: Git commit SHA
- `branch`: Branch name
- `content_hash`: SHA256 for idempotency
- `ingested_at`: Timestamp

### Non-Blocking Design

Hooks run ingestion asynchronously to avoid slowing commits:

```bash
# Run in background
(
    # ... ingestion logic ...
    echo "$COMMIT_SHA" > "$STATE_DIR/last_ingest_sha"
) &

echo "[post-commit] Ingestion queued."
```

Check status in `.agent/logs/ingestion.log`.

## Security: 10 Rounds of Council Review

The ingestion pipeline underwent 10 rounds of LLM Council security review. Here's what we hardened:

### Path Security

```python
# Path traversal prevention
canonical_path = file_path.resolve()
relative_path = canonical_path.relative_to(project_root)

# Defense in depth
if ".." in relative_path:
    return {"success": False, "reason": "Rejected path with traversal"}

if "\x00" in relative_path:
    return {"success": False, "reason": "Rejected path with null bytes"}

if relative_path.startswith("-"):
    return {"success": False, "reason": "Rejected hyphen prefix (git injection)"}
```

### Provenance Integrity

We read from the git object database, not the working tree:

```python
# Read exactly what was committed
result = subprocess.run(
    ["git", "show", f"{commit_sha}:{relative_path}"],
    capture_output=True,
    text=False,  # Binary mode
    timeout=10,
)
content = result.stdout.decode("utf-8", errors="replace")
```

This prevents race conditions where files are modified between commit and ingestion.

### DoS Prevention

```python
# Check blob size BEFORE reading content
blob_size = _get_blob_size(relative_path, commit_sha, project_root)
if blob_size is None:
    return {"success": False, "reason": "Cannot determine blob size"}

if blob_size / 1024 > config.max_file_size_kb:
    return {"success": False, "reason": f"File too large"}

# Verify it's a file, not a directory
if not _is_blob(relative_path, commit_sha, project_root):
    return {"success": False, "reason": "Not a blob (file)"}
```

### Config Validation

```python
# Hard limits cannot be overridden by config
MAX_FILE_SIZE_KB_HARD_LIMIT = 10240  # 10MB absolute max

# Clamp user config values
max_file_size_kb = min(int(raw_max_size), MAX_FILE_SIZE_KB_HARD_LIMIT)
```

### Pattern Matching (No ReDoS)

We use fnmatch instead of regex for user-configurable patterns:

```python
# Safe pattern matching without regex
def _matches_pattern(file_path: str, pattern: str) -> bool:
    if "**" in pattern:
        # Component-based matching (no regex)
        return _match_glob_components(file_path, pattern)
    return fnmatch(file_path, pattern)
```

## Configuration

All behavior is controlled via `.agent/config.yaml`:

```yaml
ingestion:
  include:
    - "docs/**/*.md"
    - "*.md"
    - "docs/adrs/**"
  exclude:
    - "**/node_modules/**"
    - "**/.venv/**"
    - "**/secrets/**"
    - "**/*secret*"
    - "**/*password*"
  max_file_size_kb: 500
  skip_binary: true

skills:
  directory: ".claude/skills"
  auto_discover: true
```

## Getting Started

### 1. Install Hooks

```bash
./scripts/install_hooks.sh
```

This installs `post-commit`, `post-merge`, and `post-rewrite` hooks.

### 2. Bootstrap KB (Fresh Clone)

```bash
python scripts/init_memory.py
```

This ingests existing documentation for the first time.

### 3. Verify Installation

```bash
# Check hooks
ls -la .git/hooks/post-*

# Check skill discovery
ls -la .claude/skills/

# Make a test commit
echo "# Test" >> test.md
git add test.md && git commit -m "test ingestion"
cat .agent/logs/ingestion.log
```

### 4. Start a Session

The agent will auto-discover `session-init` and load context. Or invoke manually:

```
/session-init
```

## When It Works

After setup, the flow becomes:

1. **Start session** → Agent auto-runs `session-init` → Context loaded
2. **Work on code** → Normal development
3. **Commit changes** → Hook auto-ingests docs → KB stays fresh
4. **End session** → Run `session-save` → State persisted
5. **Next session** → Agent knows where you left off

No more "load context" prompts. No more KB drift. No more lost continuity.

## Troubleshooting

### KB is Stale

```bash
# Check last ingestion
cat .agent/state/last_ingest_sha
git rev-parse HEAD

# Force re-ingest
rm .agent/state/last_ingest_sha
python scripts/init_memory.py --force
```

### Hooks Not Running

```bash
# Verify hooks are executable
chmod +x .git/hooks/post-*

# Check for errors
cat .agent/logs/ingestion.log
```

### Skill Not Discovered

Ensure the agent supports Agent Skills spec. Check:
- `.claude/skills/` directory exists
- `SKILL.md` files have valid YAML frontmatter
- Agent has MCP servers configured (session-memory, pixeltable-memory)

## What's Next

ADR-002 is complete, but future enhancements could include:
- **IDE integration**: VS Code extension for skill invocation
- **Real-time sync**: File watcher for uncommitted changes
- **Skill marketplace**: Community-contributed skills

---

*Automated context loading is part of ADR-002 Workflow Integration. See the [full ADR](../adrs/ADR-002-workflow-integration.md) for implementation details and security considerations.*
