# Local Deployment Guide

Quick guide to run the Context-Aware AI System locally on your machine.

## Prerequisites

- Docker Desktop installed and running
- Git (already have it since you cloned the repo)
- (Optional) OpenAI API key for meeting transcription

## Quick Start

### 1. Navigate to Project Directory

```bash
cd /Users/christopherjoseph/.gemini/antigravity/playground/luminescent-cluster
```

### 2. Configure Environment (Optional)

The `.env` file is already created. If you want to use OpenAI features, edit it:

```bash
# Edit .env to add your OpenAI API key
nano .env

# Add your key:
# OPENAI_API_KEY=sk-your-key-here
```

### 3. Build Docker Images

```bash
docker-compose build
```

This will:
- Build session-memory image (~100MB, 2-3 min)
- Build pixeltable-memory image (~2GB, 5-10 min)

### 4. Start Services

```bash
docker-compose up -d
```

This starts both MCP servers in detached mode.

### 5. Verify Services Are Running

```bash
# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Or view specific service
docker-compose logs -f session-memory
docker-compose logs -f pixeltable-memory
```

### 6. Initialize Pixeltable Knowledge Base

First time only:

```bash
docker-compose exec pixeltable-memory python pixeltable_setup.py
```

### 7. Test the System

```bash
# Test session memory (check git integration)
docker-compose exec session-memory python -c "
from session_memory_server import SessionMemoryServer
import asyncio
server = SessionMemoryServer()
commits = asyncio.run(server.get_recent_commits(5))
for c in commits:
    print(f\"{c['hash']}: {c['message'][:50]}\")
"

# Test Pixeltable (verify it's running)
docker-compose exec pixeltable-memory python -c "
import pixeltable as pxt
print('✓ Pixeltable is running')
"
```

## Connecting to Claude Code

Update your Claude MCP configuration (`~/.config/claude/config.json` or similar):

```json
{
  "mcpServers": {
    "session-memory": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "session-memory-mcp",
        "python",
        "session_memory_server.py"
      ],
      "description": "Session memory for git context"
    },
    "pixeltable-memory": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "pixeltable-memory-mcp",
        "python",
        "pixeltable_mcp_server.py"
      ],
      "description": "Long-term organizational memory"
    }
  },
  "toolConfiguration": {
    "toolSearch": {
      "enabled": true
    },
    "programmaticToolCalling": {
      "enabled": true
    }
  }
}
```

## Common Commands

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose stop

# Stop and remove containers (data persists in volumes)
docker-compose down

# View logs
docker-compose logs -f

# Restart a service
docker-compose restart session-memory

# Execute commands in containers
docker-compose exec session-memory bash
docker-compose exec pixeltable-memory python pixeltable_setup.py

# Check resource usage
docker stats
```

## Ingesting Your Codebase

```bash
# Ingest another repository into Pixeltable
docker-compose exec pixeltable-memory python -c "
from pixeltable_setup import setup_knowledge_base, ingest_codebase

kb = setup_knowledge_base()
ingest_codebase(kb, '/repos/your-repo', 'service-name')
"
```

## Adding ADRs and Incidents

```bash
# Add an ADR
docker-compose exec pixeltable-memory python -c "
from pixeltable_setup import setup_knowledge_base, ingest_adr

kb = setup_knowledge_base()
ingest_adr(kb, 'path/to/adr.md', 'ADR Title')
"

# Add an incident
docker-compose exec pixeltable-memory python -c "
from pixeltable_setup import setup_knowledge_base, ingest_incident
from datetime import datetime

kb = setup_knowledge_base()
ingest_incident(kb, {
    'title': 'Production Outage - Nov 2024',
    'description': 'Description of what happened...',
    'date': datetime(2024, 11, 26),
    'service': 'api-gateway',
    'severity': 'critical',
    'resolved': True
})
"
```

## Backup Pixeltable Data

```bash
# Create backup
docker run --rm \
  -v luminescent-cluster_pixeltable-data:/data \
  -v $(pwd)/backups:/backups \
  alpine tar czf /backups/pixeltable-$(date +%Y%m%d).tar.gz /data

# Restore backup
docker run --rm \
  -v luminescent-cluster_pixeltable-data:/data \
  -v $(pwd)/backups:/backups \
  alpine tar xzf /backups/pixeltable-20241126.tar.gz -C /
```

## Troubleshooting

### Services won't start

```bash
# Check Docker is running
docker info

# Check logs for errors
docker-compose logs

# Rebuild without cache
docker-compose build --no-cache
docker-compose up -d
```

### Permission errors

```bash
# Reset volumes
docker-compose down -v
docker-compose up -d
```

### Out of disk space

```bash
# Clean up Docker system
docker system prune -a

# Check space
docker system df
```

### Pixeltable errors

```bash
# Reinitialize database
docker-compose exec pixeltable-memory python pixeltable_setup.py
```

## Stopping Services

```bash
# Stop (containers removed, volumes persist)
docker-compose down

# Stop and remove volumes (⚠️ deletes all data)
docker-compose down -v
```

## Monitoring

```bash
# Resource usage
docker stats

# Specific container
docker stats session-memory-mcp pixeltable-memory-mcp

# Logs
docker-compose logs -f --tail=100
```

## Next Steps

1. ✅ Services running locally
2. Configure Claude Code to use the MCP servers
3. Test queries:
   - "What files were changed in the last 24 hours?"
   - "What architectural decisions do we have?"
4. Ingest your actual codebase
5. Add ADRs and incidents
6. Start using with Claude!

## Support

- Documentation: `README.md`
- Deployment Guide: `DEPLOYMENT.md`
- Architecture: `context-aware-ai-system.md`
- Examples: `examples/example_usage.py`

## GitHub Repository

https://github.com/amiable-dev/context-aware-ai-system
