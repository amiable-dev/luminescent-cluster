#!/bin/bash

# Uninstall luminescent-cluster global tool

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}Luminescent Cluster - Uninstall${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Remove uv tool
if command -v uv &> /dev/null; then
    echo -e "${BLUE}Removing luminescent-cluster tool...${NC}"
    uv tool uninstall luminescent-cluster 2>/dev/null && \
        echo -e "${GREEN}✓ Tool removed${NC}" || \
        echo -e "${YELLOW}Tool was not installed via uv${NC}"
fi

# Remove user-scope MCP servers (if configured via claude mcp add)
if command -v claude &> /dev/null; then
    echo -e "${BLUE}Removing MCP servers from Claude Code...${NC}"
    claude mcp remove session-memory --scope user 2>/dev/null || true
    claude mcp remove pixeltable-memory --scope user 2>/dev/null || true
    echo -e "${GREEN}✓ MCP servers removed${NC}"
fi

echo ""
echo -e "${GREEN}✓ Uninstall complete${NC}"
echo ""
echo -e "${YELLOW}Note: Project-level .mcp.json files are not removed.${NC}"
echo "Delete them manually from each project if desired."
echo ""
echo -e "${YELLOW}Note: Pixeltable data is not removed.${NC}"
echo "To delete Pixeltable data:"
echo "  rm -rf ~/.pixeltable"
