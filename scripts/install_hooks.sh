#!/bin/bash
# ADR-002: Install git hooks for workflow integration
#
# This script installs the git hooks from .agent/hooks/ to .git/hooks/
# for automatic knowledge base synchronization.
#
# Usage: ./scripts/install_hooks.sh
#
# Related: ADR-002 Workflow Integration

set -euo pipefail

# Determine project root
if ! PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null); then
    echo "ERROR: Not in a git repository"
    exit 1
fi

HOOKS_SOURCE="${PROJECT_ROOT}/.agent/hooks"
HOOKS_TARGET="${PROJECT_ROOT}/.git/hooks"

echo "Installing git hooks for ADR-002 workflow integration..."
echo "  Source: ${HOOKS_SOURCE}"
echo "  Target: ${HOOKS_TARGET}"
echo ""

# Check if source hooks exist
if [ ! -d "$HOOKS_SOURCE" ]; then
    echo "ERROR: Source hooks directory not found at ${HOOKS_SOURCE}"
    exit 1
fi

# Check for existing hooks and back them up
for hook in post-commit post-merge post-rewrite; do
    if [ -f "${HOOKS_TARGET}/${hook}" ]; then
        # Check if it's our hook (has ADR-002 marker)
        if grep -q "ADR-002" "${HOOKS_TARGET}/${hook}" 2>/dev/null; then
            echo "  ${hook}: Already installed (ADR-002 hook)"
        else
            echo "  WARNING: Existing ${hook} found. Backing up to ${hook}.backup"
            mv "${HOOKS_TARGET}/${hook}" "${HOOKS_TARGET}/${hook}.backup"
        fi
    fi
done

# Install new hooks
INSTALLED=0
for hook in post-commit post-merge post-rewrite; do
    if [ -f "${HOOKS_SOURCE}/${hook}" ]; then
        # Skip if already our hook
        if [ -f "${HOOKS_TARGET}/${hook}" ] && grep -q "ADR-002" "${HOOKS_TARGET}/${hook}" 2>/dev/null; then
            continue
        fi
        cp "${HOOKS_SOURCE}/${hook}" "${HOOKS_TARGET}/"
        chmod +x "${HOOKS_TARGET}/${hook}"
        echo "  Installed: ${hook}"
        INSTALLED=$((INSTALLED + 1))
    else
        echo "  WARNING: Source hook not found: ${HOOKS_SOURCE}/${hook}"
    fi
done

# Create required directories
mkdir -p "${PROJECT_ROOT}/.agent/state"
mkdir -p "${PROJECT_ROOT}/.agent/logs"
mkdir -p "${PROJECT_ROOT}/.claude/skills"

echo ""
if [ $INSTALLED -gt 0 ]; then
    echo "SUCCESS: Installed ${INSTALLED} hook(s)"
else
    echo "All hooks already installed"
fi
echo ""
echo "Directories created:"
echo "  - .agent/state/   (ingestion state)"
echo "  - .agent/logs/    (ingestion logs)"
echo "  - .claude/skills/ (Agent Skills)"
echo ""
echo "To uninstall: rm ${HOOKS_TARGET}/post-{commit,merge,rewrite}"
echo ""
echo "Test with: echo '# Test' > test.md && git add test.md && git commit -m 'test hook'"
