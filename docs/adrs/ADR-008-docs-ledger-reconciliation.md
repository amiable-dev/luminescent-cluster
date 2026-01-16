# ADR-008: MkDocs Documentation Site

**Status**: Accepted
**Date**: 2026-01-16
**Decision Makers**: Development Team
**Owners**: @christopherjoseph
**Version**: 1.1

## Decision Summary

Adopt MkDocs with Material theme for public documentation at `luminescent-cluster.dev`, providing unified navigation, search, and GitHub Pages deployment for all project documentation.

| Aspect | Decision |
|--------|----------|
| Generator | MkDocs with Material theme |
| Hosting | GitHub Pages |
| Deployment | GitHub Actions on push to main |
| Exit Criteria | `mkdocs build --strict` passes |

---

## Context

### The Problem: Fragmented Documentation

Luminescent Cluster has accumulated significant documentation across multiple formats:
- 7+ ADRs with detailed technical decisions
- 8 blog posts explaining architecture
- 3 memory system docs
- 1 operations runbook
- Multiple root-level guides (README, CONTRIBUTING, etc.)

**Pain Points**:
1. No unified documentation site for users
2. No way to navigate between related documents
3. No search functionality across documentation
4. Users must browse raw GitHub to find information
5. No consistent formatting or styling

### Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| **MkDocs Material** | Fast, search, Material Design, wide adoption | Python-based | **Selected** |
| Docusaurus | React-based, versioning | Heavier, JS ecosystem | Rejected |
| Sphinx | Python standard, RST | Steeper learning curve | Rejected |
| GitHub Wiki | Zero setup | Poor UX, no search | Rejected |
| ReadTheDocs | Free hosting | Less customizable | Rejected |

**Decision Driver**: MkDocs Material provides the best balance of simplicity, features, and Python ecosystem alignment.

---

## Decision

### Site Structure

```
docs/
├── index.md                    # Home page with feature cards
├── getting-started/
│   ├── index.md                # Section overview
│   ├── installation.md         # Install guide
│   ├── quickstart.md           # 5-minute quickstart
│   └── configuration.md        # Configuration reference
├── architecture/
│   ├── index.md                # Architecture overview
│   ├── overview.md             # System architecture
│   └── memory-tiers.md         # Tier deep-dive
├── mcp/
│   ├── index.md                # MCP servers overview
│   ├── session-memory.md       # Session memory tools
│   └── pixeltable-memory.md    # Pixeltable tools
├── memory/
│   ├── index.md                # Memory system index
│   ├── overview.md             # Memory architecture
│   ├── providers.md            # Provider extension guide
│   └── maas.md                 # MaaS documentation
├── adrs/
│   ├── index.md                # ADR index with status
│   └── ADR-*.md                # Individual ADRs
├── blog/
│   ├── index.md                # Blog index
│   └── *.md                    # Blog posts
└── operations/
    ├── index.md                # Operations index
    └── memory-runbook.md       # Runbook
```

### Configuration

```yaml
# mkdocs.yml (key sections)
site_name: Luminescent Cluster
site_url: https://amiable-dev.github.io/luminescent-cluster
repo_url: https://github.com/amiable-dev/luminescent-cluster

theme:
  name: material
  features:
    - navigation.tabs          # Top-level tabs
    - navigation.sections      # Collapsible sections
    - navigation.expand        # Auto-expand
    - navigation.indexes       # Section index pages
    - search.suggest           # Search suggestions
    - search.highlight         # Highlight matches
    - content.code.copy        # Copy code blocks
  palette:
    - scheme: default
      primary: indigo
      toggle:
        icon: material/brightness-7
        name: Switch to dark mode
    - scheme: slate
      primary: indigo
      toggle:
        icon: material/brightness-4
        name: Switch to light mode

plugins:
  - search
  - tags

markdown_extensions:
  - admonition               # Note/warning boxes
  - pymdownx.details         # Collapsible blocks
  - pymdownx.superfences     # Code fences
  - pymdownx.tabbed          # Tabbed content
  - pymdownx.highlight       # Syntax highlighting
  - tables                   # Markdown tables
  - toc:
      permalink: true        # Anchor links
```

