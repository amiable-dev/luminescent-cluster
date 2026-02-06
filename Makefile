# Makefile for Luminescent Cluster
# Copyright 2024-2026 Amiable Development
# SPDX-License-Identifier: Apache-2.0

.PHONY: help install install-all test lint format docs validate-ledger validate-all clean build publish-test publish

# Default target
help:
	@echo "Luminescent Cluster - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install          Install core + dev dependencies"
	@echo "  make install-all      Install all optional dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  make test             Run all tests"
	@echo "  make test-fast        Run tests (skip slow tests)"
	@echo "  make test-coverage    Run tests with coverage"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint             Run linter (ruff)"
	@echo "  make format           Format code (ruff format)"
	@echo ""
	@echo "Build & Publish:"
	@echo "  make build            Build package (wheel + sdist)"
	@echo "  make publish-test     Publish to Test PyPI"
	@echo "  make publish          Publish to PyPI"
	@echo ""
	@echo "Documentation:"
	@echo "  make docs             Serve documentation locally"
	@echo "  make docs-build       Build documentation"
	@echo ""
	@echo "Validation (ADR-009, ADR-010):"
	@echo "  make validate-ledger  Run spec/ledger reconciliation"
	@echo "  make validate-docs    Run documentation freshness checks"
	@echo "  make validate-all     Run all validations"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean            Clean build artifacts"

# =============================================================================
# Setup
# =============================================================================

install:
	uv pip install -e ".[dev]"

install-all:
	uv pip install -e ".[dev,pixeltable,summarization,docs]"

# =============================================================================
# Testing
# =============================================================================

test:
	pytest tests/ -v --ignore=tests/test_pixeltable_mcp_server.py

test-fast:
	pytest tests/ -v --ignore=tests/test_pixeltable_mcp_server.py -m "not slow"

test-coverage:
	pytest tests/ -v --cov=luminescent_cluster --ignore=tests/test_pixeltable_mcp_server.py

# =============================================================================
# Code Quality
# =============================================================================

lint:
	ruff check .

format:
	ruff format .

lint-fix:
	ruff check --fix .

# =============================================================================
# Build & Publish
# =============================================================================

build:
	uv build

publish-test: build
	uv publish --repository testpypi

publish: build
	uv publish

# =============================================================================
# Documentation
# =============================================================================

docs:
	mkdocs serve

docs-build:
	mkdocs build --strict

# =============================================================================
# Validation (ADR-009, ADR-010)
# =============================================================================

# Run spec/ledger reconciliation with all checks
validate-ledger:
	@echo "Running spec/ledger reconciliation (ADR-009, ADR-010)..."
	python spec/validation/reconcile.py --verbose --check-skips --check-orphans

# Run spec/ledger reconciliation in warning mode (always exit 0)
validate-ledger-warn:
	python spec/validation/reconcile.py --warn --verbose --check-skips --check-orphans

# Run spec/ledger reconciliation in strict mode (warnings are failures)
validate-ledger-strict:
	python spec/validation/reconcile.py --strict --verbose --check-skips --check-orphans

# Run documentation freshness checks
validate-docs:
	@echo "Running documentation freshness checks (ADR-010)..."
	python spec/validation/doc_freshness.py --all --verbose

# Check documentation links only
validate-links:
	python spec/validation/doc_freshness.py --check-links --verbose

# Check ADR-ledger synchronization only
validate-adr-sync:
	python spec/validation/doc_freshness.py --check-adr-sync --verbose

# Run all validations
validate-all: validate-ledger validate-docs
	@echo ""
	@echo "All validations complete!"

# Update baseline coverage (only after intentional improvements)
update-baseline:
	python spec/validation/reconcile.py --update-baseline --verbose

# =============================================================================
# Utilities
# =============================================================================

clean:
	rm -rf .pytest_cache
	rm -rf __pycache__
	rm -rf .ruff_cache
	rm -rf site/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf src/luminescent_cluster/_version.py
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
