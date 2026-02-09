# Context-Aware AI Development System

A hybrid approach combining session memory, long-term persistent knowledge, and Claude's advanced tool use features.

## Architecture

### Tier 1: Session Memory (Hot Context)
- Fast access to git history
- Recent commits and changes
- Current branch state
- Active file tracking

### Tier 2: Long-term Memory (Persistent Knowledge)
- Code repositories with semantic search
- Architectural Decision Records (ADRs)
- Production incident history
- Meeting transcripts
- Design artifacts

### Tier 3: Intelligent Orchestration
- Tool Search Tool: On-demand tool discovery (85% token reduction)
- Programmatic Tool Calling: Efficient multi-step workflows (37% token reduction)

**📖 Deep Dive**: See [Multi-Project Architecture](multi-project-architecture.md) for how session and long-term memory work together across multiple projects.

## Quick Start

### 1. Clone and Install

```bash
# Clone to a standard location (system-wide MCP servers)
git clone https://github.com/your-org/context-aware-ai-system.git ~/.mcp-servers/context-aware-ai-system
cd ~/.mcp-servers/context-aware-ai-system
```

### 1. Run the Installer

```bash
cd /path/to/luminescent-cluster
./install.sh

# Or with debug logging enabled:
./install.sh --debug
```

This will:
- Install Python dependencies
- Configure MCP servers in Claude Code (user scope)
- Initialize Pixeltable knowledge base
- Make servers available across all your projects

**Options**:
- `--debug`: Enable debug logging (logs to `~/.mcp-servers/logs/pixeltable-memory.log`)
- `--help`: Show usage information

### 2. Restart Claude Code

Restart Claude Code to load the MCP servers.

### 3. Ingest Your Codebase

You can now ask Claude Code to ingest your projects directly:

> "Ingest this codebase as 'auth-service'"

Or use the MCP tool explicitly:

```python
# Claude will call this tool for you
ingest_codebase(
    repo_path=os.getcwd(),
    service_name="auth-service"
)
```

#### Debug Logging

For troubleshooting, enable detailed logging by editing your MCP configuration:

**Step 1**: Find your Claude Code MCP config:
```bash
~/.config/claude/config.json
```

**Step 2**: Add `env` to the `pixeltable-memory` server:
```json
{
  "mcpServers": {
    "pixeltable-memory": {
      "command": "luminescent-cluster",
      "args": ["pixeltable"],
      "env": {
        "PIXELTABLE_MCP_DEBUG": "1"
      }
    }
  }
}
```

**Step 3**: Restart Claude Code

**Logs**: `~/.mcp-servers/logs/pixeltable-memory.log`

Shows:
- Exact paths being ingested
- File counts and timing  
- Error details and stack traces
- MCP call parameters

**Disable**: Remove the `"env"` field and restart.

See [`docs/DEBUG_LOGGING.md`](docs/DEBUG_LOGGING.md) for details.

### 4. Add Historical Context

> "Add this ADR to the knowledge base"
> "Record this incident: Auth service outage on Nov 27 due to timeout"

Or use the tools:

```python
# Add an ADR
ingest_architectural_decision(
    adr_path="docs/adr/001-database.md",
    title="ADR 001: Database Choice"
)

# Add an incident
ingest_incident(
    title="Auth Service Outage",
    description="Timeout in auth service caused 500 errors...",
    service="auth-service"
)
```

#### File Filtering

**Why we filter**: The ingestion process filters files by extension to avoid:
- **Binary files**: Images, executables, compiled artifacts (not useful for text search)
- **Generated code**: Build outputs, node_modules, vendor directories (adds noise)
- **Non-text formats**: Don't benefit from embedding-based semantic search

**Smart filtering**: 
- **Respects `.gitignore`**: If your project has a `.gitignore`, it's automatically used to skip files
- **Fallback filters**: Without `.gitignore`, skips common patterns (node_modules, __pycache__, .git, dist, build, etc.)
- **Extension filtering**: Only ingests source code files (configurable, see below)

**Default extensions**: Python, JavaScript, TypeScript, Rust, Go, Java, C/C++, Shell, SQL, YAML, Markdown, and more.

**Customize for your project**:

> "Ingest this codebase as 'my-service' with only Rust files"

Or specify custom extensions:
```python
ingest_codebase(
    repo_path=".",
    service_name="my-service",
    extensions=[".rs", ".toml", ".proto"]
)
```

**Check what was ingested**:
```bash
./scripts/check-status.sh -v  # Shows recent entries with file paths
```

### 5. Manage Your Knowledge Base

> "Show me stats about the knowledge base"
> "Create a snapshot called 'pre-release'"
> "List all services"


