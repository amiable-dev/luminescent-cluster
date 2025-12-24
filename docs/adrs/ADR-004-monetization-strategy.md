# ADR-004: Monetization Strategy

**Status**: Accepted
**Date**: 2025-12-22
**Decision Makers**: Development Team
**Owners**: @christopherjoseph
**Version**: 1.1 (Council Validated)

## Decision Summary

Adopt an **Open-Core + Hosted SaaS** monetization model, targeting AI-augmented development teams.

**Refined Value Proposition** (Council Validated):
- **Old Pitch**: "Contextual Code Assistant" (competes with Copilot - loses on price)
- **New Pitch**: "The Team's Technical Librarian"
- **Argument**: "Copilot helps you write code faster. Luminescent tells you *why* the code was written that way 6 months ago."

| Tier | Target | Pricing | Key Features |
|------|--------|---------|--------------|
| **Free** | Individual Devs | Self-hosted | Full OSS, single user, BYOK (you pay LLM costs) |
| **Team** | SMB / Agile Teams | $19/dev/month | Hosted, shared context, 1M tokens/workspace/mo |
| **Enterprise** | Regulated Industries | $50k+ annual | VPC/on-prem, SOC2, SLA, unlimited tokens |

**Pricing Rationale** (Council Feedback):
- GitHub Copilot: $19/user/month
- Cursor: $20/user/month
- **$19 matches market anchor** while positioning as complementary (not competitive)
- Premium justified by "Team Memory" not "Coding Assistance"

---

## Context

### The Market Opportunity

AI assistants are becoming ubiquitous in software development:
- GitHub Copilot: 1.3M+ paying subscribers
- Cursor: Fastest-growing IDE
- Claude Code: Enterprise adoption accelerating

**The Problem They All Share**: Context amnesia. Every session starts fresh.

### Why "Organizational Context" Wins

Individual developers already have memory via ChatGPT or Cursor. The unmet market need is **Organization-Level Memory**.

**Scenario**: A Senior dev leaves the company. Usually, their contextual knowledge leaves with them.

**Luminescent Value**: The Cluster retains the logic, decisions, and architectural preferences. A new Junior dev connects their IDE and instantly has access to the Senior dev's historical context.

---

## Decision

### Pricing Structure (Council Validated)

```
+-------------------------------------------------------------------------+
|                        LUMINESCENT CLUSTER                               |
|                    "The Team's Technical Librarian"                      |
+-------------------------------------------------------------------------+
|                                                                          |
|  FREE (Self-Hosted)         TEAM                    ENTERPRISE           |
|  ------------------         ----                    ----------           |
|                                                                          |
|  - Full open-source         - $19/dev/month         - $50k+ annual       |
|  - Unlimited local use      - Hosted Pixeltable     - Self-hosted +      |
|  - Community support        - Shared team context     support            |
|  - Single user              - 1M tokens/workspace   - SSO/SAML           |
|  - BYOK (you pay LLM)       - GitHub/GitLab         - Audit logs         |
|                               integration           - Data residency     |
|                             - Slack notifications   - SLA guarantee      |
|                             - Email support         - Unlimited tokens   |
|                                                     - Dedicated CSM      |
|                                                                          |
|              +---------------------------------------------+             |
|              |         USAGE ADD-ONS (Team Tier)           |             |
|              +---------------------------------------------+             |
|              | - Additional tokens: $10/10M over limit      |             |
|              | - Priority incident indexing: $5/dev/month   |             |
|              | - Custom model fine-tuning: $500/model       |             |
|              +---------------------------------------------+             |
|                                                                          |
+-------------------------------------------------------------------------+
```

### Rationale (Council Validated)

1. **Free tier is BYOK (Bring Your Own Key)**: Prevents API cost overruns; user pays their own LLM costs
2. **Team tier matches market**: $19 aligns with Copilot/Cursor; 1M token cap protects margins
3. **Enterprise is minimum $50k**: Sets sales qualification bar; includes unlimited for simplicity
4. **Usage overage for Team**: Captures heavy users without pricing out SMBs

---

## Target Customers

### Segment 1: AI-Forward Engineering Teams (Primary)

**Profile:**
- 10-200 engineers
- Heavy AI assistant usage (Copilot, Cursor, Claude)
- Frustrated by AI "forgetting" codebase context
- Already paying $20-50/dev/month for AI tools

**Pain Points:**
- "I explained our auth system to Claude 47 times this month"
- "Copilot suggests patterns we deprecated 6 months ago"
- "New engineers ask the AI questions and get answers that ignore our ADRs"

**Willingness to Pay:** High ($15-30/dev/month) if it demonstrably saves time

### Segment 2: Platform Engineering Teams (Secondary)

**Profile:**
- Building internal developer platforms
- Want to embed AI assistants with organizational knowledge
- Need enterprise controls (SSO, audit logs, data residency)

**Pain Points:**
- "We want to give devs an AI that knows our systems"
- "Compliance needs to audit what the AI knows"
- "Can't send our code to external services"

