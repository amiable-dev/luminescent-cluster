# Contributing to Luminescent Cluster

Thank you for your interest in contributing!

## Contributor License Agreement (CLA)

Before your contribution can be accepted, you must sign the Contributor License Agreement (CLA).

When you open your first Pull Request, the CLA Assistant bot will automatically comment with a link to sign the CLA. This is a one-time process that takes about 2 minutes.

**Why a CLA?**
- Ensures the project can be licensed under Apache 2.0
- Protects both contributors and users
- Required for dual-licensing flexibility (per ADR-005)

The CLA is based on the Apache Individual Contributor License Agreement and grants the project a perpetual, royalty-free license to use your contributions.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/luminescent-cluster.git`
3. Create a branch: `git checkout -b feature/your-feature-name`
4. Make your changes
5. Run tests: `pytest tests/ -v`
6. Commit: `git commit -am 'Add some feature'`
7. Push: `git push origin feature/your-feature-name`
8. Create a Pull Request (CLA Assistant will guide you through signing if needed)

## Development Setup

### Python Version Requirements (CRITICAL)

**The Pixeltable database is bound to the Python version that created it.** Using a different Python minor version will cause a silent segmentation fault.

```bash
# Check .python-version file for required version
cat .python-version  # Should show 3.11

# Use pyenv, mise, or uv to install the correct version
pyenv install 3.11.9
pyenv local 3.11.9

# Or with uv
uv venv --python 3.11
source .venv/bin/activate
```

See [ADR-001](docs/adrs/ADR-001-python-version-requirement-for-mcp-servers.md) for full details on this constraint.

### Quick Start

```bash
./quickstart.sh
```

This will:
- Create a virtual environment with the correct Python version
- Install dependencies
- Run verification tests

## Code Style

- Follow PEP 8 for Python code
- Use type hints where appropriate
- Add docstrings to all functions and classes
- Keep functions focused and single-purpose

## Testing

Before submitting a PR:

1. Run the test suite:
   ```bash
   # Run all tests (121 tests)
   pytest tests/ -v --ignore=tests/test_pixeltable_mcp_server.py

   # Run specific test file
   pytest tests/test_version_guard.py -v

   # Run with coverage
   pytest tests/ -v --cov=src --cov=integrations
   ```
2. Test your MCP server manually
3. Verify no regressions in existing functionality
4. Ensure Python version guard tests pass (ADR-001)
5. Run spec/ledger reconciliation (see Requirement Traceability below)

## Requirement Traceability

Tests should be linked to requirements using pytest markers. See [ADR-009](docs/adrs/ADR-009-spec-ledger-reconciliation.md) for the full system design.

### Using Requirement Markers

```python
import pytest

@pytest.mark.requirement("REQ-MCP-001")
def test_version_mismatch_exit_code():
    """Requirement: Version mismatch should exit with code 78."""
    # Test implementation
    pass
```

### Verifying Requirement Coverage

```bash
# Run reconciliation to check requirement coverage
python spec/validation/reconcile.py --verbose

# Expected output: Reconciliation PASSED!
# Coverage by Priority:
#   Critical   100.0% (threshold: 100%) [OK]
#   High       100.0% (threshold: 95%) [OK]
#   Medium     100.0% (threshold: 85%) [OK]
#   Low        100.0% (threshold: 75%) [OK]
```

### Adding New Requirements

When adding new functionality:

1. Add requirement to `spec/ledger.yml`:
   ```yaml
   REQ-XXX-NNN:
     title: "Your Requirement Title"
     source: "ADR-NNN"
     status: active
     priority: high  # critical | high | medium | low
     tests:
       - tests/path/to/test.py::test_function
   ```

2. Add test with requirement marker:
   ```python
   @pytest.mark.requirement("REQ-XXX-NNN")
   def test_function():
       pass
   ```

3. Verify coverage:
   ```bash
   python spec/validation/reconcile.py
   ```

### Available Markers

| Marker | Description |
|--------|-------------|
| `@pytest.mark.requirement("REQ-XXX-NNN")` | Link test to requirement |
| `@pytest.mark.critical` | Critical priority test |
| `@pytest.mark.high` | High priority test |
| `@pytest.mark.medium` | Medium priority test |
| `@pytest.mark.low` | Low priority test |
| `@pytest.mark.integration` | Cross-system integration test |
| `@pytest.mark.security` | Security-related test |
| `@pytest.mark.performance` | Performance benchmark |
| `@pytest.mark.slow` | Slow-running test |

## Areas for Contribution

### High Priority

- **GitHub PR Integration**: Add PR context to session memory
- **Cost Tracking**: Monitor embedding generation and API costs
- **Web UI**: Build interface for knowledge base management
- **Metrics Dashboard**: Track token usage, query performance

### Medium Priority

- **Additional Embeddings**: Support for OpenAI, Cohere embeddings
- **Multimodal Expansion**: Image analysis, video processing
- **Access Control**: Fine-grained permissions for sensitive data
- **Export/Import**: Backup and restore knowledge base

### Nice to Have

- **Slack Integration**: Ingest Slack conversations
- **Jira Integration**: Link tickets to code changes
- **Auto-tagging**: ML-based topic classification
- **Query Caching**: Speed up repeated searches

## Automation Opportunities

A key challenge with persistent knowledge bases is keeping them current. Here are natural integration points where automation can eliminate manual work:

### Git-Based Automation (High Impact)

**Problem**: Humans forget to re-ingest code after changes  
**Solution**: Hook into existing git workflows

#### Post-Merge Hook
```bash
# .git/hooks/post-merge
#!/bin/bash
if [ "$(git rev-parse --abbrev-ref HEAD)" = "main" ]; then
  # Trigger ingestion via helper script (background)
  ~/.mcp-servers/context-aware-ai-system/scripts/ingest.sh &
