# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
Root pytest configuration with shared fixtures and markers.

This file is automatically loaded by pytest and provides:
- Custom markers for requirement traceability (ADR-009)
- Shared fixtures for common test patterns
- Test collection customization

See ADR-009 for the spec/ledger reconciliation system design.
"""

import pytest


def pytest_configure(config):
    """Register custom markers for requirement traceability."""
    # Requirement traceability markers (ADR-009)
    config.addinivalue_line(
        "markers",
        "requirement(req_id): Link test to a requirement ID (e.g., REQ-MCP-001)",
    )

    # Priority markers
    config.addinivalue_line(
        "markers",
        "critical: Mark test as critical priority (100% coverage required)",
    )
    config.addinivalue_line(
        "markers",
        "high: Mark test as high priority (95% coverage required)",
    )
    config.addinivalue_line(
        "markers",
        "medium: Mark test as medium priority (85% coverage required)",
    )
    config.addinivalue_line(
        "markers",
        "low: Mark test as low priority (75% coverage required)",
    )

    # Test category markers
    config.addinivalue_line(
        "markers",
        "integration: Mark test as integration test (cross-system)",
    )
    config.addinivalue_line(
        "markers",
        "security: Mark test as security-related",
    )
    config.addinivalue_line(
        "markers",
        "performance: Mark test as performance benchmark",
    )
    config.addinivalue_line(
        "markers",
        "slow: Mark test as slow-running (may be skipped in quick runs)",
    )


# ============================================================================
# Shared Fixtures
# ============================================================================


@pytest.fixture
def temp_user_id():
    """Generate a temporary user ID for isolation tests."""
    import uuid

    return f"test-user-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def temp_agent_id():
    """Generate a temporary agent ID for MaaS tests."""
    import uuid

    return f"test-agent-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def temp_session_id():
    """Generate a temporary session ID for context tests."""
    import uuid

    return f"test-session-{uuid.uuid4().hex[:8]}"


# ============================================================================
# Test Collection Hooks
# ============================================================================


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add automatic markers based on paths."""
    for item in items:
        # Auto-mark tests by directory
        if "security" in str(item.fspath):
            item.add_marker(pytest.mark.security)
        if "benchmarks" in str(item.fspath):
            item.add_marker(pytest.mark.performance)
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
