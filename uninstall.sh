#!/bin/bash

# Color output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}Context-Aware AI System Uninstaller${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# Check if Claude Code CLI is installed
if ! command -v claude &> /dev/null; then
    echo -e "${RED}Error: Claude Code CLI not found${NC}"
    exit 1
fi

echo -e "${YELLOW}Removing MCP servers from Claude Code...${NC}"
echo ""

# Remove session-memory
echo -e "${BLUE}Removing session-memory...${NC}"
claude mcp remove session-memory --scope user 2>/dev/null || echo "  (already removed)"

# Remove pixeltable-memory
echo -e "${BLUE}Removing pixeltable-memory...${NC}"
claude mcp remove pixeltable-memory --scope user 2>/dev/null || echo "  (already removed)"

echo ""
echo -e "${GREEN}✓ MCP servers removed from Claude Code${NC}"
echo ""
echo -e "${YELLOW}Note: This does not delete the Pixeltable data directory.${NC}"
echo "To remove Pixeltable data:"
echo "  rm -rf ~/.pixeltable"
echo "  rm -rf ./pixeltable_data"
echo ""
echo "To remove this installation:"
echo "  rm -rf $(dirname "${BASH_SOURCE[0]}")"