## MCP Server Configuration

Luminescent Cluster provides two MCP servers that connect to Claude Code (or any MCP-compatible client):

| Server | Install | Dependencies |
|--------|---------|--------------|
| **session-memory** | Base install | Lightweight (~36 packages) |
| **pixeltable-memory** | `[pixeltable]` extra | Heavy (~500MB macOS, ~2GB Linux/CUDA: torch, sentence-transformers, embedded PostgreSQL) |

Most users only need **session-memory**. The Pixeltable server is for long-term organizational knowledge (ADRs, code embeddings, incident history).

### Install the Package

```bash
# Recommended: full install with Pixeltable long-term memory (~500MB)
uv tool install "luminescent-cluster[pixeltable]"

# Or use the install script (includes Pixeltable by default)
./install.sh

# Lightweight alternative (session memory only, no ML deps)
uv tool install luminescent-cluster
./install.sh --session-only
```

### Configure Claude Code

Create a `.mcp.json` in your project root (or add to an existing one). **Do not commit this file** — it is already in `.gitignore`.

If the project already has a `.mcp.json` with other MCP servers, merge the `session-memory` entry into the existing `mcpServers` object rather than replacing the file.

**Full install** (session + Pixeltable — the default):

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

**Development install** (editable install in a local venv):

```json
{
  "mcpServers": {
    "session-memory": {
      "command": "/absolute/path/to/.venv/bin/luminescent-cluster",
      "args": ["session"]
    }
  }
}
```

Use the absolute path to the venv binary because Claude Code does not activate virtual environments when spawning MCP server processes.

**Session memory only** (if installed with `--session-only` or without `[pixeltable]`):

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

### Install Skills

After configuring the servers, install the bundled session management skills:

```bash
luminescent-cluster install-skills
```

This copies `/session-init` and `/session-save` skills to `.claude/skills/` where Claude Code discovers them as slash commands.

### Verify

Restart Claude Code, then run `/mcp` to confirm the server(s) are connected.

## Example Queries

### With Claude Code

Once configured, Claude can query both memory tiers:

**Session queries** (fast):
```
"What files were changed in the last 24 hours?"
"Show me recent commits about authentication"
"What's the current branch status?"
```

**Long-term queries** (semantic):
```
"What architectural decisions did we make about caching?"
"Have we had any incidents related to database connections?"
"Find all code related to user authentication"
```

**Project-specific queries** (with filtering):
```
"Show me ADRs about database design in the auth-service project"
"What incidents has payment-api had?"
"Search for rate limiting code in the web-app service"
```

The Pixeltable tools support optional `service` parameter to filter results to specific projects.

**Complex orchestration** (programmatic):
```
"Compare our current auth implementation against the ADR and 
any related incidents to suggest improvements"
```

This last query would use Programmatic Tool Calling to:
1. Search ADRs for "authentication"
2. Search incidents for "auth-related failures"
3. Search code for "authentication implementation"
4. Synthesize findings without polluting context

## Tool Configuration

### Tool Search Tool

Available via  Claude Code's MCP integration:
- Session memory: Always loaded (defer_loading: false)
- Pixeltable memory: Loaded on-demand (defer_loading: true)
- Additional MCP servers: Defer by default

### Programmatic Tool Calling

Enabled via `programmaticToolCalling.enabled: true`

Allows Claude to write Python orchestration code that:
- Calls multiple tools in parallel
- Processes results in sandbox
- Returns only synthesized output
- Reduces context consumption by 37%

## File Structure

```
luminescent-cluster/
├── pyproject.toml                 # Package config, dependencies, extras
├── src/luminescent_cluster/       # Core package
│   ├── cli.py                     # CLI entry point
│   ├── servers/
│   │   ├── session_memory.py      # Tier 1: Session memory MCP server
│   │   └── pixeltable.py          # Tier 2: Long-term memory MCP server
│   ├── skills/                    # Bundled skills and loader
│   │   ├── loader.py              # SkillLoader with progressive disclosure
│   │   └── bundled/               # Skills shipped in the wheel
│   ├── memory/                    # Memory system (extraction, MaaS)
│   ├── extensions/                # Protocol-based extension system
│   └── chatbot/                   # Multi-platform chatbot gateway
├── tests/                         # Test suite (pytest)
├── docs/adrs/                     # Architecture Decision Records
├── install.sh                     # Global install script (uv tool)
├── quickstart.sh                  # Developer setup script
└── uninstall.sh                   # Uninstall script
```

## Performance Characteristics

### Session Memory
- **Latency**: <10ms (in-memory)
- **Scope**: Current repository, last 200 commits
- **Best for**: Hot context, current work

