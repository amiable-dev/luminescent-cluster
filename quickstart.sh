#!/bin/bash
set -e

# Quick start for developers working on luminescent-cluster itself

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}Luminescent Cluster - Developer Setup${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Determine Python version
PYTHON_VERSION="${PYTHON_VERSION:-3.13}"

# Check for uv
if ! command -v uv &> /dev/null; then
    echo -e "${RED}Error: uv not found${NC}"
    echo "Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi
echo -e "${GREEN}✓ uv found${NC}"

# Create venv if needed
if [ ! -d ".venv" ]; then
    echo -e "${BLUE}Creating .venv with Python ${PYTHON_VERSION}...${NC}"
    uv venv --python "$PYTHON_VERSION"
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}✓ Virtual environment already exists${NC}"
fi

# Install dev dependencies
echo -e "${BLUE}Installing dev dependencies...${NC}"
uv pip install -e ".[dev]"
echo -e "${GREEN}✓ Dev dependencies installed${NC}"

# Optionally install pixeltable
if [[ "$1" == "--with-pixeltable" ]]; then
    echo -e "${BLUE}Installing Pixeltable dependencies...${NC}"
    uv pip install -e ".[dev,pixeltable]"
    echo -e "${GREEN}✓ Pixeltable dependencies installed${NC}"
fi

# Verify
echo ""
echo -e "${BLUE}Verifying installation...${NC}"
.venv/bin/luminescent-cluster --version
echo -e "${GREEN}✓ CLI works${NC}"

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Setup complete!${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo "Activate the environment:"
echo "  source .venv/bin/activate"
echo ""
echo "Run tests:"
echo "  pytest tests/ -v --ignore=tests/test_pixeltable_mcp_server.py"
echo ""
echo "Start session memory server:"
echo "  luminescent-cluster session"
echo ""
if [[ "$1" != "--with-pixeltable" ]]; then
    echo -e "${YELLOW}Tip: Run with --with-pixeltable to include Pixeltable deps${NC}"
fi
