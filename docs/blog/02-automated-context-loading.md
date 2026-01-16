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

## Prerequisites: MCP Servers

This system requires two MCP (Model Context Protocol) servers:

**Session Memory MCP** (`session-memory`): Short-term memory for task context, recent activity, and session state. Think of it as the agent's working memory—what you're currently doing.

**Pixeltable Memory MCP** (`pixeltable-memory`): Long-term organizational knowledge base powered by [Pixeltable](https://pixeltable.com). Stores ADRs, documentation, incident history, and code patterns. This is where ingested content goes.

Both are included in the Luminescent Cluster repository. See the [MCP Server setup guide](../operations/mcp-setup.md) for installation.

## Agent Skills: A Portable Standard

Agent Skills is a format for packaging AI agent capabilities as discoverable markdown files. Any agent that supports the format can auto-discover skills in `.claude/skills/` directories.

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

# Secrets protection (filename patterns)
SECRETS_PATTERNS="\.env|secret|\.key$|\.pem$|password|token|credential"
```

**Note:** Filename-based filtering catches obvious secrets but isn't sufficient alone. The ingestion pipeline also performs content scanning for high-entropy strings (potential API keys) and common secret patterns. See the [security deep dive](./08-security-deep-dive.md) for the full detection strategy.

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
# Layer 1: Check raw input BEFORE resolution (catches obvious attempts)
if ".." in str(file_path) or "\x00" in str(file_path):
    return {"success": False, "reason": "Rejected suspicious path characters"}

# Layer 2: Resolve to canonical path
canonical_path = file_path.resolve()

# Layer 3: Verify result is under project root (the authoritative check)
try:
    relative_path = canonical_path.relative_to(project_root.resolve())
except ValueError:
    return {"success": False, "reason": "Path escapes project boundary"}

# Layer 4: Prevent git argument injection
if str(relative_path).startswith("-"):
    return {"success": False, "reason": "Rejected hyphen prefix (git injection)"}
```

**Why layered checks?** The `relative_to()` check is authoritative, but checking raw input first provides defense in depth and clearer audit logs for attack attempts.

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

## Access Control

**Who can read memory?** In single-user mode (self-hosted), the MCP servers run locally and are only accessible to processes on your machine. There's no network exposure.

**Who can write memory?** Only the git hooks and MCP server tools can write. The hooks run in your shell context with your git credentials. The MCP servers validate that writes come from authorized MCP clients.

**Multi-tenant deployments** use the cloud tier, which adds authentication, tenant isolation, and audit logging. See [Memory-as-a-Service](./01-memory-as-a-service.md) for the trust model.

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

**Platform support:** The shell scripts target Unix-like systems (Linux, macOS). Windows users can run them via WSL or Git Bash, or manually copy the hook files to `.git/hooks/`.

### 1. Install Hooks

```bash
./scripts/install_hooks.sh
```

This installs `post-commit`, `post-merge`, and `post-rewrite` hooks. The script backs up any existing hooks before replacement.

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

## Repository

All scripts, hooks, and skills referenced in this post are in the [Luminescent Cluster repository](https://github.com/amiable-dev/luminescent-cluster):

- **Hooks**: `.agent/hooks/post-commit`, `post-merge`, `post-rewrite`
- **Skills**: `.claude/skills/session-init/`, `.claude/skills/session-save/`
- **Scripts**: `scripts/install_hooks.sh`, `scripts/init_memory.py`
- **Config**: `.agent/config.yaml`
- **Source**: `src/workflows/config.py`, `src/workflows/ingestion.py`

---

*Automated context loading is part of ADR-002 Workflow Integration. See the [full ADR](../adrs/ADR-002-workflow-integration.md) for implementation details and security considerations.*
