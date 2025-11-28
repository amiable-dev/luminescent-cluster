# Quick Reference: Debug Logging

## Enable Debug Logging

MCP servers are spawned by Claude Code, so you need to configure environment variables in the MCP configuration file, not your shell.

### Step 1: Find Your MCP Config

```bash
# macOS/Linux
~/.config/claude/config.json

# Or check with:
claude mcp list
```

### Step 2: Edit the Configuration

Find the `pixeltable-memory` server entry and add the `env` field:

```json
{
  "mcpServers": {
    "pixeltable-memory": {
      "command": "python3",
      "args": ["/absolute/path/to/pixeltable_mcp_server.py"],
      "env": {
        "PIXELTABLE_MCP_DEBUG": "1"
      }
    }
  }
}
```

### Step 3: Restart Claude Code

Close and reopen Claude Code to reload the MCP configuration.

## Log Location

```
~/.mcp-servers/logs/pixeltable-memory.log
```

## View Logs

```bash
# Tail in real-time
tail -f ~/.mcp-servers/logs/pixeltable-memory.log

# View last 50 lines
tail -50 ~/.mcp-servers/logs/pixeltable-memory.log

# Search for errors
grep ERROR ~/.mcp-servers/logs/pixeltable-memory.log
```

## What's Logged

- **MCP tool calls**: Function name, parameters
- **Ingestion details**: Repo path, file count, duration
- **Errors**: Full stack traces
- **Performance**: Operation timing

## Disable

Remove the `"env"` field from the MCP config and restart Claude Code.

## Example Log Output

```
2025-11-28 09:30:00 [DEBUG] ingest_codebase called: repo_path=/Users/christopherjoseph/projects/amiable/midimon, service=conductor, extensions=None
2025-11-28 09:30:00 [DEBUG] Starting ingestion from /Users/christopherjoseph/projects/amiable/midimon...
2025-11-28 09:30:19 [INFO] Ingested 530 files from conductor in 19.2s
2025-11-28 09:30:19 [DEBUG] Ingestion result: {'success': True, 'files_ingested': 530, 'service': 'conductor', 'repo_path': '/Users/christopherjoseph/projects/amiable/midimon', 'duration_seconds': 19.2}
```
