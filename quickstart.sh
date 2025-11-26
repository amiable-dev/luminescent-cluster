#!/bin/bash

# Quick start script for the context-aware AI system

echo "======================================================================"
echo "Context-Aware AI Development System - Quick Start"
echo "======================================================================"
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version || { echo "Error: Python 3 not found"; exit 1; }
echo "✓ Python 3 found"
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"
echo ""

# Install dependencies
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✓ Dependencies installed"
echo ""

# Run verification tests
echo "Running verification tests..."
python3 test_setup.py

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "======================================================================"
    echo "✓ Quick start completed successfully!"
    echo "======================================================================"
    echo ""
    echo "The virtual environment is now active."
    echo ""
    echo "Next steps:"
    echo "1. Initialize Pixeltable:"
    echo "   python pixeltable_setup.py"
    echo ""
    echo "2. Start MCP servers (in separate terminals):"
    echo "   python session_memory_server.py"
    echo "   python pixeltable_mcp_server.py"
    echo ""
    echo "3. Configure Claude Code with the MCP servers"
    echo ""
    echo "To deactivate the virtual environment later, run: deactivate"
else
    echo ""
    echo "======================================================================"
    echo "⚠ Some issues were detected. Please review the output above."
    echo "======================================================================"
    exit 1
fi
