# ADR-005: Repository Organization Strategy (OSS vs Paid Separation)

**Status**: Implemented
**Date**: 2025-12-23
**Implemented**: 2025-12-23
**Decision Makers**: Development Team
**Owners**: @christopherjoseph
**Version**: 1.1 (Implemented)

## Implementation Summary

| Phase | Status | Details |
|-------|--------|---------|
| Phase 1: Prepare Public Repo | ✅ Complete | Extension system, integrations, CI/CD (121 tests) |
| Phase 2: Create Private Repo | ✅ Complete | CloudTenantProvider, StripeUsageTracker, CloudAuditLogger (58 tests) |
| Phase 3: Validate Separation | ✅ Complete | Cross-repo integration tests passing |

**Total Tests**: 179 (121 public + 58 private)

## Decision Summary

Adopt a **Dual Repository Model** to separate open-source core from proprietary paid features:

| Repository | Visibility | License | Purpose |
|------------|------------|---------|---------|
| `luminescent-cluster` | **Public** | Apache 2.0 | OSS core: MCP servers, local Pixeltable, single-user |
| `luminescent-cloud` | **Private** | Proprietary | Paid features: multi-tenancy, billing, hosted infra |

**Key Principle**: Public repo must be **fully functional for standalone deployments**. Paid features extend (not gate) the core.

---

## Context

### Why Separation is Necessary

ADR-004 established a three-tier monetization model:
- **Free**: Self-hosted, single-user, BYOK
- **Team**: $19/dev/month, hosted, shared team context
- **Enterprise**: $50k+ annual, VPC/on-prem, compliance

Clear separation enables:
1. **Community trust** via Apache 2.0 commitment
2. **IP protection** for paid differentiators
3. **Contributor clarity** on where PRs go

### Industry Precedent

| Company | Model | Notes |
|---------|-------|-------|
| GitLab | Dual repo (foss + ee) | Clear legal separation |
| Grafana | Dual repo (AGPL + proprietary) | Similar to our approach |
| Supabase | Monorepo + private services | Alternative for small teams |

---

## Feature Separation (Council Revised)

### The "Compute/Identity" Tiebreaker Rule

**Principle**: Features are FREE if they run on user compute with personal API keys. Features are PAID if they require Luminescent infrastructure or corporate identity management.

### Revised Feature Boundary

| Feature | OSS (Free) | Paid (Team/Enterprise) |
|---------|------------|------------------------|
| **Code Context** | Read-only GitHub/GitLab via PAT, Local FS | Org-level GitHub App, Write Access (PR Agent) |
| **Memory** | Local Pixeltable, semantic search | Managed Pixeltable, cloud storage |
| **Tenancy** | Single user (Local/Docker) | Multi-tenant, VPC isolation |
| **Security** | API Key auth | SSO/SAML, RBAC, data residency |
| **Telemetry** | Opt-in anonymous | Full usage metering & quotas |
| **Deployment** | Docker Compose, basic K8s | Production K8s (HA), managed hosting |
| **Integrations** | Personal webhooks (outbound) | Slack bidirectional, Linear, Jira |
| **Audit** | Local structured logs | Centralized audit logs (SOC2) |

### Why GitHub Integration is FREE (Council Mandated)

For an "AI-native development environment," reading code context is **functional necessity**, not enterprise feature:
- Without repo context, the memory architecture (ADR-003) loses its primary data source
- Competitors (Cursor, Cody, Continue) all offer free Git integration
- **Boundary**: Personal Access Token = FREE; Org-level OAuth App = PAID

---

