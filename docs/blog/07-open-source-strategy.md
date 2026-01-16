# Open Source Strategy: What's Free and Why

**We open-sourced the core of Luminescent under Apache 2.0. Here's what that means for you, how we decide what's free vs paid, and why we think this model works.**

---

"Will this stay free?" is the first question engineers ask when evaluating open-source tools. Fair question. Too many projects bait-and-switch: start open, build a community, then pull features behind paywalls.

Here's our commitment: **The core memory architecture is Apache 2.0 and will stay that way.** You can self-host Luminescent forever, contribute to it, fork it, even build competing products on it.

But we're also a company that needs revenue to keep developing. This post explains exactly where the free/paid line is, why it's there, and how we designed the architecture to keep that line clean.

## The License: Apache 2.0

We chose Apache 2.0 for the public repository. Here's why:

| License | Pros | Cons | Our Take |
|---------|------|------|----------|
| **MIT** | Simple, permissive | No patent protection | Too risky for enterprise adoption |
| **Apache 2.0** | Permissive + patent grant | Slightly more complex | Best balance for enterprise + community |
| **AGPL** | Strong copyleft, SaaS protection | Scares away enterprise | Kills adoption before it starts |
| **BSL/SSPL** | Prevents cloud competition | Not OSI-approved, trust issues | We want real open source |

