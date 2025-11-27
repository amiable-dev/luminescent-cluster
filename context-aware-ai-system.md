# Context-Aware AI Development: A Practical Implementation

## The Problem

AI coding assistants **forget everything between sessions**. Every conversation starts from scratch:
- Architectural decisions made last week? Gone.
- Production incidents debugged yesterday? Forgotten.
- Team design discussions? Lost.

This creates a cycle of repetitive explanations, inconsistent suggestions, and lost institutional knowledge.

## The Solution: Tiered Memory Architecture

Different context has different access patterns. Our solution uses **three tiers**:

1. **Session Memory (Hot)**: Fast, ephemeral context for active work
2. **Long-term Memory (Cold)**: Persistent organizational knowledge with semantic search
3. **Intelligent Orchestration**: On-demand tool discovery and efficient retrieval

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│               AI Agent (Claude/Antigravity)               │
│                                                           │
│  • Tool Search: Dynamic discovery of tools               │
│  • Programmatic Calling: Efficient orchestration         │
└────────────┬──────────────────────────┬──────────────────┘
             │ MCP Protocol             │ MCP Protocol
             │                          │
   ┌─────────▼──────────┐    ┌─────────▼────────────┐
   │  Session Memory    │    │ Long-term Memory     │
   │  (Hot - <10ms)     │    │ (Cold - 100-500ms)   │
   ├────────────────────┤    ├──────────────────────┤
   │ • Recent commits   │    │ • Code repositories  │
   │ • Current diffs    │    │ • ADR documents      │
   │ • Branch state     │    │ • Incident reports   │
   │ • Active files     │    │ • Meeting records    │
   │                    │    │ • Design artifacts   │
   │ Python + gitpython │    │ Pixeltable + Vector  │
   └────────────────────┘    └──────────────────────┘
```

## Current Status

✅ **Fully Implemented and Operational**

- Session memory MCP server with git integration
- Pixeltable-based long-term memory with semantic search
- Docker Compose deployment for easy setup
- Integration guides for Antigravity and Claude Code
- Helper tools for direct CLI access

## Key Design Decisions

### 1. Tiered Memory Over Single Database

**Why**: Different access patterns require different solutions.
- Session data needs microsecond latency → in-memory structures
- Historical data needs durability and search → persistent database

### 2. Pixeltable for Long-term Memory

**Why**: Incremental computation + multimodal support.
- **Auto-updating embeddings**: Code changes automatically trigger re-indexing
- **Multimodal native**: Videos, images, audio, documents in one system
- **Lineage tracking**: Audit trail for compliance
- **Unified interface**: One API instead of orchestrating 3+ systems

**Alternative considered**: PostgreSQL + pgvector + S3  
**Rejected**: Requires manual pipeline orchestration

### 3. Selective Persistence

**Store**:
- ✅ Architectural decision records (ADRs)
- ✅ Production incidents
- ✅ Meeting transcripts/recordings
- ✅ Major refactoring decisions

**Keep ephemeral**:
- ❌ Current file contents (use git)
- ❌ Build logs (too noisy)
- ❌ Temporary experiments

## Deployment

### Prerequisites

```bash
# Required
docker
docker-compose

# Optional (for local development)
python 3.11+
```

### Quick Start

```bash
# Clone repository
git clone <repo-url> && cd luminescent-cluster

# Start services
docker-compose up -d

# Verify health
docker-compose ps
# Both services should show "healthy"

# Initialize knowledge base (first time only)
docker-compose exec pixeltable-memory python pixeltable_setup.py
```

### Ingest Your Data

```bash
# From examples directory
docker-compose exec pixeltable-memory python -c "
from pixeltable_setup import ingest_codebase
ingest_codebase('/repos', 'your-service-name')
"
```

## Integration with AI Agents

### Antigravity (Gemini Code Assist)

Add to `~/.gemini/antigravity/mcp_config.json`:

```json
{
  "mcpServers": {
    "session-memory": {
      "command": "docker",
      "args": ["exec", "-i", "session-memory-mcp", "python", "session_memory_server.py"],
      "description": "Git context and active changes"
    },
    "pixeltable-memory": {
      "command": "docker", 
      "args": ["exec", "-i", "pixeltable-memory-mcp", "python", "pixeltable_mcp_server.py"],
      "description": "Long-term organizational memory"
    }
  }
}
```

Restart Antigravity. You can now ask:
- "What are recent changes in this repo?"
- "Search for architectural decisions about database"

### Claude Code

Use the provided `claude_config.json` with:
- Tool Search enabled for on-demand discovery
- Programmatic Tool Calling for efficient multi-step workflows
- Deferred loading for Pixeltable (larger tool set)

## Usage Examples

### Direct CLI (No AI Agent)

```bash
# Get recent commits
python agent_tools.py session get_recent_commits --limit 5

