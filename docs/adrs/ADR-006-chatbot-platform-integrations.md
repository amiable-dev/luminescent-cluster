# ADR-006: Chatbot Platform Integrations

**Status**: Accepted
**Date**: 2025-12-24
**Decision Makers**: Development Team
**Owners**: @christopherjoseph
**Version**: 1.1 (Council Validated)

## Decision Summary

Extend Luminescent Cluster to support conversational interfaces via chatbot integrations on **Slack, Discord, Telegram, and WhatsApp**. This enables developers to query organizational knowledge, code context, and architectural decisions through their existing team communication platforms.

**Strategic Value** (Council Validated):
1. **User Acquisition**: Lower barrier to entry - meet users where they already work
2. **Viral Adoption**: Non-users see AI responses in shared channels (real-time demos)
3. **Product Stickiness**: Embedded in daily workflows increases retention
4. **Team Memory**: Transforms Pixeltable from individual tool to shared team resource

| Tier | Platforms | LLM Configuration | Hosting |
|------|-----------|-------------------|---------|
| **Free (OSS)** | All 4 platforms, 100 queries/month | BYOK (local/remote) | Self-hosted |
| **Team ($19/dev)** | All 4 platforms, unlimited | Managed LLM included | Cloud-hosted |
| **Enterprise** | All + custom integrations | Managed + custom models | VPC/on-prem |

---

## Context

### The Opportunity

Modern development teams live in chat platforms. Slack, Discord, Telegram, and WhatsApp are where:
- Questions get asked and answered
- Decisions get discussed
- Knowledge gets shared (and lost)

**Current State**: Our MCP servers require IDE integration (Claude Code, Cursor). This limits adoption to developers actively coding.

**Proposed State**: Any team member can query organizational memory by mentioning a bot in their team chat:

```
@luminescent-bot What was the rationale for choosing PostgreSQL?

Based on ADR-005 from March 2024, your team chose PostgreSQL because:
1. Strong JSON support for flexible schema evolution
2. Existing team expertise from Project Aurora
3. Cost considerations vs managed NoSQL options

The decision was made by @sarah with input from @mike.
Related: INC-234 (connection pool tuning after launch)

📎 View full ADR: https://luminescent.app/workspace/adr/005
```

### Industry Research: Existing Solutions