## Repository Structure

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        PUBLIC: luminescent-cluster                       │
│                            (Apache 2.0 License)                          │
├─────────────────────────────────────────────────────────────────────────┤
│  src/                                                                    │
│  ├── session_memory_server.py    # Tier 1: Session Memory (git)         │
│  ├── pixeltable_mcp_server.py    # Tier 2: Long-term Memory             │
│  ├── pixeltable_setup.py         # Knowledge base setup                 │
│  ├── agent_tools.py              # Shared utilities                     │
│  ├── version_guard.py            # Python version safety                │
│  └── extensions/                 # Extension point protocols            │
│      ├── __init__.py                                                    │
│      ├── protocols.py            # TenantProvider, UsageTracker, etc.   │
│      └── registry.py             # ExtensionRegistry singleton          │
│                                                                          │
│  integrations/                   # FREE integrations                     │
│  ├── github_pat.py               # Read-only GitHub via PAT             │
│  └── gitlab_pat.py               # Read-only GitLab via PAT             │
│                                                                          │
│  docker-compose.yml              # Self-hosted deployment               │
│  Dockerfile.*                    # Container images                     │
│  k8s/                            # Basic K8s manifests                  │
│  docs/, examples/, scripts/      # Documentation                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ pip install luminescent-cluster
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       PRIVATE: luminescent-cloud                         │
│                          (Proprietary License)                           │
├─────────────────────────────────────────────────────────────────────────┤
│  cloud/                                                                  │
│  ├── extensions/                 # PAID extension implementations        │
│  │   ├── multi_tenant.py         # CloudTenantProvider                  │
│  │   └── stripe_tracker.py       # StripeUsageTracker                   │
│  ├── billing/                    # Subscription management              │
│  ├── auth/                       # SSO/SAML                             │
│  └── api/                        # Hosted API layer                     │
│                                                                          │
│  integrations/                   # PAID integrations                     │
│  ├── github_app/                 # Org-level GitHub App                 │
│  ├── slack_bidirectional/        # Slack with inbound commands          │
│  └── linear_jira/                # Issue tracker sync                   │
│                                                                          │
│  infra/                          # Proprietary infrastructure           │
│  ├── terraform/                  # AWS/GCP deployment                   │
│  ├── k8s-production/             # HA Kubernetes                        │
│  └── monitoring/                 # Observability stack                  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Extension Architecture (Council Revised)

### Protocol-Based Composition (NOT Inheritance)

The draft's inheritance pattern was flagged as an **antipattern** for cross-repo work. We adopt Protocol/Registry pattern instead.

#### Public Repo: Define Protocols

```python
# luminescent-cluster/src/extensions/protocols.py
from typing import Protocol, Optional
from dataclasses import dataclass

class TenantProvider(Protocol):
    """Extension point for multi-tenancy."""
    def get_tenant_id(self, request_context: dict) -> Optional[str]: ...
    def get_tenant_filter(self, tenant_id: str) -> dict: ...

class UsageTracker(Protocol):
    """Extension point for metering."""
    def track(self, operation: str, tokens: int, metadata: dict) -> None: ...

# luminescent-cluster/src/extensions/registry.py
@dataclass
class ExtensionRegistry:
    tenant_provider: Optional[TenantProvider] = None
    usage_tracker: Optional[UsageTracker] = None

    _instance: ClassVar[Optional['ExtensionRegistry']] = None

    @classmethod
    def get(cls) -> 'ExtensionRegistry':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
```

#### Private Repo: Inject Implementations

```python
# luminescent-cloud/cloud/extensions/multi_tenant.py
from luminescent_cluster.extensions import TenantProvider, ExtensionRegistry

class CloudTenantProvider:
    def get_tenant_id(self, ctx: dict) -> Optional[str]:
        return ctx.get("x-tenant-id")

    def get_tenant_filter(self, tenant_id: str) -> dict:
        return {"tenant_id": {"$eq": tenant_id}}

# At startup
def init_cloud_extensions():
    registry = ExtensionRegistry.get()
    registry.tenant_provider = CloudTenantProvider()
    registry.usage_tracker = StripeUsageTracker()
```

#### Usage in Core Code

