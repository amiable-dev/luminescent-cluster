#!/bin/bash
set -e

# Install luminescent-cluster for use across all projects on this machine

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

INSTALL_PIXELTABLE=0

show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Install luminescent-cluster globally for use in any project."
    echo ""
    echo "Options:"
    echo "  --with-pixeltable  Include Pixeltable long-term memory (~500MB extra)"
    echo "  -h, --help         Show this help message"
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --with-pixeltable)
            INSTALL_PIXELTABLE=1
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_usage
            exit 1
            ;;
    esac
done

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}Luminescent Cluster - Global Install${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Check for uv
if ! command -v uv &> /dev/null; then
    echo -e "${RED}Error: uv not found${NC}"
    echo "Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi
echo -e "${GREEN}✓ uv found${NC}"

# Install via uv tool
if [ "$INSTALL_PIXELTABLE" -eq 1 ]; then
    echo -e "${BLUE}Installing luminescent-cluster with Pixeltable...${NC}"
    uv tool install "luminescent-cluster[pixeltable]" --force
else
    echo -e "${BLUE}Installing luminescent-cluster (session memory only)...${NC}"
    uv tool install luminescent-cluster --force
fi
echo -e "${GREEN}✓ Package installed${NC}"

# Verify CLI is on PATH
if ! command -v luminescent-cluster &> /dev/null; then
    echo -e "${YELLOW}Warning: luminescent-cluster not on PATH${NC}"
    echo "You may need to add ~/.local/bin to your PATH:"
    echo '  export PATH="$HOME/.local/bin:$PATH"'
else
    echo -e "${GREEN}✓ CLI on PATH: $(which luminescent-cluster)${NC}"
    luminescent-cluster --version
fi

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Installation complete!${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo "To use in a project, add session-memory to .mcp.json in the project root:"
echo ""
echo '  {'
echo '    "mcpServers": {'
echo '      "session-memory": {'
echo '        "command": "luminescent-cluster",'
echo '        "args": ["session"]'
echo '      }'
echo '    }'
echo '  }'
echo ""
echo "If the project already has a .mcp.json, merge the session-memory"
echo "entry into the existing mcpServers object."
echo ""
echo "Then install skills:"
echo "  cd your-project && luminescent-cluster install-skills"
echo ""
if [ "$INSTALL_PIXELTABLE" -eq 0 ]; then
    echo -e "${YELLOW}Tip: Run with --with-pixeltable for long-term organizational memory${NC}"
fi
