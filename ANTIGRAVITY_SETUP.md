# Enabling Antigravity (Gemini Code Assist)

To enable Antigravity to natively use the Context-Aware AI System, you need to register the MCP servers in your agent's configuration.

## 1. Locate Configuration

The configuration file is located at:
`/Users/christopherjoseph/.gemini/antigravity/mcp_config.json`

## 2. Add MCP Servers

Add the following to the `mcpServers` section of the config file:

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
      "env": {
        "PYTHONUNBUFFERED": "1"
      },
      "description": "Session memory for git context and active changes"
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
      "env": {
        "PYTHONUNBUFFERED": "1"
      },
      "description": "Long-term organizational memory (code, ADRs, incidents)"
    }
  }
}
```

## 3. Restart

After saving the configuration, restart your IDE or the Antigravity agent for the changes to take effect.

## 4. Verification

Once restarted, you can ask Antigravity:
- "What are the recent changes in this repo?" (Uses session-memory)
- "Search for architectural decisions about database" (Uses pixeltable-memory)

---

## Immediate Usage (Without Restart)

I have also created a helper script `agent_tools.py` that allows you (or me) to use these tools immediately via the terminal, without changing global configuration.

```bash
# Example: Get recent commits
python agent_tools.py session get_recent_commits --limit 5

# Example: Search knowledge base
python agent_tools.py pixeltable search_knowledge --query "deployment"
```