### Long-term Memory
- **Latency**: 100-500ms (semantic search)
- **Scope**: Entire organizational history
- **Best for**: Architecture decisions, incident history, cross-service context

### Tool Orchestration
- **Token savings**: 60-85% combined (Tool Search + PTC)
- **Accuracy improvement**: +7-13% on complex tasks
- **Latency improvement**: 10x for multi-step workflows

## Maintenance

### Update Embeddings

Pixeltable automatically updates embeddings when content changes:

```python
# Just update the content, embeddings recompute automatically
kb.update({kb.path == 'some/file.py'}, {'content': new_content})
```

### Create Snapshots

Before major refactors:

```python
from pixeltable_setup import snapshot_knowledge_base

snapshot_knowledge_base(
    name='pre-auth-refactor',
    tags=['v2.0', 'stable']
)
```

### Rollback if Needed

```python
pxt.restore('org_knowledge', snapshot='pre-auth-refactor')
```

## Cost Optimization

### Embedding Generation
- Uses local sentence-transformers by default (free)
- Upgrade to OpenAI embeddings if needed

### Summaries
- Uses simple truncation by default
- Enable OpenAI summarization in `pixeltable_setup.py` for better quality

### Token Usage
- Tool Search Tool: 85% reduction
- Programmatic Tool Calling: 37% reduction
- Combined effect: ~90% reduction for complex queries

## Python Version Requirements

**CRITICAL:** The Pixeltable database is bound to the Python version that created it. Using a different Python minor version will cause a **silent segmentation fault** (exit code 139).

### Version Compatibility

| Created With | Safe to Run | Unsafe |
|--------------|-------------|--------|
| 3.10.x       | 3.10.0 - 3.10.99 | 3.9.x, 3.11+ |
| 3.11.x       | 3.11.0 - 3.11.99 | 3.10.x, 3.12+ |
| 3.12.x       | 3.12.0 - 3.12.99 | 3.11.x, 3.13+ |

**Patch version changes are SAFE** (3.11.0 -> 3.11.9). Only minor version changes are dangerous.

### Runtime Protection

The MCP servers include a version guard that:
- Creates a `.python_version` marker on first run
- Exits with code **78** if Python version mismatches
- Exits with code **65** for legacy databases without markers

### Quick Fix

```bash
# Check what version the database expects
cat ~/.pixeltable/.python_version

# Switch to the correct version
uv venv --python 3.11
source .venv/bin/activate
```

For migration procedures, see [ADR-001](docs/adrs/ADR-001-python-version-requirement-for-mcp-servers.md).

## Troubleshooting

### "No git repository found"
Session memory server needs to run in a git repository directory.

### "Could not connect to org_knowledge"
Run `python pixeltable_setup.py` first to initialize the knowledge base.

### Tools not appearing in Claude
Check `.mcp.json` exists and MCP servers are configured correctly.

### Exit code 78: Python version mismatch
The runtime guard detected that your Python version doesn't match the database.
```bash
# Check expected version
cat ~/.pixeltable/.python_version

# Switch to correct version
uv venv --python <version>
source .venv/bin/activate
```

### Exit code 65: Legacy database detected
The database was created before version tracking was implemented.
```bash
# If you know the Python version that created it:
echo '3.11' > ~/.pixeltable/.python_version

# Then run with that version
uv venv --python 3.11
source .venv/bin/activate
```

### Exit code 139: Segmentation fault

Caused by corrupted UDFs (User-Defined Functions) after Python version changes.

**Quick diagnosis:**
```bash
python -m scripts.db_repair --check
```

**Recovery options:**

1. **Use correct Python version** (recommended):
   ```bash
   uv venv --python 3.11  # Use version that created DB
   source .venv/bin/activate
   ```

2. **Backup and restore** (preserves data):
   ```bash
   python -m scripts.backup_restore --backup-restore --confirm
   ```

3. **Fresh install** (deletes all data):
   ```bash
   rm -rf ~/.pixeltable/
   ```

