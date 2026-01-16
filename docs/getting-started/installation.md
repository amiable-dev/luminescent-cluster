# Installation

This guide covers installing Luminescent Cluster and configuring MCP servers for Claude Code.

---

## Prerequisites

- Python 3.10+ (3.11 recommended)
- Git
- Claude Code (or MCP-compatible client)

---

## Quick Install

```bash
# Clone the repository
git clone https://github.com/amiable-dev/luminescent-cluster.git ~/.mcp-servers/luminescent-cluster
cd ~/.mcp-servers/luminescent-cluster

# Run the installer
./install.sh
```

The installer will:

1. Create a virtual environment
2. Install Python dependencies
3. Configure MCP servers in Claude Code (user scope)
4. Initialize the Pixeltable knowledge base

### Installer Options

```bash
./install.sh --help     # Show usage information
./install.sh --debug    # Enable debug logging
```

---

## Manual Installation

If you prefer manual installation:

### 1. Create Virtual Environment

=== "uv (Recommended)"

    ```bash
    cd ~/.mcp-servers/luminescent-cluster
    uv venv --python 3.11
    source .venv/bin/activate
    uv pip install -e .
    ```

=== "pip"

    ```bash
    cd ~/.mcp-servers/luminescent-cluster
    python3.11 -m venv .venv
    source .venv/bin/activate
    pip install -e .
    ```

### 2. Configure Claude Code

Edit `~/.config/claude/config.json`:

```json
{
  "mcpServers": {
    "session-memory": {
      "command": "python3",
      "args": ["~/.mcp-servers/luminescent-cluster/session_memory_server.py"]
    },
    "pixeltable-memory": {
      "command": "python3",
      "args": ["~/.mcp-servers/luminescent-cluster/pixeltable_mcp_server.py"]
    }
  }
}
```

### 3. Initialize Knowledge Base

```bash
python pixeltable_setup.py
```

### 4. Restart Claude Code

Restart to load the MCP servers.

---

## Verify Installation

After installation, verify the MCP servers are available:

```
> "What MCP tools are available?"
```

You should see tools like:

- `get_recent_commits`
- `get_current_branch`
- `search_organizational_memory`
- `ingest_codebase`

---

## Troubleshooting

### Exit Code 78: Python Version Mismatch

The runtime guard detected a version mismatch.

```bash
# Check expected version
cat ~/.pixeltable/.python_version

# Switch to correct version
uv venv --python <version>
source .venv/bin/activate
```

### Exit Code 65: Legacy Database

Database was created before version tracking.

```bash
# If you know the Python version:
echo '3.11' > ~/.pixeltable/.python_version
```

### Tools Not Appearing

1. Verify `.mcp.json` exists
2. Check MCP server paths are correct
3. Restart Claude Code

See [Known Issues](../KNOWN_ISSUES.md) for more troubleshooting.

---

## Next Steps

- [Quick Start](quickstart.md) - Ingest your first codebase
- [Configuration](configuration.md) - Enable debug logging and extensions