```python
# luminescent-cluster/src/pixeltable_mcp_server.py
def handle_query(query: str, context: dict):
    registry = ExtensionRegistry.get()

    tenant_filter = {}
    if registry.tenant_provider:
        tenant_id = registry.tenant_provider.get_tenant_id(context)
        tenant_filter = registry.tenant_provider.get_tenant_filter(tenant_id)

    result = execute_query(query, tenant_filter)

    if registry.usage_tracker:
        registry.usage_tracker.track("query", len(query), {"tenant": tenant_id})

    return result
```

### Benefits of Protocol Pattern
- **No inheritance** - Composition over inheritance
- **Testable** - Mock extensions in public repo tests
- **Versioned** - Protocols versioned independently
- **Clean separation** - OSS code has no concept of tenancy

---

## Cross-Repo Operations

### Dependency Direction

```
luminescent-cloud (private)
         │
         │ pip install luminescent-cluster>=x.y.z
         ▼
luminescent-cluster (public)
```

**Critical Rule**: Private imports public as library. Public NEVER imports private.

### Development Workflow

1. **Sync Policy**: Private repo treats public as versioned pip dependency
2. **Local Development**: `make local-dev` installs public in editable mode (`pip install -e ../luminescent-cluster`)
3. **Upstream First**: All core bug fixes committed to public first. Private consumes releases.

### Cross-Repo Change Process

| Scenario | Process |
|----------|---------|
| Bug fix in core | PR to public → release → update private dependency |
| New extension point | PR to public (protocol) → PR to private (implementation) |
| Feature needs both | Coordinate: public PR first, private PR references it |

### Version Sync Automation

```yaml
# luminescent-cloud/.github/workflows/sync.yml
name: Sync Public Dependency
on:
  schedule:
    - cron: '0 0 * * 1'  # Weekly
jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - name: Update dependency
        run: pip install --upgrade luminescent-cluster
      - name: Run integration tests
        run: pytest tests/integration
      - name: Create PR if changes
        uses: peter-evans/create-pull-request@v5
```

---

## Database Migration Strategy (Council Required)

### Schema Ownership

| Component | Owner | Location |
|-----------|-------|----------|
| Schema definitions | PUBLIC | `luminescent-cluster/src/schemas/` |
| Migration scripts (local) | PUBLIC | `luminescent-cluster/migrations/` |
| Migration runners (cloud) | PRIVATE | `luminescent-cloud/migrations/` |

### Migration Flow

1. Schema changes originate in PUBLIC repo
2. PUBLIC provides migration scripts for local Pixeltable
3. PRIVATE repo adapts migrations for multi-tenant cloud DB
4. Version tags ensure schema compatibility

---

## Governance

### Feature Boundary Decision Framework

```
Feature Placement Decision Tree:

1. Does it require Luminescent-hosted infrastructure?
   YES → PAID (can't give away hosting costs)
   NO  → Continue

2. Does it require per-org data isolation or corporate identity?
   YES → PAID (multi-tenancy is complex)
   NO  → Continue

3. Is it a compliance checkbox feature? (SOC2, SSO, audit)
   YES → ENTERPRISE
   NO  → Continue

4. Does a solo developer need this on day 1?
   YES → FREE (adoption/activation feature)
   NO  → TEAM

DEFAULT: When uncertain, choose FREE
```

### Feature Boundary Disputes

**Tiebreaker**: "Who owns the compute/identity?"
- User's laptop + Personal API Key → **FREE**
- Luminescent Cloud + Corporate IdP → **PAID**

### Backporting Policy

No automatic backporting. Features move to lower tiers only if:
1. Competitors commoditize them (market pressure)
2. Security features (fast-track to free)

---

## Licensing & Legal

### Apache 2.0 Considerations

1. **CLA Required**: Implement Contributor License Agreement immediately
   - Ensures right to use contributions in proprietary tier
   - Use Apache-style ICLA (low friction, community-accepted)
   - Tool: CLA Assistant on GitHub