# Search knowledge base
python agent_tools.py pixeltable search_knowledge --query "authentication"

# Get architectural decisions
python agent_tools.py pixeltable get_architectural_decisions --topic "database"
```

### Via AI Agent

**Session queries** (fast):
```
"What files changed in the last 24 hours?"
"Show recent commits about authentication"
"What's the current branch status?"
```

**Long-term queries** (semantic):
```
"What architectural decisions did we make about caching?"
"Have we had incidents related to database connections?"
"Find code related to user authentication"
```

**Complex orchestration**:
```
"Compare current auth implementation against the ADR and 
related incidents to suggest improvements"
```

## Performance

### Session Memory
- **Latency**: <10ms
- **Scope**: Current repository, last 200 commits
- **Best for**: Hot context, active work

### Long-term Memory
- **Latency**: 100-500ms (semantic search)
- **Scope**: Entire organizational history
- **Best for**: Architecture decisions, incident history, cross-service context

### Token Efficiency
- **Tool Search**: 85% reduction in upfront token usage
- **Programmatic Calling**: 37% reduction in context consumption
- **Combined**: ~90% reduction for complex queries

## Troubleshooting

### Session Memory Can't Find Git Repo

**Symptom**: "Warning: /app is not a git repository"

**Fix**: Ensure `docker-compose.yml` volume mount is correct:
```yaml
volumes:
  - ${REPO_PATH:-.}:/repos:ro
```

The `REPO_PATH` environment variable must point to your git repository.

### Pixeltable Connection Fails

**Symptom**: "Could not connect to org_knowledge"

**Fix**: 
1. Check service health: `docker-compose ps`
2. Initialize database: `docker-compose exec pixeltable-memory python pixeltable_setup.py`
3. View logs: `docker-compose logs pixeltable-memory`

### Tools Not Appearing in Agent

**Symptom**: AI agent doesn't recognize MCP tools

**Fix**:
1. Verify services are running: `docker-compose ps`
2. Check MCP config file paths are absolute
3. Restart AI agent after config changes
4. Test direct access: `python agent_tools.py session get_recent_commits`

## Maintenance

### Refreshing the Knowledge Base

**Important**: Pixeltable does NOT automatically detect filesystem changes. You must manually re-ingest when code changes.

```bash
# Re-ingest your codebase after changes
docker-compose exec pixeltable-memory python -c "
from pixeltable_setup import setup_knowledge_base, ingest_codebase
kb = setup_knowledge_base()
ingest_codebase(kb, '/repos', 'your-service-name')
"
```

**What's automatic**: When you update the database, embeddings recompute automatically:

```python
# This triggers automatic embedding re-computation
kb.update({kb.path == 'file.py'}, {'content': new_content})
```

**What's NOT automatic**: Detecting file changes on disk. Consider:
- Manual re-ingestion after significant changes
- Cron job to periodically refresh (e.g., nightly)
- Git hooks to trigger updates on commits

### Create Snapshots

Before major refactors:

```python
from pixeltable_setup import snapshot_knowledge_base
snapshot_knowledge_base(name='pre-refactor', tags=['v2.0'])
```

### Cost Optimization

- Uses local `sentence-transformers` for embeddings (free)
- OpenAI optional for higher-quality summaries
- Token reduction from Tool Search (85%) + Programmatic Calling (37%)

## When to Use This

### Ideal For

✅ Teams with significant historical context (mature codebases)  
✅ Multi-person projects where knowledge sharing matters  
✅ Regulated industries needing audit trails (healthcare, finance)  
✅ Multimodal workflows (design, videos, meetings)  
✅ Complex architectures with interconnected services

### Not Ideal For

❌ Solo developers on greenfield projects  
❌ Prototype/MVP development without history  
❌ Teams without AI assistant adoption  
❌ Simple, single-file projects

## Next Steps

1. **Deploy**: Run `docker-compose up -d`
2. **Integrate**: Configure your AI agent (Antigravity or Claude Code)
3. **Ingest**: Add your codebase and ADRs
4. **Test**: Ask "What are recent changes?" and verify it works
5. **Automate** (optional): Set up git hooks to keep knowledge base current (see [CONTRIBUTING.md](CONTRIBUTING.md#automation-opportunities))
6. **Iterate**: Add incidents, meetings, and other context over time

The system gets smarter as you add more context. It's not just about larger context windows—it's about **persistent, queryable memory** that compounds over time.

---

## References

- [Pixeltable Documentation](https://docs.pixeltable.com)
- [MCP Protocol](https://modelcontextprotocol.org)
- [Sample ADR](examples/sample_adr.md) in this repository
