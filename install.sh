#!/bin/bash
set -e

# Color output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}Context-Aware AI System Installer${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

echo -e "${YELLOW}Prerequisites:${NC}"
echo "- Claude Code with CLI installed"
echo "- Python 3.8+"
echo ""

# Check if Claude Code CLI is installed
if ! command -v claude &> /dev/null; then
    echo -e "${RED}✗ Error: Claude Code CLI not found${NC}"
    echo ""
    echo "Please install Claude Code first:"
    echo "  https://code.claude.com"
    echo ""
    echo "After installing Claude Code, the 'claude' CLI should be available."
    exit 1
fi
echo -e "${GREEN}✓ Claude Code CLI found${NC}"

# Check if Python is installed
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo -e "${RED}✗ Error: Python not found${NC}"
    echo "Please install Python 3.8 or higher"
    exit 1
fi
echo -e "${GREEN}✓ Python found${NC}"
echo ""

# Determine Python command
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_CMD="python"
fi

# Get the absolute path of this script's directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo -e "${YELLOW}Installing from: ${SCRIPT_DIR}${NC}"
echo ""

# Install Python dependencies
echo -e "${BLUE}[1/3] Installing Python dependencies...${NC}"
$PYTHON_CMD -m pip install -r "${SCRIPT_DIR}/requirements.txt" --quiet
echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# Add session-memory MCP server
echo -e "${BLUE}[2/3] Configuring session-memory MCP server...${NC}"
claude mcp add --transport stdio session-memory \
  --scope user \
  -- $PYTHON_CMD "${SCRIPT_DIR}/session_memory_server.py"

echo -e "${GREEN}✓ session-memory configured${NC}"
echo ""

# Add pixeltable-memory MCP server
echo -e "${BLUE}[3/3] Configuring pixeltable-memory MCP server...${NC}"

# Note: To enable debug logging, manually edit ~/.config/claude/config.json after installation
# and add "env": {"PIXELTABLE_MCP_DEBUG": "1"} to the pixeltable-memory server config
claude mcp add --transport stdio pixeltable-memory \
  --scope user \
  -- $PYTHON_CMD "${SCRIPT_DIR}/pixeltable_mcp_server.py"

echo -e "${GREEN}✓ pixeltable-memory configured${NC}"
echo ""

# Initialize Pixeltable knowledge base
echo -e "${BLUE}Initializing Pixeltable knowledge base...${NC}"
$PYTHON_CMD "${SCRIPT_DIR}/pixeltable_setup.py"
echo -e "${GREEN}✓ Knowledge base initialized${NC}"
echo ""

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}Installation Complete!${NC}"
echo -e "${GREEN}================================${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "1. Restart Claude Code to load the MCP servers"
echo "2. In any project, ask Claude:"
echo "   - 'What are recent changes in this repo?'"
echo "   - 'Search for architectural decisions about authentication'"
echo ""
echo -e "${YELLOW}Note: Session memory analyzes the project where Claude Code is running.${NC}"
echo -e "${YELLOW}      Pixeltable provides long-term organizational knowledge.${NC}"
echo ""
echo "To verify installation:"
echo "  claude mcp list"
echo ""
echo "To uninstall:"
echo "  ./uninstall.sh"