**Willingness to Pay:** Very high for enterprise ($50-100/dev/month)

### Segment 3: Solo/Small Team Developers (Freemium Funnel)

**Profile:**
- Individual devs or teams < 5
- Price-sensitive but influential
- Active on Twitter, HN, Reddit

**Value:** Market awareness, bottom-up adoption, feedback loop

---

## Differentiators

### What Makes Luminescent Cluster Unique?

| Competitor | Their Focus | Our Differentiation |
|------------|-------------|---------------------|
| Mem0 | General conversational memory | **Technical context depth**: Code semantics, ADR relationships, incident patterns |
| LangChain Memory | LLM application building | **End-to-end solution**: Not just a library, a complete system |
| Cursor/Copilot | Code completion | **Organizational knowledge**: Not just your codebase, your decisions, incidents, patterns |
| RAG frameworks | Document Q&A | **Active memory**: Learns from conversations, not just retrieves documents |

### Concrete Differentiators

**1. Decision Traceability**
```
"Why do we use Kafka instead of RabbitMQ?"

Generic RAG: "Kafka is a distributed streaming platform..."

Luminescent: "Based on ADR-017 from March 2023, your team chose Kafka
because: (1) need for event replay during incident recovery,
(2) anticipated scale of 50k msgs/sec by Q4, (3) existing team
expertise from Project Aurora. The decision was made by @sarah
with input from @mike. Related incidents: INC-234 (Kafka config issue),
INC-456 (successfully used replay during outage)."
```

**2. Incident-Informed Suggestions**
```
"How should I implement the payment retry logic?"

Generic AI: "Here's a standard exponential backoff pattern..."

Luminescent: "Based on INC-892 from last month, your payment provider
has specific retry requirements: max 3 retries, minimum 30s between
attempts, and you MUST include idempotency keys (your team learned
this the hard way). Here's the pattern from approved PR #4521."
```

**3. Preference Propagation**
```
User A (senior): "We should always use structured logging with
correlation IDs for any new service."

User B (new hire, different session): "How should I add logging
to my new service?"

Luminescent: "Your team has standardized on structured logging with
correlation IDs (team preference from @senior_dev). Here's the
template from your logging ADR..."
```

---

## Go-to-Market Strategy (Council Revised)

**Critical Fix**: Original phases had resource conflict in months 4-6. Revised to stagger.

### Phase A: Open Source Traction (Months 1-6)

**Goal:** 1,000 GitHub stars, 100 active self-hosted users

**Tactics:**
1. Launch on HN/Reddit with honest "We built this because X frustrated us"
2. Technical blog series: "How we index 1M lines of code for semantic search"
3. Integration tutorials: Cursor, Continue, Claude Desktop, VS Code
4. Discord community: Direct feedback loop, support, champions

**Metrics:**
- GitHub stars/forks/contributors (target: 20% MoM growth)
- Discord members, active conversations
- Self-hosted deployments (telemetry opt-in)

**Failure Trigger:** If month 6 <500 stars → Re-evaluate market fit, not just marketing

### Phase B: Hosted Beta (Months 6-10) ← STAGGERED

**Goal:** 50 paying teams, $10k MRR

**Resource Allocation (Months 6-8):**
- 60% engineering: Hosted infrastructure
- 20% engineering: OSS maintenance/community PRs
- 20% founder time: Beta customer development

**Tactics:**
1. Invite active community members to hosted beta (free first month)
2. Case studies from beta users (with permission)
3. ProductHunt launch when stable
4. Early adopter pricing: 50% off for first 6 months, locked in forever

**Metrics:**
- Conversion: self-hosted → hosted (target: 10%)
- Retention: weekly active teams
- NPS from beta users (target: >40)

**Failure Trigger:** If month 10 <$5k MRR → Extend beta, delay Enterprise investment

### Phase C: Enterprise Motion (Months 10-16) ← DELAYED

**Goal:** 3 enterprise contracts, $100k+ ARR

**Tactics:**
1. Compliance certifications: SOC 2 Type 1 (month 10), Type 2 (month 16)
2. Enterprise pilot program: Free 90-day pilot with success criteria
3. Warm intros from Team tier users to their enterprise friends
4. Partner with AI consultancies who implement AI for enterprises

**Metrics:**
- Pipeline value
- Pilot → Paid conversion rate (target: 30%)
- Average contract value (target: $50k+)

**Failure Trigger:** If month 12 pipeline <3 qualified opportunities → Focus on SMB, defer Enterprise

---

## Competitive Moat

### What's Defensible Long-Term?

| Moat Type | Strength | Our Angle |
|-----------|----------|-----------|
| **Network effects** | Medium | Team memories become more valuable as team uses it more; switching cost increases |
| **Data/learning** | High | Accumulated organizational context is irreplaceable; fine-tuned models specific to customer |
| **Integrations** | Medium | Deep integrations with dev tools create switching cost |
| **Brand/community** | Medium | Being "the" AI context tool for developers |
| **Technical lead** | Low | Can be replicated; need to keep innovating |

### The Real Moat: Accumulated Context