**Apache 2.0 gives you:**
- Perpetual, worldwide license to use, modify, and distribute
- Patent protection (we can't sue you for using patents in our code)
- Freedom to use in proprietary products
- No requirement to open-source your modifications

**What it doesn't give:**
- Rights to our trademarks ("Luminescent Cluster" is separately registered)
- Access to our cloud infrastructure
- Multi-tenant features (those are proprietary)

## The Model: Open Core

We use an **open-core** model with two repositories:

```
PUBLIC: luminescent-cluster (Apache 2.0)
+----------------------------------------------+
|  Session Memory MCP Server                   |
|  Pixeltable MCP Server                       |
|  Memory architecture (all 5 phases)          |
|  Chatbot adapters (Discord, Slack, etc.)     |
|  Git hooks & Agent Skills                    |
|  Single-user deployment (Docker, local)      |
|  166+ tests                                  |
+----------------------------------------------+
           |
           | imports as pip library
           v
PRIVATE: luminescent-cloud (Proprietary)
+----------------------------------------------+
|  Multi-tenant isolation                      |
|  Billing & usage metering                    |
|  SSO/SAML integration                        |
|  Enterprise audit logging                    |
|  Managed cloud hosting                       |
|  Advanced integrations (GitHub App, etc.)    |
+----------------------------------------------+
```

**Key rule:** Private imports public. Never the reverse. The open-source codebase has zero knowledge of cloud concepts.

## The Tiebreaker: Compute vs Identity

How do we decide what's free vs paid? We use a simple rule:

> **If it runs on your compute with your API keys, it's free.**
> **If it requires our infrastructure or corporate identity management, it's paid.**

This isn't arbitrary—it's grounded in where value actually lives.

### What's Always Free

| Feature | Why It's Free |
|---------|---------------|
| Memory storage & retrieval | Runs on your machine |
| Semantic search (HybridRAG) | Your Pixeltable instance |
| Git context loading | Your repository, your PAT |
| Chatbot adapters | Your bot tokens, your servers |
| Agent Skills | YAML files in your repo |
| LLM integration | Your API keys (OpenAI, Anthropic, etc.) |

You bring your own API keys, you run on your own infrastructure, you own your data. We provide the software; you provide the compute.

### What's Paid

| Feature | Why It's Paid |
|---------|---------------|
| Multi-tenancy | Requires our isolation infrastructure |
| Managed hosting | We run the servers |
| SSO/SAML | Corporate identity integration |
| Usage metering & billing | Stripe integration, quota enforcement |
| GitHub App (org-level) | OAuth flow requires our registered app |
| Audit logging (SOC2) | Compliance infrastructure |
| SLA guarantees | Requires operational investment |

These features require us to run infrastructure, maintain compliance certifications, or provide ongoing operational support. That costs money.

## The Three Tiers

### Free (Self-Hosted)

**Who it's for:** Individual developers, small teams evaluating the product

**What you get:**
- Full memory architecture (all 5 ADR-003 phases)
- Session Memory + Pixeltable MCP servers
- Single-user deployment via Docker Compose
- GitHub/GitLab integration (read-only via PAT)
- All chatbot adapters
- Community support (GitHub Issues)

**What you provide:**
- Your own compute (local machine, VPS, etc.)
- Your own API keys (LLM providers, GitHub PAT)
- Your own Pixeltable database

**Limitations:**
- Single user (no shared team context)
- No SSO (API key auth only)
- No usage quotas (self-manage your LLM costs)
- Community support only

### Team ($19/dev/month)

**Who it's for:** Engineering teams of 10-200 developers

**What you get (in addition to Free):**
- Multi-tenant isolation (team workspaces)
- Shared team context (everyone sees the same ADRs, incidents)
- Managed Pixeltable hosting
- GitHub App integration (org-level, write access)
- 1M tokens/workspace/month included
- Email support (24-hour SLA)

**Why teams pay:**
- Don't want to run infrastructure
- Need shared context across the team
- Want write access for PR automation
- Prefer predictable pricing over BYOK LLM costs

### Enterprise ($50k+/year)

**Who it's for:** Regulated industries, large organizations

**What you get (in addition to Team):**
- VPC deployment or on-premises
- SSO/SAML integration
- Advanced RBAC
- SOC2-compliant audit logging
- Data residency options
- Unlimited tokens
- Dedicated CSM
- SLA with uptime guarantees

**Why enterprises pay:**
- Compliance requirements (SOC2, HIPAA)
- Security policies requiring SSO
- Data residency constraints
- Need for guaranteed uptime

## Extension Points: Clean Separation

How do we add paid features without polluting the open-source codebase? **Protocols and registries.**

### The Pattern

```python
# 1. PUBLIC REPO: Define the protocol (interface)
from typing import Protocol, runtime_checkable

@runtime_checkable
class TenantProvider(Protocol):
    """Protocol for multi-tenancy. OSS code is tenant-unaware."""

    def get_tenant_id(self, context: dict) -> str:
        """Extract tenant ID from request context."""
        ...

    def get_tenant_filter(self, tenant_id: str) -> dict:
        """Return filter to scope queries to tenant."""
        ...
```

```python
# 2. PRIVATE REPO: Implement the protocol
class CloudTenantProvider:
    """Proprietary implementation for cloud hosting."""

    def get_tenant_id(self, context: dict) -> str:
        # Extract from OAuth token
        return context.get("x-tenant-id", "default")

    def get_tenant_filter(self, tenant_id: str) -> dict:
        return {"tenant_id": tenant_id}
```

```python
# 3. PUBLIC REPO: Check gracefully at runtime
from src.extensions import ExtensionRegistry

def retrieve_memories(query: str, context: dict) -> list[Memory]:
    registry = ExtensionRegistry.get()

    # If multi-tenancy is available (cloud), use it
    if registry.tenant_provider:
        tenant_id = registry.tenant_provider.get_tenant_id(context)
        tenant_filter = registry.tenant_provider.get_tenant_filter(tenant_id)
        return search(query, filters=tenant_filter)

    # OSS mode: no tenant filtering
    return search(query)
```

### Why This Works

1. **No inheritance pollution:** OSS code doesn't import cloud code
2. **Graceful degradation:** Missing extensions = OSS behavior
3. **Clear contracts:** Protocols define exactly what's expected
4. **Testable:** Mock implementations in OSS tests
5. **Composable:** Multiple extensions can be registered

### Extension Points

| Extension | Protocol | OSS Default | Cloud Implementation |
|-----------|----------|-------------|---------------------|
| Tenancy | `TenantProvider` | No filtering | `CloudTenantProvider` |
| Billing | `UsageTracker` | No tracking | `StripeUsageTracker` |
| Audit | `AuditLogger` | Local logs | `CloudAuditLogger` |
| Access | `AccessController` | Allow all | `CloudAccessController` |

## Why Open Core Works

We're not inventing a new business model. Open core is proven:

| Company | Core Product | Proprietary Layer | Outcome |
|---------|--------------|-------------------|---------|
| **GitLab** | Git hosting, CI/CD | Enterprise features, SaaS | $14B IPO |
| **Grafana** | Visualization, alerting | Enterprise plugins, cloud | $6B valuation |
| **Supabase** | Postgres, Auth, Storage | Managed hosting, enterprise | $2B valuation |
| **HashiCorp** | Terraform, Vault, Consul | Enterprise features, cloud | $5B acquisition |

The pattern is consistent:

1. **Build trust with OSS:** Developers evaluate and adopt freely
2. **Prove value at individual level:** Free tier validates product-market fit
3. **Monetize at team/org level:** Teams pay for collaboration, enterprises pay for compliance
4. **Accumulate switching costs:** The longer you use it, the harder it is to leave

## The Moat: Accumulated Context

Here's why we're confident in this model:

```
Day 1:   Luminescent knows your codebase structure
Day 30:  Luminescent knows your ADRs and why decisions were made
Day 90:  Luminescent knows your patterns, preferences, and team conventions
Day 365: Luminescent knows your org better than most employees
```

At Day 365, switching to a competitor means starting over from zero. Your accumulated context—the decisions, incidents, patterns, preferences—is locked in your Luminescent instance.

This is the Slack/Notion playbook: the product gets more valuable over time because your data is in it. The difference is that with Luminescent, you can always export and self-host. We don't hold your data hostage; we earn your continued payment by providing value.

## Contributing

We accept contributions to the public repository under our CLA (Contributor License Agreement).

**Why CLA?** The CLA grants us the right to use contributions in both the open-source and proprietary tiers. Without it, we couldn't include community contributions in the cloud product.

**What the CLA says:**
- You retain copyright of your contributions
- You grant us a perpetual license to use, modify, and distribute (including in proprietary products)
- You confirm the contribution is your original work (or properly licensed)
- We commit to keeping your contribution available under Apache 2.0

**What the CLA doesn't say:**
- We don't claim ownership of your code
- We don't restrict your use of your own contributions
- We don't require assignment of copyright

The CLA is standard for open-core companies (Docker, MongoDB, HashiCorp use similar agreements). If this is a blocker, you can still use the software—you just can't contribute upstream.

**What you can contribute:**
- Bug fixes
- New features for the core product
- Documentation improvements
- Test coverage
- New chatbot adapters
- Memory provider implementations

**What you can't contribute:**
- Features that depend on proprietary code
- Cloud-specific functionality
- Anything that would break the OSS/cloud separation

**Protected paths:**
- `.claude/skills/` - Agent Skills are executable code (security review required)
- `.agent/hooks/` - Git hooks (security critical)
- `src/extensions/` - Extension protocols (architectural review required)

## Our Commitments

### What will stay free forever

1. **The memory architecture** - Session Memory, Pixeltable integration, HybridRAG retrieval
2. **Single-user deployment** - Docker Compose, local development
3. **MCP server protocols** - The standard for tool integration
4. **Chatbot adapters** - Discord, Slack, Telegram, WhatsApp
5. **Git integration** - Hooks, context loading, PAT-based auth

### What might become free

Features move to lower tiers when:
- Competitors commoditize them (market pressure)
- They become table stakes (user expectations)
- We develop newer premium features (product evolution)

We won't move features up the pricing ladder. If something is free today, it stays free.

### What will stay paid

1. **Multi-tenancy** - Fundamental infrastructure difference
2. **Managed hosting** - Operational cost we bear
3. **Enterprise compliance** - SOC2, HIPAA, audit logs
4. **SSO/SAML** - Corporate identity management
5. **SLA guarantees** - Operational commitment

## The Economics

**Why $19/dev/month for Team?**

| Component | Cost per Seat |
|-----------|---------------|
| LLM inference (1M tokens/month) | ~$3 |
| Vector storage (Pixeltable) | ~$1 |
| Compute (shared infra) | ~$1 |
| **Total COGS** | **~$5** |
| **Price** | **$19** |
| **Gross Margin** | **~74%** |

At 74% gross margin, we can invest in product development, support, and infrastructure. Below $15/seat, the math doesn't work.

**Why not usage-based only?**

Usage-based pricing (pay per token) creates unpredictable bills that scare teams. Seat-based pricing is predictable. The included token allocation (1M/workspace/month) covers typical usage; heavy users can buy more.

## Hard Questions

Before the FAQ, let's address the questions skeptical engineers actually ask:

### Does the free tier phone home?

**No telemetry by default.** The OSS version doesn't contact our servers. You can run it fully air-gapped.

If you opt into crash reporting or usage analytics (disabled by default), that data is anonymized and never includes prompt content, memory content, or code. The telemetry schema is documented in `docs/telemetry.md`.

### What about the gray areas?

The "compute vs identity" rule is a guiding heuristic, not a constitutional law. Some features don't fit cleanly:

| Feature | Classification | Rationale |
|---------|---------------|-----------|
| Audit logs | **Free** (local), **Paid** (SOC2-compliant) | Local structured logs are free. Centralized, compliance-ready logging requires our infrastructure |
| RBAC | **Paid** | Requires multi-tenancy substrate |
| Rate limiting | **Free** | Runs on your compute, your config |
| Encryption at rest | **Free** | Use your own KMS |
| Team sharing without SSO | **Free** | No identity management needed |

When we're genuinely torn, we default to free. This rule helps us stay consistent, but we acknowledge it's not a perfect classifier.

### Can I migrate from paid to free?

**Yes.** Data portability is a commitment:

1. **Export everything:** Full data export in documented JSON/Parquet formats
2. **No proprietary formats:** Memory storage uses standard Pixeltable/PostgreSQL
3. **Downgrade path:** Switch from Team to self-hosted without data loss

If budget gets cut, you can export your data and run the free tier. We don't hold your data hostage.

### What if you get acquired?

We can't prevent every scenario, but we've structured things to limit damage:

1. **Apache 2.0 is irrevocable:** Existing releases stay Apache 2.0 forever. You can fork at any point.
2. **Protocols are public:** The extension interfaces live in the OSS repo. If we disappear, you can implement your own adapters.
3. **No relicensing:** We will not change the license of existing code (new major versions could theoretically differ, but we have no plans for this).

We're not committing to a dead man's switch (auto-release proprietary code on acquisition) because that's a promise we can't legally guarantee. What we *can* guarantee: the open code stays open.

## FAQ

**Q: Can I self-host for my company?**
Yes. The Apache 2.0 license explicitly allows commercial use. You can run Luminescent internally, modify it, and never pay us a cent.

**Q: What if you get acquired and change the license?**
Existing versions remain Apache 2.0 forever—that's how open source works. You can fork at any point. The worst case is you're stuck on an old version, which is the same risk as any software.

**Q: Why not AGPL to prevent cloud competition?**
AGPL scares enterprise legal teams. We'd rather compete on product quality than license restrictions. If someone builds a better cloud offering on our code, that's a sign we need to improve.

**Q: Can I contribute features and then you put them in the paid tier?**
Technically yes—that's what the CLA allows. In practice, we only do this for features that genuinely require cloud infrastructure (multi-tenancy, billing, etc.). Pure product improvements stay in OSS.

**Q: What's the minimum team size for Team tier?**
5 seats. Below that, self-hosting makes more economic sense for you and us.

## Summary

| Question | Answer |
|----------|--------|
| What's the license? | Apache 2.0 |
| What's free? | Everything that runs on your compute |
| What's paid? | Infrastructure, identity, compliance |
| How do you add paid features? | Protocol/registry pattern, no OSS pollution |
| Will free features stay free? | Yes, committed in writing |
| Can I contribute? | Yes, under CLA |
| Why this model? | Proven by GitLab, Grafana, Supabase |

The open-core model aligns our incentives: we succeed when you succeed. Free users validate the product, team users fund development, enterprise users fund compliance. Everyone gets value appropriate to what they pay.

---

*Open source strategy is detailed in ADR-004 (commercialization) and ADR-005 (licensing). See the [full ADRs](../adrs/) for implementation details and legal analysis.*
