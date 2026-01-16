# Architectural Decision Records

Architectural Decision Records (ADRs) document significant technical decisions made during the development of Luminescent Cluster. They capture the context, decision, and consequences of each choice.

---

## Active ADRs

| ADR | Title | Status | Summary |
|-----|-------|--------|---------|
| [ADR-001](ADR-001-python-version-requirement-for-mcp-servers.md) | Python Version Requirement | Accepted v6 | Multi-layered defense against Pixeltable UDF serialization issues |
| [ADR-002](ADR-002-workflow-integration.md) | Workflow Integration | Accepted | Temporal workflow orchestration patterns |
| [ADR-003](ADR-003-project-intent-persistent-context.md) | Project Intent & Memory | Accepted v6.7 | Memory-first architecture with 4-phase implementation |
| [ADR-004](ADR-004-monetization-strategy.md) | Monetization Strategy | Accepted | Three-tier model: Free, Team, Enterprise |
| [ADR-005](ADR-005-repository-organization-strategy.md) | Repository Organization | Implemented | Dual-repo OSS/Paid separation with extension system |
| [ADR-006](ADR-006-chatbot-platform-integrations.md) | Chatbot Integrations | Accepted v1.1 | Slack, Discord, Telegram, WhatsApp support |
| [ADR-007](ADR-007-cross-adr-integration-guide.md) | Cross-ADR Integration | Accepted | Protocol consolidation and phase alignment |
| [ADR-008](ADR-008-docs-ledger-reconciliation.md) | MkDocs Documentation Site | Accepted v1.1 | MkDocs Material for public documentation |
| [ADR-009](ADR-009-spec-ledger-reconciliation.md) | Spec/Ledger Reconciliation | Accepted | Bidirectional requirement traceability |

---

## ADR Index by Topic

### Memory Architecture
- [ADR-003](ADR-003-project-intent-persistent-context.md) - Core memory system design
- [ADR-007](ADR-007-cross-adr-integration-guide.md) - Integration patterns

### Platform & Deployment
- [ADR-001](ADR-001-python-version-requirement-for-mcp-servers.md) - Python version safety
- [ADR-005](ADR-005-repository-organization-strategy.md) - OSS vs Paid separation

### Integrations
- [ADR-002](ADR-002-workflow-integration.md) - Temporal workflows
- [ADR-006](ADR-006-chatbot-platform-integrations.md) - Chat platform adapters

### Business
- [ADR-004](ADR-004-monetization-strategy.md) - Pricing tiers

### Documentation & Quality
- [ADR-008](ADR-008-docs-ledger-reconciliation.md) - MkDocs documentation site
- [ADR-009](ADR-009-spec-ledger-reconciliation.md) - Requirement traceability

---

## ADR Template

New ADRs should follow this structure:

```markdown
# ADR-NNN: Title

**Status**: Proposed | Accepted | Implemented | Deprecated
**Date**: YYYY-MM-DD
**Decision Makers**: Team/Council
**Version**: X.Y

## Decision Summary

Brief overview of the decision.

## Context

What problem are we solving? What constraints exist?

## Decision

What was decided and why.

## Consequences

### Positive
### Negative
### Mitigations

## Related Decisions

Links to other ADRs.

## Changelog

Version history.
```

---

## LLM Council Review Process

Significant ADRs undergo LLM Council review for:

1. **Design Review**: Architecture validation before implementation
2. **Implementation Verification**: Code review against ADR requirements
3. **Security Hardening**: Vulnerability assessment

Council configuration typically includes:
- Gemini-3-Pro
- Claude Opus 4.5
- Grok-4
- GPT-5.2-Pro

See [ADR-003](ADR-003-project-intent-persistent-context.md#council-review-summary) for an example of the review process.