2. **Patent Grant Asymmetry**
   - Apache 2.0 includes patent grant to users
   - Proprietary license does not
   - Prepare standard patent grant language for enterprise contracts

3. **License Compliance**
   - Add license checker to CI
   - Pixeltable (Apache 2.0) ✓
   - MCP SDK (MIT) ✓

4. **Trademark Protection**
   - Apache doesn't cover trademarks
   - Register "Luminescent Cluster" branding

---

## Decision Triggers

### When to Revisit This ADR

| Trigger | Action |
|---------|--------|
| Team remains <4 developers for 12 months | Evaluate monorepo with build-time separation |
| Cross-repo coordination exceeds 20% of dev time | Consider monorepo migration |
| Community fork gains significant traction | Accelerate feature backporting |
| Major version drift between repos | Implement stricter sync automation |

---

## Migration Plan

### Phase 1: Prepare Public Repo (Week 1-2)

1. Create `luminescent-cluster` public repo
2. Move core files:
   - `session_memory_server.py`
   - `pixeltable_mcp_server.py`
   - `pixeltable_setup.py`
   - `src/version_guard.py`
   - `docs/`, `examples/`, `scripts/`
3. Add extension protocols (`src/extensions/`)
4. Add GitHub PAT integration
5. Add Apache 2.0 LICENSE
6. Set up CLA Assistant
7. Configure CI/CD for PyPI publishing

### Phase 2: Create Private Repo (Week 2-3)

1. Create `luminescent-cloud` private repo
2. Add `luminescent-cluster` as dependency
3. Implement extension providers:
   - `CloudTenantProvider`
   - `StripeUsageTracker`
4. Move infrastructure code:
   - `terraform/`
   - `k8s-production/`
5. Set up private CI/CD

### Phase 3: Validate Separation (Week 3-4)

1. Fresh clone of public repo works standalone
2. Private repo extends without modifying public
3. Integration tests pass across repos
4. Release process tested end-to-end

---

## Consequences

### Positive

- Clear value proposition for OSS users
- Apache 2.0 signals commitment to open source
- Contributor PRs go to public repo only
- Enterprise sales have clear upgrade path
- IP protection for paid differentiators

### Negative

- Two repos to maintain
- Version drift risk between repos
- CI/CD complexity doubles
- Cross-repo changes require coordination

### Mitigations

| Risk | Mitigation |
|------|------------|
| Version drift | Weekly automated sync CI job |
| Proprietary leak to public | Pre-commit hooks, CI license scanning |
| Contributor confusion | Clear CONTRIBUTING.md in both repos |
| Extension API instability | Semantic versioning, deprecation policy |

---

## Related Decisions

- **ADR-001**: Python Version Requirement
- **ADR-003**: Project Intent (architecture foundation)
- **ADR-004**: Monetization Strategy (pricing tiers this enables)

---

## Council Review Summary

**Review Date**: 2025-12-23
**Council Configuration**: High confidence (3 of 4 models responded)
**Models**: Gemini-3-Pro, Claude Opus 4.5, Grok-4

### Unanimous Recommendations (Incorporated)
1. Move GitHub/GitLab read-only integration to FREE tier
2. Replace inheritance pattern with Protocol/Registry (Composition)
3. Add CLA requirement for Apache 2.0 repo
4. Add "Compute/Identity" tiebreaker rule for feature disputes
5. Add decision triggers for reconsidering dual-repo
6. Add database migration strategy section

### Key Insights by Model
- **Gemini**: "Inheritance/hooks pollute OSS domain with tenancy concepts"
- **Claude**: "GitHub integration must be free; it's table-stakes for dev tools"
- **Grok**: "Add decision trigger to revisit if team <4 for 12 months"

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-23 | Initial council-validated version with dual-repo strategy, Protocol/Registry extension pattern, and "Compute/Identity" tiebreaker rule |