```
Day 1:   Luminescent knows your code structure
Day 30:  Luminescent knows your decisions and why
Day 90:  Luminescent knows your team's preferences and patterns
Day 180: Luminescent has seen 50 incidents and knows your failure modes
Day 365: Luminescent understands your organization better than most employees

Switching cost at Day 365: Starting over from zero
```

This is the Slack/Notion playbook: the product gets more valuable over time, and that value is locked in your instance.

---

## Context Scoping for Tenancy

To support monetization, context must be scoped at three levels:

| Scope | Description | Tier |
|-------|-------------|------|
| **Session Scope** | Ephemeral (Git-based) | All tiers |
| **User Scope** | Personal preferences (Pixeltable partition) | All tiers |
| **Team Scope** | Shared architectural knowledge (Global partition) | **Paid Feature** |

**Implementation Note**: The separation of User vs Team scope is the technical boundary for the Free vs Paid tier.

---

## Unit Economics (Council Required)

| Metric | Estimate | Notes |
|--------|----------|-------|
| COGS per Team seat | ~$5/month | LLM inference, vector storage, compute |
| Target gross margin | >70% | $19 price - $5 COGS = $14 margin |
| Break-even for hosted infra | 30 teams | ~$600 MRR covers base infrastructure |
| CAC assumption | <3 months payback | Community-driven, low paid acquisition |

### Pricing Validation Plan
- **Beta**: Offer $10/dev/month to first 20 teams
- **Track**: Usage patterns, willingness-to-pay surveys at month 3
- **Adjust**: Final pricing based on actual COGS and perceived value

---

## Investment Required

| Category | Requirement | Notes |
|----------|-------------|-------|
| Engineering | 2 FTE for core product | Pixeltable native memory, MCP tools |
| Infrastructure | ~$2k/month hosting | Scales with customers |
| Go-to-market | 0.5 FTE developer relations | Blog, community, integrations |
| Compliance | $30-50k for SOC 2 | Month 10+ for enterprise motion |

---

## Revenue Projections

### Year 1 Targets

| Milestone | Timeline | Revenue |
|-----------|----------|---------|
| Hosted Beta Launch | Month 4 | $0 (free beta) |
| First 50 Paying Teams | Month 8 | $10k MRR |
| First Enterprise Deal | Month 10 | +$25k ARR |
| End of Year 1 | Month 12 | **$150k ARR** |

### Assumptions
- 50 teams × $25/dev × 8 devs avg = $10k MRR
- 3 enterprise deals × $50k avg = $150k ARR
- 20% month-over-month growth in team tier

---

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Mem0 or similar raises large round and out-executes** | Medium | High | Speed: Ship fast, build community before competition. Depth: Focus on technical context, not general memory. |
| **Large AI lab (OpenAI, Anthropic) builds native memory** | Medium | High | Stickiness: Make accumulated context the moat. They can't replicate your specific org's history. |
| **Market timing: Too early? Developers not ready to pay?** | Low | Medium | Freemium funnel: Low barrier to adoption. Measure activation to time paid conversion. |
| **Enterprise sales cycle too long** | Medium | Medium | Land with Team tier, expand to Enterprise. Warm intros from champions. |

---

## Success Metrics

### Product Metrics
- Weekly active teams
- Context queries per team
- Memory items per user
- Retrieval accuracy (precision@5)

### Business Metrics
- MRR and ARR
- Team tier → Enterprise conversion rate
- Net Revenue Retention
- Customer Acquisition Cost

### Community Metrics
- GitHub stars and contributors
- Discord active users
- Self-hosted to hosted conversion

---

## Council Review Summary

**Review Date**: 2025-12-22
**Council Configuration**: High confidence (all 4 models)

### Unanimous Recommendations
1. **Open-core model is correct** for developer tools
2. **Per-seat + usage hybrid pricing** aligns cost with value
3. **"Organizational Context" is the value prop**, not generic memory
4. **Bottom-up GTM** (OSS → Team → Enterprise) is the right motion
5. **Accumulated context is the moat** - switching costs increase over time

### Key Insights by Model
- **Gemini**: "The Team Brain" positioning; sell what generic AI can't provide
- **Claude**: Detailed pricing structure with add-ons; enterprise pilot program
- **Grok**: Freemium SaaS model; $500K ARR Year 1 target possible
- **GPT**: Open-core "Context Backend" positioning; metering hooks for billing

---

## Related Decisions

- **ADR-001**: Python Version Requirement (database integrity)
- **ADR-002**: Workflow Integration (automated ingestion)
- **ADR-003**: Project Intent (architecture and memory strategy)
- **ADR-005**: Repository Organization Strategy (implements this monetization model)

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-22 | Initial draft based on council review of ADR-003 monetization question |
| 1.1 | 2025-12-23 | **Council Validation**: Reduced Team pricing from $25 to $19 (market alignment). Added "Technical Librarian" positioning. Fixed GTM phase overlap (staggered B to month 6). Added BYOK for Free tier. Added unit economics. Added failure triggers per phase. |