### Deployment

GitHub Actions workflow (`.github/workflows/docs.yml`):

```yaml
name: Documentation
on:
  push:
    branches: [main]
    paths: ['docs/**', 'mkdocs.yml']

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install mkdocs-material
      - run: mkdocs build --strict
      - uses: actions/upload-pages-artifact@v3
        with:
          path: ./site

  deploy:
    if: github.ref == 'refs/heads/main'
    needs: build
    environment:
      name: github-pages
    runs-on: ubuntu-latest
    steps:
      - uses: actions/deploy-pages@v4
```

---

## Consequences

### Positive
- **Discoverability**: Users find documentation via search
- **Navigation**: Consistent cross-linking between docs
- **Aesthetics**: Material Design provides professional appearance
- **Maintenance**: Markdown files easy to update
- **Automation**: Auto-deploy on merge to main

### Negative
- **Build Step**: Requires build before preview
- **Python Dependency**: Adds mkdocs-material to dev dependencies
- **Learning Curve**: Contributors must learn MkDocs conventions

### Mitigations
- `mkdocs serve` for instant local preview
- Document MkDocs conventions in CONTRIBUTING.md
- Use strict mode to catch broken links early

---

## Verification

```bash
# Install
pip install mkdocs-material

# Build with strict mode (fails on warnings)
mkdocs build --strict

# Local preview
mkdocs serve  # http://localhost:8000
```

---

## Related Decisions

- **ADR-009**: Spec/Ledger Reconciliation System (companion ADR)
- **ADR-003**: Memory Architecture (documented in site)
- **ADR-005**: Repository Organization (OSS docs strategy)

---

## Council Review

**Review Date**: 2026-01-16
**Verdict**: Sound and accepted with amendments
**Consensus Strength**: 0.85

### Key Recommendations

1. **Add mkdocstrings Plugin** (High Priority)
   - Enables automatic API reference generation from docstrings
   - Reduces documentation drift from code
   - Action: Add to `plugins` section in mkdocs.yml

2. **Add mike Plugin for Versioning** (Medium Priority)
   - Supports multiple documentation versions (e.g., v1.0, v1.1, latest)
   - Critical for OSS projects with multiple release lines
   - Action: Add mike to plugins, configure aliases

3. **Restructure MCP Section** (Medium Priority)
   - Current flat structure insufficient for growth
   - Recommended structure:
     ```
     mcp/
     ├── index.md          # Overview
     ├── quickstart.md     # 5-minute setup
     ├── servers/
     │   ├── session-memory.md
     │   └── pixeltable-memory.md
     └── protocol-specs/   # Protocol documentation
     ```

4. **Add Secrets Scanner** (High Priority)
   - Operations documentation may contain example configs
   - Integrate trufflehog or gitleaks in CI
   - Action: Add to docs.yml workflow

5. **Pin GitHub Actions by SHA** (Security)
   - Use `actions/checkout@<sha>` instead of `@v4`
   - Prevents supply chain attacks via tag mutation
   - Action: Update all action references

6. **Strict Mode Already Implemented** (Confirmed)
   - `mkdocs build --strict` already in workflow
   - No action required

### Accepted Amendments

| Amendment | Status | Target |
|-----------|--------|--------|
| mkdocstrings plugin | Deferred | Phase 4 |
| mike versioning | Deferred | Phase 4 |
| MCP restructure | Deferred | Phase 4 |
| Secrets scanner | Accepted | docs.yml |
| Pin actions by SHA | Accepted | docs.yml |

### Dissenting Opinion

One council member noted that mike versioning adds complexity for a pre-1.0 project. Recommendation: defer until v1.0 release when versioned docs become necessary.

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-16 | Initial ADR (combined with ledger) |
| 1.1 | 2026-01-16 | Split from ADR-008, focused on MkDocs only |