fi
```

**Trigger**: PR merged to main  
**Benefit**: Knowledge base stays synced with main branch

#### Post-Tag Hook
```bash
# .git/hooks/post-tag
#!/bin/bash
TAG_NAME=$(git describe --tags)
# Create snapshot via MCP tool (conceptually)
# In practice, use the helper script which now supports snapshots
~/.mcp-servers/context-aware-ai-system/scripts/snapshot.sh "$TAG_NAME"

```

**Trigger**: Git tag created (release)  
**Benefit**: Snapshots + re-ingestion at natural checkpoints

### CI/CD Integration

Add to GitHub Actions, GitLab CI, or Jenkins:

```yaml
# .github/workflows/update-kb.yml
name: Update Knowledge Base
on:
  push:
    branches: [main]
jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - name: Re-ingest codebase
        run: |
          docker-compose exec -T pixeltable-memory python -c "
          from pixeltable_setup import setup_knowledge_base, ingest_codebase
          kb = setup_knowledge_base()
          ingest_codebase(kb, '/repos', 'my-service')
          "
```

### ADR Auto-Ingestion

Monitor `docs/adr/` for new ADRs:

```bash
# .git/hooks/post-commit
git diff --name-only HEAD~1 HEAD | grep 'docs/adr/.*\.md' | while read file; do
  # Ingest ADR via helper script
  ~/.mcp-servers/context-aware-ai-system/scripts/ingest_adr.sh "$file" &
done
```

**Benefit**: New decisions are immediately searchable

### Scheduled Sync (Safety Net)

```bash
# crontab: Run nightly at 2 AM
0 2 * * * ~/.mcp-servers/context-aware-ai-system/scripts/ingest-all-projects.sh
```


**Benefit**: Catches anything missed by other triggers

### Recommended Implementation Order

1. **Start**: Post-merge hook (highest ROI)
2. **Add**: Weekly cron job (safety net)
3. **Enhance**: Git tag snapshots (versioning)
4. **Advanced**: CI/CD integration, ADR monitoring

**Key Principle**: Hook into existing developer workflows rather than requiring new manual steps.


## MCP Server Development

When adding new tools:

1. Define the tool in `list_tools()`
2. Implement the handler in `call_tool()`
3. Add error handling
4. Update documentation
5. Consider if it should be defer-loaded

Example:

```python
Tool(
    name="your_new_tool",
    description="Clear description of what it does",
    inputSchema={
        "type": "object",
        "properties": {
            "param": {
                "type": "string",
                "description": "Parameter description"
            }
        },
        "required": ["param"]
    }
)
```

## Documentation

- Update README.md for user-facing changes
- Add inline comments for complex logic
- Create examples in `examples/` directory
- Update docs/adrs/ for architectural changes

## Commit Messages

Use conventional commits:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `refactor:` Code refactoring
- `test:` Test additions or changes
- `chore:` Maintenance tasks

Example: `feat: add GitHub PR integration to session memory`

## Questions?

Open an issue for:
- Bug reports
- Feature requests
- Questions about architecture
- Implementation help

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.

## CLA Setup for Maintainers

To set up CLA Assistant on this repository:

1. Go to https://cla-assistant.io/
2. Sign in with GitHub
3. Add this repository: `amiable-dev/luminescent-cluster`
4. Create a CLA gist with the Apache ICLA content
5. Configure the webhook

The CLA Assistant will automatically:
- Comment on new PRs from first-time contributors
- Block merging until the CLA is signed
- Track all signatures in a private gist