See [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md#known-issue-udf-corruption-after-python-version-change) for detailed recovery procedures.

## Architecture: Extension System

Luminescent Cluster uses a **Protocol/Registry pattern** for extensibility (see [ADR-005](docs/adrs/ADR-005-repository-organization-strategy.md)).

### Extension Points

| Extension | Purpose | OSS Default |
|-----------|---------|-------------|
| `TenantProvider` | Multi-tenancy isolation | None (single-user) |
| `UsageTracker` | Usage metering/billing | None (no tracking) |
| `AuditLogger` | Compliance audit logs | None (local logs only) |

### Usage Pattern

```python
from src.extensions import ExtensionRegistry

# Check if extensions are registered
registry = ExtensionRegistry.get()

# OSS mode: Extensions are None, code handles gracefully
if registry.tenant_provider:
    tenant_id = registry.tenant_provider.get_tenant_id(context)
    filter = registry.tenant_provider.get_tenant_filter(tenant_id)

# Check mode
registry.get_status()  # {'mode': 'oss', ...} or {'mode': 'cloud', ...}
```

### Implementing Extensions

Extensions implement Python Protocols (duck typing):

```python
from src.extensions import ExtensionRegistry

class MyTenantProvider:
    def get_tenant_id(self, ctx: dict) -> str:
        return ctx.get("x-tenant-id")

    def get_tenant_filter(self, tenant_id: str) -> dict:
        return {"tenant_id": {"$eq": tenant_id}}

    def validate_tenant_access(self, tenant_id, user_id, resource) -> bool:
        return True  # Your RBAC logic

# Register at startup
registry = ExtensionRegistry.get()
registry.tenant_provider = MyTenantProvider()
```

## Chatbot Platform Integrations (ADR-006)

Luminescent Cluster supports conversational interfaces via chatbot integrations on **Slack, Discord, Telegram, and WhatsApp**. See [ADR-006](docs/adrs/ADR-006-chatbot-platform-integrations.md) for full details.

### Access Control Configuration

The chatbot uses a pluggable access control system:

```python
from src.chatbot.access_control import (
    DefaultAccessControlPolicy,      # OSS: allow all
    ConfigurableAccessControlPolicy,  # Self-hosted: config-based
    ResponseFilterPolicy,             # Filter sensitive data
)

# Default (OSS mode) - allows all channels and commands
policy = DefaultAccessControlPolicy()

# Self-hosted with restrictions
policy = ConfigurableAccessControlPolicy(
    allowed_channels=["#general", "#engineering"],
    blocked_channels=["#hr", "#legal"],
    allowed_commands=["/help", "/ask", "/search"],
)

# Filter sensitive data in public channels
filter_policy = ResponseFilterPolicy(
    sensitive_patterns=[
        r"password\s*[:=]\s*\S+",
        r"api[_-]?key\s*[:=]\s*\S+",
    ]
)
```

### Context Persistence

Conversation context persists in Pixeltable with 90-day retention:

```python
from src.chatbot.context import ThreadContextManager, PixeltableContextStore

# With persistence
store = PixeltableContextStore()
manager = ThreadContextManager(context_store=store)

# Get/update thread context
context = await manager.get_context(thread_id="thread-123")
await manager.update_context(thread_id="thread-123", message=new_message)
```

### Observability

ChatMetrics provides telemetry for monitoring:

```python
from src.chatbot.metrics import ChatMetrics

metrics = ChatMetrics()
await metrics.record_query(
    platform="discord",
    user_id="user-123",
    query_type="search",
    latency_ms=245,
    tokens_used=150,
    memory_hits=3,
)
```

### Data Management (Self-Hosted)

When using luminescent-cluster self-hosted, you have full control over your data:

- **Location**: Data stored in your local Pixeltable instance (`~/.pixeltable/`)
- **Deletion**: Use Pixeltable CLI or API to manage/delete data
- **No Third Party**: Amiable does not access your self-hosted data
- **Retention**: Default 90-day TTL for conversation context (configurable)

For GDPR compliance in self-hosted deployments, you are the data controller. Use Pixeltable's built-in tools:

```python
import pixeltable as pxt

# View stored data
pxt.list_tables()

# Delete conversation context
table = pxt.get_table('conversation_context')
table.delete(table.thread_id == 'thread-to-delete')

# Clear all chatbot data
pxt.drop_table('conversation_context')
```

**Note**: For managed Luminescent Cloud deployments, GDPR-compliant `/forget-me` and `/export-my-data` commands are available.

## Project Structure

```
luminescent-cluster/
├── pyproject.toml                 # Package config, deps, extras ([pixeltable], [dev], [all])
├── src/luminescent_cluster/
│   ├── cli.py                     # CLI entry point (session, pixeltable, install-skills)
│   ├── version_guard.py           # Python version safety (ADR-001)
│   ├── servers/
│   │   ├── session_memory.py      # Tier 1: Session memory MCP server
│   │   └── pixeltable.py          # Tier 2: Long-term memory MCP server
│   ├── skills/                    # Bundled skills and progressive disclosure loader
│   │   ├── loader.py              # SkillLoader (Level 1/2/3)
│   │   └── bundled/               # Skills shipped in the wheel
│   ├── memory/                    # Memory system (extraction, evaluation, MaaS)
│   ├── extensions/                # Extension system (ADR-005)
│   │   ├── protocols.py           # TenantProvider, UsageTracker, AuditLogger
│   │   └── registry.py            # ExtensionRegistry singleton
│   ├── chatbot/                   # Chatbot platform integrations (ADR-006)
│   │   ├── gateway.py             # Central Chat Gateway
│   │   ├── context.py             # Thread context management
│   │   ├── metrics.py             # ChatMetrics telemetry
│   │   ├── access_control.py      # Access control policies
│   │   └── adapters/              # Platform-specific adapters
│   └── integrations/              # PAT integrations (GitHub, GitLab)
├── tests/
│   ├── test_version_guard.py      # Version guard tests (19 tests)
│   ├── test_extensions.py         # Extension system tests (30 tests)
│   ├── test_skills.py             # Skills loader tests (45 tests)
│   └── chatbot/                   # Chatbot tests
├── docs/adrs/                     # Architectural Decision Records
├── install.sh                     # Global install script (uv tool)
├── quickstart.sh                  # Developer setup script
└── uninstall.sh                   # Uninstall script
```

## Contributing

This is an open-source project under Apache 2.0 license. Contributions welcome!

**Note**: First-time contributors will need to sign a Contributor License Agreement (CLA). The CLA Assistant will guide you through the process when you open your first PR.

### Development Setup

```bash
# Clone and quick start
git clone https://github.com/amiable-dev/luminescent-cluster.git
cd luminescent-cluster
./quickstart.sh                    # or: ./quickstart.sh --with-pixeltable

# Or manually
uv venv && uv pip install -e ".[dev]"

# Run tests
pytest tests/ -v --ignore=tests/test_pixeltable_mcp_server.py
```

### Contribution Areas

1. **Core Features**: MCP server improvements, semantic search enhancements
2. **Integrations**: Webhook support, IDE plugins, additional Git hosting providers
3. **Documentation**: Examples, tutorials, API documentation
4. **Testing**: Additional test coverage, integration tests

### Test Suite

```bash
# Run all tests
pytest tests/ -v --ignore=tests/test_pixeltable_mcp_server.py

# Run specific test categories
pytest tests/test_skills.py -v              # Skills loader (45 tests)
pytest tests/test_extensions.py -v          # Extension system (30 tests)
pytest tests/test_version_guard.py -v       # Version safety (19 tests)
pytest tests/test_session_memory_mcp_server.py -v  # Session MCP server
```

### ADR Process

Significant changes require an ADR (Architectural Decision Record):
1. Copy `docs/adrs/template.md` to `docs/adrs/ADR-NNN-title.md`
2. Fill in context, decision, and consequences
3. Submit PR for review

## License

Apache 2.0 License - see LICENSE file

## References

- [Pixeltable Documentation](https://docs.pixeltable.com)
- [Claude Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)
- [MCP Protocol](https://modelcontextprotocol.org)

## Advanced Usage & Fallbacks

## Advanced Usage & Fallbacks

### Enabling Advanced Tool Use (Claude Code)
To leverage Anthropic's **Advanced Tool Use** features (Tool Search and Programmatic Tool Calling) with this system, you must configure your client (Claude Code).

**Configuration (`.mcp.json`):**
```json
{
    "toolConfiguration": {
        "toolSearch": {
            "enabled": true,
            "provider": "regex"  // or "embedding"
        },
        "programmaticToolCalling": {
            "enabled": true
        },
        "deferredLoading": {
            "pixeltableMemory": true  // Defer heavy tools
        }
    }
}
```

**How it works:**
-   **Tool Search**: When enabled, Claude Code automatically handles the "beta headers" and tool discovery process. You do not need to implement `search_tools` yourself; the client handles it.
-   **Programmatic Tool Calling**: Claude Code will write Python orchestration scripts to call our atomic tools (`get_recent_commits`, `search_knowledge`) efficiently.

### Graceful Fallback (RAG Pattern)
For other AI clients or models that do not support tool calling (or if you prefer manual control), the system fully supports the **RAG (Retrieval Augmented Generation)** pattern.

**How to use:**
1.  **Pre-fetch Context**: Use the provided scripts to search for relevant information.
2.  **Inject Context**: Insert the retrieved text into your prompt.

**Example (Python):**
```python
# 1. Retrieve context programmatically
context = search_knowledge(kb, query="database schema", limit=2)

# 2. Construct prompt
prompt = f"""
Context: {context}
Question: How do I query the user table?
"""

# 3. Send to LLM
response = llm.complete(prompt)
```

See `examples/example_usage.py` (Example 9) for a complete working demonstration.