| Project | Platforms | LLM Support | RAG | Architecture | Limitations |
|---------|-----------|-------------|-----|--------------|-------------|
| [**MuseBot**](https://github.com/yincongcyincong/MuseBot) | Telegram, Discord, Slack, Lark, DingTalk, WeChat, QQ, Web | OpenAI, Gemini, DeepSeek, Qwen, custom URLs | Basic | Go, MCP function calling, streaming | Complex Go codebase, less RAG focus |
| [**Vectara Ragtime**](https://github.com/vectara/ragtime) | Slack, Discord, WhatsApp (Twilio) | Vectara-locked | Strong (Vectara) | Python, Redis caching | Locked to Vectara, modest community |
| [**llmcord**](https://github.com/jakobdylanc/llmcord) | Discord only | Any OpenAI-compatible | None (context window) | Python (~300 LOC), async | No true RAG, Discord-only |
| [**discord-rag**](https://github.com/antoinelrnld/discord-rag) | Discord only | OpenAI only | Vector search | Python, MongoDB | Prototype, static ingestion, OpenAI-locked |
| [**Botpress**](https://github.com/botpress/botpress) | Multi-channel | OpenAI focused | Via plugins | Node.js, Studio UI | UI-first design, less code-friendly |

### Key Insights from Research

1. **No single solution covers all platforms + flexible LLM + quality RAG**
2. **MuseBot** is closest in scope but uses Go (our stack is Python)
3. **llmcord's** simplicity (~300 LOC) is appealing for our adapter pattern
4. **Vectara Ragtime** proves the Slack/Discord/WhatsApp trio is viable
5. **None leverage MCP** - we have a differentiation opportunity

---

## Council Decisions on Open Questions

The LLM Council (Gemini-3-Pro, Claude Opus 4.5, Grok-4, GPT-5.2-Pro) reached consensus on all five open questions:

| Question | Decision | Rationale |
|----------|----------|-----------|
| **1. Pricing** | **Include in $19 Team tier** | Adoption driver, not luxury feature. Control costs via rate limits, not seat licenses. |
| **2. Launch Platform** | **Discord first, Slack in parallel** | Discord for velocity/feedback (Weeks 1-4), but start Slack OAuth/App Review immediately (longer lead time). |
| **3. Streaming** | **Batched with pseudo-streaming** | True streaming is fragile and hits rate limits. Use "Thinking..." placeholders, then batched updates. Reserve true streaming for V2. |
| **4. Thread Context** | **Yes, bounded** | Mandatory for RAG usability. Limit to last 10 messages, 24h TTL to preserve context window for retrieved memories. |
| **5. Voice Support** | **Defer to V2** | High complexity, lower value for coding contexts. Design API to accept attachments now, don't build processing yet. |

---

## Decision

### Architecture: Thin Adapter Layer with Central Gateway

We adopt a **thin adapter pattern** with a **central gateway** that routes chat messages to our existing MCP infrastructure:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CHATBOT PLATFORM ADAPTERS                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │    Slack     │  │   Discord    │  │  Telegram    │  │  WhatsApp    │    │
│  │   Adapter    │  │   Adapter    │  │   Adapter    │  │   Adapter    │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
│         │                 │                 │                 │             │
│         └─────────────────┴────────┬────────┴─────────────────┘             │
│                                    │                                         │
│                                    ▼                                         │
│                    ┌───────────────────────────────────┐                    │
│                    │      Central Chat Gateway         │                    │
│                    │  • Message normalization          │                    │
│                    │  • AuthN/AuthZ + ACLs             │                    │
│                    │  • Rate limiting (token bucket)   │                    │
│                    │  • Dedupe + idempotency           │                    │
│                    │  • Audit logging                  │                    │
│                    │  • LLM capability detection       │                    │
│                    └───────────────┬───────────────────┘                    │
│                                    │                                         │
├────────────────────────────────────┼────────────────────────────────────────┤
│                                    ▼                                         │
│               ┌────────────────────────────────────────┐                    │
│               │         LLM Orchestration Layer        │                    │
│               │  • Local (Ollama, LM Studio, vLLM)     │                    │
│               │  • Cloud (OpenAI, Anthropic, Gemini)   │                    │
│               │  • Tool calling to MCP servers         │                    │
│               │  • Circuit breaker for failures        │                    │
│               └───────────────┬────────────────────────┘                    │
│                               │                                              │
│               ┌───────────────┴────────────────┐                            │
│               │                                │                            │
│               ▼                                ▼                            │
│  ┌────────────────────────┐    ┌────────────────────────────┐              │
│  │   Session Memory MCP   │    │   Pixeltable Memory MCP    │              │
│  │   (Hot: Git context)   │    │   (Cold: ADRs, incidents)  │              │
│  └────────────────────────┘    └────────────────────────────┘              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Reuse MCP Infrastructure**: Chatbots are just another client of our existing MCP servers
2. **LLM Agnostic**: Support local (Ollama) and cloud (OpenAI, Anthropic, Gemini) via OpenAI-compatible API
3. **Platform Agnostic Core**: Adapters handle platform specifics; core logic is shared
4. **Central Gateway**: Consolidate authZ, rate limiting, dedupe, and audit in one layer
5. **Stateless Adapters**: Context managed by Pixeltable, not in bot memory
6. **Extension Point Ready**: Use ADR-005's protocol pattern for paid enhancements

---

## Critical Design Decisions (Council Required)

### Invocation Policy

**Decision**: Bot responds ONLY when explicitly invoked (not passive listening).

| Trigger Type | Behavior |
|--------------|----------|
| @mention | Respond in channel |
| Slash command (`/lumi ask`) | Respond in thread |
| Direct message | Respond in DM |
| Thread started with bot | Continue responding in thread |

**Rationale**: Prevents trust erosion, reduces noise, and avoids ingesting sarcasm/incorrect context.

**Admin Controls** (Enterprise tier):
- Allowed channels list
- Allowed commands per channel
- DM permissions (enabled/disabled)
- Channel history reading permissions

### Message Persistence & Compliance

**Decision**: Chat messages are stored in Pixeltable for continuity, subject to explicit policies.

```python
# Message storage policy
class MessagePersistencePolicy:
    STORE_IN_PIXELTABLE = True  # Enable cross-session "what did we discuss?"
    RETENTION_DAYS = 90         # Default retention (configurable per workspace)
    GDPR_DELETE_ON_REQUEST = True
    SENSITIVE_CHANNEL_EXCLUSIONS = ["#legal", "#hr", "#confidential"]
```

**Compliance Implications**:
- Privacy policy must disclose chat storage
- Data deletion must include chat history
- EU customers need EU Pixeltable deployment option (Enterprise tier)
- Right-to-be-forgotten supported via `@lumi /forget-me`

**Explicit Ingestion for Long-term Memory**:
- Chat messages are stored as "conversation context" (ephemeral, 90-day default)
- Promotion to long-term memory requires explicit command: `@lumi /memorize this thread`
- This prevents noise, sarcasm, and incorrect assumptions from polluting ADR-quality memory

### Access Control (ACLs)

**CRITICAL RISK** (flagged by all Council members): Preventing data leakage.

**Scenario**: User asks `@lumi What are the DB credentials?` in a public channel. Bot must NOT answer with private data.

**Mitigation**:

```python
class AccessControlPolicy:
    def filter_response(self, query: str, response: str, channel: ChannelContext) -> str:
        """Filter response based on channel visibility."""
        if channel.is_public and self._contains_sensitive_data(response):
            return (
                "I found relevant information but it may contain sensitive data. "
                "Please ask in a private channel or DM me directly."
            )
        return response

    def check_retrieval_permission(self, user: User, memory_item: MemoryItem) -> bool:
        """Verify user can access this memory item."""
        return (
            memory_item.visibility == "public" or
            user.has_access_to(memory_item.workspace_id)
        )
```

**Channel Permission Rules**:
| Channel Type | Memory Access | Response Visibility |
|--------------|---------------|---------------------|
| Public channel | Public memories only | Visible to all |
| Private channel | Workspace memories | Visible to channel members |
| DM | User's full access | Private to user |

### Rate Limiting Strategy

**Architecture**: Token bucket per user, channel, and workspace to prevent query storms.

```python
class RateLimiter:
    def __init__(self):
        self.per_user = TokenBucket(rate=5, period=60)      # 5 queries/min/user
        self.per_channel = TokenBucket(rate=20, period=60)  # 20 queries/min/channel
        self.per_workspace = TokenBucket(rate=100, period=60) # 100 queries/min/workspace

    async def acquire(self, user_id: str, channel_id: str, workspace_id: str) -> bool:
        return all([
            self.per_user.acquire(user_id),
            self.per_channel.acquire(channel_id),
            self.per_workspace.acquire(workspace_id)
        ])
```

**Tier Limits**:
| Tier | Free | Team | Enterprise |
|------|------|------|------------|
| Queries/day | 100 | Unlimited* | Unlimited |
| Queries/min/user | 2 | 10 | 20 |
| Concurrent requests | 1 | 5 | 20 |

*Subject to fair use; heavy users may be contacted for Enterprise upgrade.

### Thread Context Management

**Decision**: Maintain bounded conversation context within threads.

```python
class ThreadContext:
    MAX_CONTEXT_MESSAGES = 10  # Prevent unbounded growth
    MAX_CONTEXT_TOKENS = 2000  # Reserve room for memory retrieval
    CONTEXT_TTL_HOURS = 24     # Don't maintain stale threads forever

    async def get_thread_context(self, thread_id: str) -> list[Message]:
        messages = await self.store.get_recent(
            thread_id,
            limit=self.MAX_CONTEXT_MESSAGES,
            since=datetime.now() - timedelta(hours=self.CONTEXT_TTL_HOURS)
        )
        return self._truncate_to_token_limit(messages)
```

**Context Window Budget**:
```
4K context window allocation:
├── System prompt:     ~200 tokens
├── Thread context:    ~1000 tokens (bounded)
├── Retrieved memory:  ~2000 tokens
├── User query:        ~200 tokens
└── Response buffer:   ~600 tokens
                       ────────────
                       4000 tokens
```

**Reset Command**: Users can clear context with `@lumi /reset`

### LLM Capability Detection

**Problem**: "OpenAI-compatible" doesn't guarantee feature parity (streaming, tool calling, etc.).

**Solution**: Probe LLM capabilities at startup.

```python
class LLMProvider:
    def __init__(self, base_url: str, api_key: str | None = None):
        self.base_url = base_url
        self.api_key = api_key
        self.capabilities = self._probe_capabilities()

    def _probe_capabilities(self) -> dict:
        return {
            "streaming": self._test_streaming(),
            "function_calling": self._test_functions(),
            "max_context": self._detect_context_window(),
        }

    async def complete(self, messages, tools=None, stream=False):
        if stream and not self.capabilities["streaming"]:
            # Graceful degradation
            stream = False
        if tools and not self.capabilities["function_calling"]:
            raise CapabilityError("Provider doesn't support function calling")
        # ... proceed with call
```

### Circuit Breaker for MCP Failures

**Problem**: MCP servers may be unavailable; adapters must degrade gracefully.

```python
class MCPClient:
    async def query_with_fallback(self, query: str) -> Response:
        try:
            return await self._query_mcp(query, timeout=5.0)
        except (TimeoutError, ConnectionError) as e:
            logger.warning(f"MCP unavailable: {e}")
            return Response(
                content="I'm having trouble accessing the knowledge base right now. "
                        "Please try again in a few moments, or check system status.",
                degraded=True
            )
```

---

## Feature Matrix

| Feature | Free (OSS) | Team | Enterprise |
|---------|------------|------|------------|
| **Platforms** | All 4 | All 4 + priority support | All + custom integrations |
| **Queries** | 100/month | Unlimited (fair use) | Unlimited |
| **LLM Configuration** | BYOK only | Managed included | Managed + custom models |
| **Memory Access** | Personal Pixeltable | Shared team memory | VPC-isolated memory |
| **Thread Context** | 10 messages | 10 messages | Configurable |
| **Message Persistence** | 30 days | 90 days | Custom retention |
| **Authentication** | Bot tokens | OAuth + workspace | SSO/SAML |
| **Admin Controls** | None | Channel allowlists | Full governance |
| **Audit Logging** | Local logs | Cloud logs | SOC2-compliant |
| **Support** | Community | Email | Dedicated CSM |

---

## Alignment with Existing ADRs

### ADR-003: Project Intent (Memory Architecture)

| ADR-003 Requirement | Chatbot Alignment |
|---------------------|-------------------|
| Pixeltable as canonical memory | Chatbots query Pixeltable via MCP - no separate storage |
| Tier 1 (Session Memory) | Available for git context queries |
| Tier 2 (Long-term Memory) | Available for ADR/incident/code queries |
| Tier 3 (Orchestration) | LLM layer orchestrates tool calls |

**No architectural changes required** - chatbots consume existing MCP tools.

### ADR-004: Monetization Strategy

| ADR-004 Tier | Chatbot Offering | Rationale |
|--------------|------------------|-----------|
| **Free** | Self-hosted bots, BYOK LLM, 100 queries/month | BYOK = user pays LLM costs |
| **Team ($19/dev)** | Managed bots, included LLM, unlimited queries | Part of "shared team context" value prop |
| **Enterprise ($50k+)** | Custom connectors, SSO, audit logs | Enterprise controls per ADR-004 |

**Council Decision**: Include chatbots in Team tier (adoption driver, not add-on).

### ADR-005: Repository Organization

| Component | Repository | Rationale |
|-----------|------------|-----------|
| Chat Gateway Core | **Public** (luminescent-cluster) | Core abstraction, Apache 2.0 |
| Platform Adapters (basic) | **Public** | Enable self-hosted deployments |
| Managed Bot Infrastructure | **Private** (luminescent-cloud) | Hosting, scaling, monitoring |
| SSO/SAML Integration | **Private** | Enterprise feature |
| Advanced Analytics | **Private** | Usage metering for billing |

---

## Implementation Plan (Revised per Council)

### Phase 1: Foundation (Weeks 1-4)

**Goal**: Discord bot with basic RAG + Slack development started in parallel

**Deliverables**:
1. Central Chat Gateway module (rate limiting, auth, dedupe)
2. Discord adapter (using discord.py)
3. LLM orchestration layer with capability detection
4. Integration with existing MCP tools
5. Slack OAuth setup + basic event handling (parallel track)

**Exit Criteria**:
- Discord bot responds to @mentions with RAG-backed answers
- Supports local (Ollama) and cloud (OpenAI) LLMs
- Response latency <3s for simple queries
- Slack app submitted for review

### Phase 2: Multi-Platform + Dogfooding (Weeks 5-8)

**Goal**: All platforms functional, internal team validation

**Deliverables**:
1. Slack adapter (using slack-bolt) - feature complete
2. Telegram adapter (using python-telegram-bot)
3. WhatsApp adapter (using Twilio API)
4. **Week 7: Internal dogfooding** (team-only deployment)
5. Thread context management

**Exit Criteria**:
- All 4 platforms functional
- Internal team has used for 2 weeks
- UX issues identified and prioritized
- Documentation for self-hosted setup

### Phase 3: Beta + Production Hardening (Weeks 9-12)

**Goal**: External beta, production-ready for Team tier

**Deliverables**:
1. Beta release (10-20 external users)
2. Authentication via ADR-005 extension protocols
3. Usage metering for billing
4. ACL implementation (channel-based filtering)
5. Observability (latency, accuracy metrics)

**Exit Criteria**:
- Handles 100 concurrent users per workspace
- 99.9% uptime target
- NPS > 40 from beta users
- Usage data feeds into billing system

### Phase 4: GA + Enterprise Features (Weeks 13-16)

**Goal**: General availability, Enterprise tier capabilities

**Deliverables**:
1. GA release with streaming support (optional)
2. SSO/SAML integration
3. Audit logging (SOC2-compatible)
4. Admin dashboard for bot management
5. Custom connector framework

---

## Technical Decisions

### Chat-Accessible MCP Tools

| Tool | Chat Command | Example |
|------|--------------|---------|
| search_organizational_memory | `@lumi search <query>` | `@lumi search authentication decisions` |
| get_architectural_decisions | `@lumi adr <number>` | `@lumi adr 003` |
| get_incident_history | `@lumi incidents <service>` | `@lumi incidents auth-service` |
| get_recent_commits | `@lumi commits` | `@lumi commits --since yesterday` |
| memorize | `@lumi /memorize` | `@lumi /memorize this thread` |
| reset | `@lumi /reset` | `@lumi /reset` |

### Response Format with Citations

**Council Requirement**: All responses must include source links to build trust.

```
@lumi Why did we choose Kafka over RabbitMQ?

Based on **ADR-017** from March 2023, your team chose Kafka because:
1. Need for event replay during incident recovery
2. Anticipated scale of 50k msgs/sec by Q4
3. Existing team expertise from Project Aurora

📎 Sources:
- [ADR-017: Message Broker Selection](link)
- [INC-234: Kafka config issue](link)
- [INC-456: Successful replay during outage](link)
```

### Observability Layer

```python
class ChatMetrics:
    async def record_query(self,
                          platform: str,
                          user_id: str,
                          query_type: str,
                          latency_ms: int,
                          tokens_used: int,
                          memory_hits: int):
        await self.emit({
            "event": "chat_query",
            "platform": platform,
            "latency_ms": latency_ms,
            "memory_relevance": memory_hits / max(tokens_used, 1),
            "degraded": False,
        })
```

**Key Metrics**:
- Query latency by platform (p50, p95)
- Memory retrieval relevance (were answers helpful?)
- Thread depth distribution
- Error rate by LLM provider

---

## Risks and Mitigations (Council Revised)

### Security & Privacy Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Data leakage to public channels** | Medium | **Critical** | ACLs: filter sensitive data based on channel type; ephemeral replies for private data |
| **Cross-workspace access** | Low | **Critical** | Strict workspace isolation; namespace-separated queries |
| **Prompt injection via chat** | Medium | High | Input validation; output filtering; rate limiting |
| **Secret exposure** | Low | **Critical** | Secret redaction in ingestion; .gitignore-style exclusions |

### Operational Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Rate limit cascades** | High | Medium | Token bucket per user/channel/workspace; backoff strategies |
| **Platform API changes** | Medium | Medium | Abstract via adapters; monitor deprecation notices |
| **LLM latency for chat UX** | Medium | High | "Thinking..." indicators; async processing; timeout handling |
| **Self-hosted LLM timeouts** | High | Medium | Immediate ACK; async response; latency warnings |

### Compliance Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **GDPR right-to-delete** | Medium | High | `/forget-me` command; retention policies; EU deployment option |
| **Chat persistence ambiguity** | High | Medium | Explicit policy in docs; opt-in for long-term memory |

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Query accuracy** | >85% rated "helpful" | Thumbs up/down feedback |
| **Response latency** | <3s p90 | Instrumentation |
| **Platform coverage** | All 4 platforms functional | Feature completion |
| **Adoption** | 100 active bots (Month 6) | Telemetry |
| **Team tier conversion** | 10% of free users upgrade | Billing data |
| **NPS (beta)** | >40 | Survey |

---

## Alternatives Considered

### Alternative A: Fork MuseBot

**Pros**: Feature-rich, multi-platform support
**Cons**: Go codebase (we're Python), complex architecture, no MCP integration
**Decision**: Rejected - rewriting in Python negates benefits

### Alternative B: Integrate Vectara Ragtime

**Pros**: Production-proven, Slack/Discord/WhatsApp support
**Cons**: Vectara-locked (we use Pixeltable), modest community
**Decision**: Rejected - conflicts with ADR-003 memory architecture

### Alternative C: Build on llmcord

**Pros**: Simple (~300 LOC), easy to understand and extend
**Cons**: Discord-only, no RAG, minimal architecture
**Decision**: Partially adopted - use as inspiration for thin adapter pattern

### Alternative D: Use Botpress

**Pros**: Enterprise-grade, multi-channel
**Cons**: UI-first design, Node.js, complex integration
**Decision**: Rejected - doesn't fit our Python/MCP architecture

---

## Council Review Summary

**Review Date**: 2025-12-24
**Council Configuration**: High confidence (all 4 models responded)
**Models**: Gemini-3-Pro, Claude Opus 4.5, Grok-4, GPT-5.2-Pro

### Unanimous Recommendations (Incorporated)

1. **Include chatbots in Team tier** (not add-on) - adoption driver
2. **Discord-first, Slack in parallel** - start Slack OAuth early due to longer lead time
3. **Batched responses with pseudo-streaming** for V1 - true streaming is fragile
4. **Bounded thread context** (10 messages, 24h TTL) - preserves context window
5. **Explicit invocation policy** - prevent trust erosion from passive listening
6. **Central gateway required** - consolidate auth, rate limiting, audit
7. **ACLs for public/private channel filtering** - critical security requirement
8. **Message persistence policy** - explicit, with GDPR compliance
9. **Citations in all responses** - builds trust, combats hallucinations

### Key Insights by Model

- **Gemini**: "Shift Left on Knowledge" - bot transforms archive into active participant; add explicit ingestion (`/memorize`) to filter noise
- **Claude**: Detailed context window budget; observability from day one; add "conversation handoff" links to web UI
- **Grok**: High strategic value for viral adoption; provider capability test suite essential for LLM agnosticism
- **GPT**: Central gateway is security boundary; invocation policy is first-class design element; treat session state vs memory explicitly

---

## Related Decisions

- **ADR-003**: Project Intent (memory architecture we consume)
- **ADR-004**: Monetization Strategy (pricing tiers)
- **ADR-005**: Repository Organization (public/private split)

## References

- [MuseBot - Multi-platform LLM Bot](https://github.com/yincongcyincong/MuseBot)
- [Vectara Ragtime - RAG Chatbot](https://github.com/vectara/ragtime)
- [llmcord - Simple Discord LLM Bot](https://github.com/jakobdylanc/llmcord)
- [discord-rag - Discord RAG Prototype](https://github.com/antoinelrnld/discord-rag)
- [Botpress - Conversational AI Platform](https://github.com/botpress/botpress)

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-24 | Initial draft based on industry research and ADR alignment |
| 1.1 | 2025-12-24 | **Council Validation**: Resolved all 5 open questions. Added invocation policy, message persistence, ACLs, rate limiting, LLM capability detection, circuit breaker. Revised timeline with dogfooding week and parallel Slack development. Added observability requirements and citations requirement. |
| 1.2 | 2025-12-28 | **Peer Review Remediation**: Implemented all critical gaps identified in peer review. See Implementation Notes below. |

---

## Implementation Notes (v1.2)

**Peer Review Date**: 2025-12-28
**Status**: All critical gaps remediated

### Implemented Components

| Component | Status | Location | Tests |
|-----------|--------|----------|-------|
| **Access Control Integration** | ✅ Complete | `src/chatbot/gateway.py:316+` | `tests/chatbot/test_gateway_access_control.py` |
| **Pixeltable Context Persistence** | ✅ Complete | `src/chatbot/context.py` | `tests/chatbot/test_context_persistence.py` |
| **ChatMetrics Telemetry** | ✅ Complete | `src/chatbot/metrics.py` | `tests/chatbot/test_metrics.py` |
| **DefaultAccessControlPolicy** | ✅ Complete | `src/chatbot/access_control.py` | `tests/chatbot/test_access_control.py` |

### Access Control (`src/chatbot/access_control.py`)

Three policy classes per ADR-006 requirements:

1. **DefaultAccessControlPolicy**: Permissive OSS default - allows all channels and commands
2. **ConfigurableAccessControlPolicy**: File-based allowlist/blocklist for self-hosted deployments
3. **ResponseFilterPolicy**: Filters sensitive data (passwords, API keys) in public channels

```python
# OSS mode (default)
from src.chatbot.access_control import DefaultAccessControlPolicy
policy = DefaultAccessControlPolicy()
allowed, reason = policy.check_channel_access(user_id, channel_id, workspace_id)
# allowed == True for all channels

# Self-hosted with restrictions
from src.chatbot.access_control import ConfigurableAccessControlPolicy
policy = ConfigurableAccessControlPolicy(
    allowed_channels=["#general", "#engineering"],
    blocked_channels=["#hr", "#legal"],
    allowed_commands=["/help", "/ask", "/search"],
)
```

### Context Persistence (`src/chatbot/context.py`)

Pixeltable-backed context storage per ADR-003 memory architecture:

- **Hot cache**: In-memory dict for fast reads
- **Persistence**: Pixeltable `conversation_context` table
- **Retention**: 90-day TTL per ADR-006

```python
# Schema
pxt.create_table('conversation_context', {
    'thread_id': pxt.String,
    'channel_id': pxt.String,
    'created_at': pxt.Timestamp,
    'last_activity': pxt.Timestamp,
    'messages': pxt.Json,
    'metadata': pxt.Json,
})
```

### ChatMetrics Telemetry (`src/chatbot/metrics.py`)

Observability per ADR-006 spec:

```python
class ChatMetrics:
    async def record_query(
        self,
        platform: str,        # "discord", "slack", "telegram", "whatsapp"
        user_id: str,
        query_type: str,      # "search", "memorize", "reset"
        latency_ms: int,
        tokens_used: int,
        memory_hits: int,
    ) -> None:
        # Emits: latency, memory_relevance, degraded status
```

**Key Metrics**:
- Query latency by platform (p50, p95)
- Memory retrieval relevance (`memory_hits / tokens_used`)
- Token usage by user/workspace
- Error rates by LLM provider

### Test Coverage

Total chatbot tests: **414 passing**

| Test File | Count | Coverage |
|-----------|-------|----------|
| `test_gateway_access_control.py` | 15 | ACL integration in gateway |
| `test_context_persistence.py` | 18 | Pixeltable storage, TTL, cache |
| `test_metrics.py` | 12 | ChatMetrics recording |
| `test_access_control.py` | 21 | Policy behavior |
| Platform adapters | 348 | Discord, Slack, Telegram, WhatsApp |

### Repository Placement (per ADR-005)

| Component | Repository | Rationale |
|-----------|------------|-----------|
| DefaultAccessControlPolicy | luminescent-cluster (public) | OSS permissive default |
| ConfigurableAccessControlPolicy | luminescent-cluster (public) | Self-hosted config |
| ResponseFilterPolicy | luminescent-cluster (public) | Core security |
| ContextStore protocol | luminescent-cluster (public) | Interface definition |
| PixeltableContextStore | luminescent-cluster (public) | Uses user's own Pixeltable |
| ChatMetrics | luminescent-cluster (public) | Core observability |
| CloudAccessController | luminescent-cloud (private) | Workspace SSO, ACLs |
