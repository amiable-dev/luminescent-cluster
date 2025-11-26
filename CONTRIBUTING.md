# Contributing to Context-Aware AI System

Thank you for your interest in contributing!

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/context-aware-ai-system.git`
3. Create a branch: `git checkout -b feature/your-feature-name`
4. Make your changes
5. Run tests: `python test_setup.py`
6. Commit: `git commit -am 'Add some feature'`
7. Push: `git push origin feature/your-feature-name`
8. Create a Pull Request

## Development Setup

```bash
./quickstart.sh
```

This will:
- Create a virtual environment
- Install dependencies
- Run verification tests

## Code Style

- Follow PEP 8 for Python code
- Use type hints where appropriate
- Add docstrings to all functions and classes
- Keep functions focused and single-purpose

## Testing

Before submitting a PR:

1. Run the test suite: `python test_setup.py`
2. Test your MCP server manually
3. Verify no regressions in existing functionality

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
- Update `context-aware-ai-system.md` for architectural changes

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

By contributing, you agree that your contributions will be licensed under the MIT License.
