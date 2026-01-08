# ADR-007: Cross-ADR Integration Guide

**Status**: Accepted
**Date**: 2025-12-28
**Decision Makers**: Development Team
**Owners**: @christopherjoseph
**Version**: 1.1 (Council Validated)

## Decision Summary

This ADR provides a **unified integration map** across ADRs 003-006, addressing:

1. End-to-end data flow from user interfaces to memory persistence
2. Protocol definitions and extension registry consolidation
3. Phase alignment between memory and chatbot roadmaps
4. Compliance responsibilities by deployment type
5. Implementation status tracking

**Purpose**: Ensure coherent implementation of the Luminescent platform by documenting how architectural decisions interconnect.

---

## Context

### The Problem: Fragmented ADR Landscape

ADRs 003-006 were created in sequence, each addressing a specific concern:

| ADR | Focus | Status |
|-----|-------|--------|
| ADR-003 | Memory Architecture (Pixeltable, MCP) | Accepted (Phases 0-4 defined) |
| ADR-004 | Monetization (Free/Team/Enterprise tiers) | Accepted |
| ADR-005 | Repository Organization (OSS vs Paid) | Implemented |
| ADR-006 | Chatbot Platform Integrations | Partially Implemented |

**Gaps Identified**:

1. **No unified data flow diagram** - How does a Discord message become a Pixeltable query?
2. **Protocol fragmentation** - ADR-005 defines TenantProvider/UsageTracker; ADR-006 implements CloudAccessController without cross-reference
3. **Phase misalignment** - ADR-003 has memory phases (0-4); ADR-006 has chatbot phases (1-4); unclear how they coordinate
4. **Compliance gaps** - GDPR implemented in luminescent-cloud but not referenced in ADR-004's tier definitions
5. **Status tracking** - Each ADR uses different implementation tracking formats

---

## Decision

### 1. Unified Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                        LUMINESCENT PLATFORM ARCHITECTURE                             │
│                    (Integration of ADRs 003, 004, 005, 006)                         │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  USER INTERFACES (ADR-006)                                                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐              │
│  │ Discord  │ │  Slack   │ │ Telegram │ │ WhatsApp │ │ Claude/IDE   │              │
│  │ Adapter  │ │ Adapter  │ │ Adapter  │ │ Adapter  │ │ (MCP Client) │              │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘              │
│       │            │            │            │               │                      │
│       └────────────┴────────────┴────────────┘               │                      │
│                          │                                   │                      │
│                          ▼                                   │                      │
│  ┌───────────────────────────────────────────────┐          │                      │
│  │          Central Chat Gateway (ADR-006)        │          │                      │
│  │  • Message normalization                       │          │                      │
│  │  • AuthN/AuthZ via AccessController Protocol   │◄─────────┤                      │
│  │  • Rate limiting (TokenBucket)                 │          │                      │
│  │  • Audit logging                               │          │                      │
│  └───────────────────────────────┬───────────────┘          │                      │
│                                  │                           │                      │
├──────────────────────────────────┼───────────────────────────┼──────────────────────┤
│  EXTENSION REGISTRY (ADR-005)    │                           │                      │
│  ┌───────────────────────────────┼───────────────────────────┼────────────────────┐ │
│  │  Protocols (luminescent-cluster)                          │                    │ │
│  │  ├── TenantProvider         ──┤                           │                    │ │
│  │  ├── UsageTracker           ──┼───────────────────────────┘                    │ │
│  │  ├── AuditLogger            ──┤                                                │ │
│  │  └── ChatbotAccessController ─┤  ◄── NEW: Documented in this ADR              │ │
│  │                               │                                                │ │
│  │  Implementations (luminescent-cloud)                                           │ │
│  │  ├── CloudTenantProvider                                                       │ │
│  │  ├── StripeUsageTracker                                                        │ │
│  │  ├── CloudAuditLogger                                                          │ │
│  │  ├── CloudAccessController                                                     │ │
│  │  └── GDPRService                                                               │ │
│  └────────────────────────────────────────────────────────────────────────────────┘ │
│                                  │                                                  │
├──────────────────────────────────┼──────────────────────────────────────────────────┤
│  LLM ORCHESTRATION LAYER         │                                                  │
│  ┌───────────────────────────────┼────────────────────────────────────────────────┐ │
│  │  • Local (Ollama, LM Studio, vLLM)                                             │ │
│  │  • Cloud (OpenAI, Anthropic, Gemini)                                           │ │
│  │  • Tool calling to MCP servers ◄──────────────────────────────────────────┐    │ │
│  │  • Circuit breaker for failures                                           │    │ │
│  └─────────────────────┬─────────────────────────────────────────────────────┤────┘ │
│                        │                                                     │      │
├────────────────────────┼─────────────────────────────────────────────────────┼──────┤
│  MEMORY TIERS (ADR-003)│                                                     │      │
│  ┌─────────────────────┼─────────────────────────────────────────────────────┼────┐ │
│  │                     │                                                     │    │ │
│  │  TIER 1: SESSION MEMORY (Hot)           TIER 2: LONG-TERM MEMORY (Warm)   │    │ │
│  │  ┌────────────────────────┐             ┌─────────────────────────────┐   │    │ │
│  │  │  session_memory_server │             │   pixeltable_mcp_server     │   │    │ │
│  │  │  • Git state           │             │   • org_knowledge table     │   │    │ │
│  │  │  • Recent commits      │             │   • conversation_context    │◄──┘    │ │
│  │  │  • Current diff        │             │   • meetings table          │        │ │
│  │  │  • Task context        │             │   • usage_metrics table     │        │ │
│  │  └────────────────────────┘             └─────────────────────────────┘        │ │
│  │                                                                                │ │
│  │  TIER 3: ORCHESTRATION                                                         │ │
│  │  • Tool Search (85% token reduction)                                           │ │
│  │  • Programmatic Tool Calling (37% token reduction)                             │ │
│  │  • Deferred Loading                                                            │ │
│  └────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                      │
├──────────────────────────────────────────────────────────────────────────────────────┤
│  DATA PERSISTENCE                                                                    │
│  ┌────────────────────────────────────────────────────────────────────────────────┐ │
│  │                            Pixeltable Database                                 │ │
│  │  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐               │ │
│  │  │  org_knowledge   │ │ conversation_    │ │  usage_metrics   │               │ │
│  │  │  (ADRs, code,    │ │ context          │ │  (ADR-006        │               │ │
│  │  │  incidents)      │ │ (chat threads)   │ │  ChatMetrics)    │               │ │
│  │  └──────────────────┘ └──────────────────┘ └──────────────────┘               │ │
│  │                                                                                │ │
│  │  OSS: ~/.pixeltable/ (local)                                                   │ │
│  │  Cloud: Managed Pixeltable (multi-tenant via TenantProvider)                   │ │
│  └────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                      │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### 1a. Security Overlay (Council Required)

**Critical Requirement**: The architecture must show WHERE security enforcement happens.

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           SECURITY ENFORCEMENT POINTS                                │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌──────────────┐     ┌──────────────────────────────────────────────────────┐      │
│  │   Adapter    │     │                CENTRAL GATEWAY                       │      │
│  │   Layer      │────▶│  ┌─────────────────────────────────────────────────┐ │      │
│  │              │     │  │ ENFORCEMENT POINT 1: Access Control             │ │      │
│  └──────────────┘     │  │ • ChatbotAccessController.check_channel_access  │ │      │
│                       │  │ • Strips unauthorized commands BEFORE LLM       │ │      │
│                       │  │ • Returns "Access denied" immediately           │ │      │
│                       │  └─────────────────────────────────────────────────┘ │      │
│                       │                        │                             │      │
│                       │                        ▼                             │      │
│                       │  ┌─────────────────────────────────────────────────┐ │      │
│                       │  │ ENFORCEMENT POINT 2: Rate Limiting              │ │      │
│                       │  │ • TokenBucket.acquire(user, channel, workspace) │ │      │
│                       │  │ • Prevents abuse before expensive LLM calls     │ │      │
│                       │  └─────────────────────────────────────────────────┘ │      │
│                       └──────────────────────────────────────────────────────┘      │
│                                            │                                         │
│                                            ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │ ENFORCEMENT POINT 3: Tenant Isolation (Pixeltable Layer)                     │   │
│  │ • TenantProvider.get_tenant_filter() applied to ALL queries                  │   │
│  │ • Namespace separation: workspace_123.org_knowledge vs workspace_456.*      │   │
│  │ • Cross-tenant queries return empty results (not errors)                     │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│                                            │                                         │
│                                            ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │ ENFORCEMENT POINT 4: Response Filtering                                       │   │
│  │ • ResponseFilterPolicy.filter_sensitive_data() on outbound                   │   │
│  │ • Redacts: passwords, API keys, PII in public channels                       │   │
│  │ • Private channels: Less aggressive filtering                                 │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

**Key Principle**: Security checks happen BEFORE expensive operations (LLM calls, database queries).

### 1b. Error Handling & Resilience (Council Required)

**Problem**: The integrated system has multiple failure modes. Define behavior for each.

| Failure Point | Failure Mode | Behavior | User Experience |
|---------------|--------------|----------|-----------------|
| **Adapter** | Platform API down | Fail fast | "Platform unavailable, try later" |
| **Gateway** | Rate limit exceeded | Reject | "Rate limit exceeded. Wait 60s." |
| **Access Control** | Auth service timeout | Fail closed | "Unable to verify access. Try again." |
| **LLM** | Provider timeout | Circuit breaker | "Thinking... (retrying)" then fallback |
| **Memory (Tier 2)** | Pixeltable unavailable | Degrade gracefully | Answer without memory context |
| **ContextStore** | Save failed | Log + continue | Response succeeds, context lost |
| **GDPR** | Partial deletion | Retry queue | "Deletion in progress. Check back." |

**Resilience Strategy**:

```python
# Central Gateway resilience pattern
class ResilientGateway:
    async def handle_message(self, message: ChatMessage) -> Response:
        # 1. Access control: Fail CLOSED (deny on error)
        try:
            allowed, reason = self.access_controller.check_access(...)
            if not allowed:
                return Response.denied(reason)
        except Exception:
            return Response.denied("Unable to verify access")

        # 2. Rate limiting: Fail CLOSED (reject on error)
        if not self.rate_limiter.acquire(...):
            return Response.rate_limited()

        # 3. LLM + Memory: Fail OPEN (degrade on error)
        try:
            response = await self.llm.complete_with_memory(...)
        except MemoryUnavailable:
            response = await self.llm.complete_without_memory(...)
            response.degraded = True

        # 4. Context persistence: Fail OPEN (log, don't crash)
        try:
            await self.context_store.save(...)
        except Exception as e:
            logger.error(f"Context save failed: {e}")

        return response
```

### 1c. Migration Strategy (Council Required)

**Problem**: Protocol consolidation introduces breaking changes to Extension Registry.

**Migration Path**:

| Step | Action | Timeline |
|------|--------|----------|
| 1 | Add new protocols to `src/extensions/protocols.py` | Day 1 |
| 2 | Update `ExtensionRegistry` with new optional fields | Day 1 |
| 3 | Update Gateway to check for new protocols | Day 2-3 |
| 4 | Update luminescent-cloud implementations | Day 4-5 |
| 5 | Add deprecation warnings for old patterns | Week 2 |
| 6 | Remove deprecated patterns | v2.0 release |

**Backward Compatibility**:

```python
# Graceful migration pattern
class ExtensionRegistry:
    # New protocol (v1.1+)
    chatbot_access_controller: Optional[ChatbotAccessController] = None

    # Deprecated compatibility (remove in v2.0)
    @property
    def access_controller(self) -> Optional[ChatbotAccessController]:
        warnings.warn(
            "access_controller is deprecated, use chatbot_access_controller",
            DeprecationWarning
        )
        return self.chatbot_access_controller
```

### 2. Protocol Registry Consolidation

ADR-005's Extension Registry must include all cross-cutting protocols.

**Protocol Versioning (Council Decision)**: All protocols use Semantic Versioning (SemVer):

| Protocol | Version | Status | Breaking Changes |
|----------|---------|--------|------------------|
| TenantProvider | v1.0.0 | Stable | - |
| UsageTracker | v1.0.0 | Stable | - |
| ChatbotAccessController | v1.0.0 | New | - |
| AuditLogger | v1.0.0 | New | - |
| ContextStore | v1.0.0 | New | - |

**Versioning Rules**:
- MAJOR: Breaking changes to method signatures
- MINOR: New optional methods added
- PATCH: Documentation or bug fixes only
- Deprecation: Support old versions for 6 months minimum

```python
# luminescent-cluster/src/extensions/protocols.py

from typing import Protocol, Optional, List, Dict, Any, Tuple
from datetime import datetime

# Protocol version constants
TENANT_PROVIDER_VERSION = "1.0.0"
USAGE_TRACKER_VERSION = "1.0.0"
CHATBOT_ACCESS_CONTROLLER_VERSION = "1.0.0"
AUDIT_LOGGER_VERSION = "1.0.0"
CONTEXT_STORE_VERSION = "1.0.0"

# === ADR-005 Original Protocols ===

class TenantProvider(Protocol):
    """Multi-tenancy extension point."""
    def get_tenant_id(self, request_context: dict) -> Optional[str]: ...
    def get_tenant_filter(self, tenant_id: str) -> dict: ...

class UsageTracker(Protocol):
    """Usage metering extension point."""
    def track(self, operation: str, tokens: int, metadata: dict) -> None: ...

# === ADR-006 Chatbot Protocols (NEW) ===

class ChatbotAccessController(Protocol):
    """Access control for chatbot integrations (ADR-006)."""

    def check_channel_access(
        self, user_id: str, channel_id: str, workspace_id: str
    ) -> Tuple[bool, Optional[str]]:
        """Check if user can access bot in channel. Returns (allowed, reason)."""
        ...

    def check_command_access(
        self, user_id: str, command: str, workspace_id: str
    ) -> Tuple[bool, Optional[str]]:
        """Check if user can execute command. Returns (allowed, reason)."""
        ...

    def get_allowed_channels(self, workspace_id: str) -> List[str]:
        """Get list of channels where bot is allowed."""
        ...

class AuditLogger(Protocol):
    """Audit logging for compliance (ADR-006 GDPR)."""

    def log_gdpr_deletion(
        self, user_id: str, workspace_id: str,
        items_deleted: Dict[str, int], timestamp: datetime
    ) -> None: ...

    def log_gdpr_export(
        self, user_id: str, workspace_id: str,
        total_items: int, timestamp: datetime
    ) -> None: ...

class ContextStore(Protocol):
    """Conversation context persistence (ADR-006)."""

    async def get_context(self, thread_id: str) -> Optional[Dict[str, Any]]: ...
    async def save_context(self, thread_id: str, context: Dict[str, Any]) -> None: ...
    async def delete_context(self, thread_id: str) -> None: ...
```

Updated `ExtensionRegistry`:

```python
# luminescent-cluster/src/extensions/registry.py

@dataclass
class ExtensionRegistry:
    """Singleton registry for all extension points."""

    # ADR-005 Original
    tenant_provider: Optional[TenantProvider] = None
    usage_tracker: Optional[UsageTracker] = None

    # ADR-006 Chatbot Extensions (NEW)
    chatbot_access_controller: Optional[ChatbotAccessController] = None
    audit_logger: Optional[AuditLogger] = None
    context_store: Optional[ContextStore] = None

    _instance: ClassVar[Optional['ExtensionRegistry']] = None

    @classmethod
    def get(cls) -> 'ExtensionRegistry':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
```

### 3. Phase Alignment Matrix (Council Revised)

ADR-003 (Memory) and ADR-006 (Chatbot) phases now aligned with **explicit dependencies**.

**Hard Blockers (Council Identified)**:
- Memory Phase 1b (Storage) → Chatbot Phase 2 (Multi-platform) - Cannot persist context without storage
- Memory Phase 1c (Retrieval) → Chatbot Phase 4 (Context Engineering) - Advanced context requires retrieval

```
┌───────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              PHASE ALIGNMENT MATRIX WITH DEPENDENCIES                              │
├───────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                    │
│  TIMELINE     ADR-003 (Memory)      ADR-006 (Chatbot)      INTEGRATION       DEPENDENCIES         │
│  ────────     ────────────────      ────────────────       ───────────       ────────────         │
│                                                                                                    │
│  Weeks 1-4    Phase 0: Foundations  Phase 1: Discord +     Eval harness      None (parallel)      │
│               • Eval harness        Slack parallel         includes                               │
│               • Schema & lifecycle  • Central Gateway      chatbot                                │
│               • Governance/observ.  • LLM orchestration    queries                                │
│                                                                                                    │
│  Weeks 5-8    Phase 1a-1b: Storage  Phase 2: Multi-plat    Chatbot uses      HARD BLOCKER:        │
│               • user_memory table   • Telegram, WhatsApp   conversation_     Memory 1b must       │
│               • conversation_memory • Thread context mgmt  context from      complete BEFORE      │
│               • Async extraction                           Phase 1b          Chatbot Phase 2      │
│                                                                                                    │
│  Weeks 9-12   Phase 1c-1d: Retrieval Phase 3: Beta + ACLs  ACLs use          Soft: Memory 1c      │
│               • Ranking logic        • Usage metering      UsageTracker      recommended but      │
│               • Janitor process      • Authentication      protocol          not required for     │
│               • Memory decay                                                 basic ACLs           │
│                                                                                                    │
│  Weeks 13-16  Phase 2: Context Eng.  Phase 4: GA + Enter.  SSO uses          HARD BLOCKER:        │
│               • Memory blocks        • SSO/SAML (cloud)    TenantProvider    Memory Phase 2       │
│               • Provenance tracking  • Audit logging       + new chatbot     must complete        │
│                                      • GDPR compliance     protocols         BEFORE Context Eng.  │
│                                                                                                    │
│  Weeks 17+    Phase 3: HybridRAG     V2: Voice, advanced   Graph-backed      Memory Phase 3       │
│               • Knowledge graph      • Voice transcription memory for        enables but does     │
│               • Entity extraction    • True streaming      chatbot RAG       not block V2         │
│                                                                                                    │
└───────────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Dependency Summary**:

| Chatbot Phase | Required Memory Phase | Blocker Type |
|---------------|----------------------|--------------|
| Phase 1 (Discord/Slack) | None | Parallel OK |
| Phase 2 (Multi-platform) | Phase 1b (Storage) | HARD |
| Phase 3 (Beta + ACLs) | Phase 1c (Retrieval) | Soft |
| Phase 4 (Enterprise) | Phase 2 (Context Eng) | HARD |
| V2 (Voice) | Phase 3 (HybridRAG) | Soft |

### 4. Compliance Responsibilities by Deployment Type

**ADR-004 Monetization Tier + ADR-006 GDPR Integration**:

| Tier | Deployment | Data Controller | GDPR Status | Deletion Method | Audit Logs |
|------|------------|-----------------|-------------|-----------------|------------|
| **Free** | Self-hosted | User | User's responsibility | Pixeltable CLI/API | Local files |
| **Team** | Cloud-hosted | Amiable | Required | `/forget-me` command | Cloud logs |
| **Enterprise** | VPC/On-prem | Customer | Customer's responsibility | API + CLI | SOC2-compliant |

**GDPR Auto-Deletion Policy (Council Decision)**:

| Tier | Auto-Delete on Workspace Exit | Rationale |
|------|-------------------------------|-----------|
| **Free (OSS)** | No | User controls data; auto-deletion risks unexpected data loss |
| **Team (Cloud)** | **Yes** | Amiable is Data Controller; minimize liability via webhooks |
| **Enterprise** | Configurable | Customers may have legal retention requirements (legal hold) |

**Team Tier Implementation**:
```python
# Webhook triggered on workspace exit
@workspace_webhook("member_left")
async def handle_member_exit(event: MemberLeftEvent):
    if event.workspace.tier == "team":
        # Auto-trigger GDPR deletion for Team tier
        await gdpr_service.delete_user_data(
            user_id=event.user_id,
            workspace_id=event.workspace_id,
            confirmed=True,  # No confirmation needed for auto-deletion
            reason="workspace_exit_auto_purge"
        )
```

**Implementation Location**:

| Component | Repository | Rationale |
|-----------|------------|-----------|
| DefaultAccessControlPolicy | luminescent-cluster | OSS permissive default |
| ConfigurableAccessControlPolicy | luminescent-cluster | Self-hosted config |
| ResponseFilterPolicy | luminescent-cluster | Core security |
| CloudAccessController | luminescent-cloud | Requires workspace SSO |
| GDPRService | luminescent-cloud | Hosted data processor |

### 5. Implementation Status Tracking (Council Revised: Hybrid Approach)

**Tracking Strategy**: Automated coverage + manual validation (not pure test coverage).

| Column | Source | Purpose |
|--------|--------|---------|
| Tests | Automated (CI) | Objective metric from Codecov |
| Coverage | Automated (CI) | % of lines covered |
| Validation | Manual | Architectural sign-off |

Unified status format across ADRs:

| ADR | Component | Status | Tests | Coverage | Validation | Location |
|-----|-----------|--------|-------|----------|------------|----------|
| **ADR-003** | Session Memory MCP | Implemented | 45 | 89% | Validated | `src/session_memory_server.py` |
| ADR-003 | Pixeltable MCP | Implemented | 62 | 91% | Validated | `src/pixeltable_mcp_server.py` |
| ADR-003 | Phase 0 (Eval harness) | Not started | - | - | Pending | - |
| ADR-003 | Phase 1 (Conversational Memory) | Not started | - | - | Pending | - |
| **ADR-005** | Extension Protocols | Implemented | 18 | 95% | Validated | `src/extensions/` |
| ADR-005 | CloudTenantProvider | Implemented | 12 | 88% | Validated | `cloud/extensions/` |
| ADR-005 | StripeUsageTracker | Implemented | 8 | 82% | Validated | `cloud/extensions/` |
| **ADR-006** | Discord Adapter | Implemented | 87 | 94% | Validated | `src/chatbot/adapters/discord.py` |
| ADR-006 | Slack Adapter | Implemented | 89 | 93% | Validated | `src/chatbot/adapters/slack.py` |
| ADR-006 | Telegram Adapter | Implemented | 82 | 91% | Validated | `src/chatbot/adapters/telegram.py` |
| ADR-006 | WhatsApp Adapter | Implemented | 75 | 89% | Validated | `src/chatbot/adapters/whatsapp.py` |
| ADR-006 | Central Gateway | Implemented | 45 | 87% | Validated | `src/chatbot/gateway.py` |
| ADR-006 | Context Persistence | Implemented | 18 | 92% | Validated | `src/chatbot/context.py` |
| ADR-006 | ChatMetrics | Implemented | 12 | 85% | Validated | `src/chatbot/metrics.py` |
| ADR-006 | CloudAccessController | Implemented | 18 | 96% | Validated | `cloud/chatbot/access_controller.py` |
| ADR-006 | GDPRService | Implemented | 19 | 94% | Validated | `cloud/chatbot/gdpr_service.py` |

**Total Tests**: 1303 (1168 cluster + 135 cloud)

---

## Data Flow Examples

### Example 1: Discord Query to Memory Retrieval

```
1. User: "@luminescent What auth method did we choose?"
   └──▶ Discord Adapter receives message

2. Discord Adapter normalizes to ChatMessage
   └──▶ Central Gateway

3. Gateway checks access (via ChatbotAccessController protocol)
   ├── OSS: DefaultAccessControlPolicy → Allow all
   └── Cloud: CloudAccessController → Check workspace membership

4. Gateway routes to LLM Orchestration
   └──▶ LLM calls MCP tools

5. LLM calls pixeltable_mcp.search_organizational_memory("auth method")
   └──▶ Tier 2: Long-term Memory

6. Pixeltable queries org_knowledge table
   ├── OSS: Local ~/.pixeltable/
   └── Cloud: Managed Pixeltable (tenant-filtered via TenantProvider)

7. Results returned with citations
   └──▶ Gateway

8. Gateway tracks usage (via UsageTracker protocol)
   ├── OSS: No-op
   └── Cloud: StripeUsageTracker.track("query", tokens, metadata)

9. Response formatted for Discord
   └──▶ User sees answer with ADR link
```

### Example 2: GDPR Deletion Request

```
1. User: "@luminescent /forget-me"
   └──▶ WhatsApp Adapter

2. Gateway recognizes GDPR command
   └──▶ Check if Cloud deployment (protocol available)

3. If OSS:
   └──▶ Respond: "Self-hosted: Use Pixeltable CLI to manage your data"

4. If Cloud:
   └──▶ GDPRService.delete_user_data(user_id, workspace_id, confirmed=False)

5. GDPRService returns summary (requires confirmation)
   └──▶ User: "You have 47 conversations, 12 knowledge items. Confirm deletion?"

6. User confirms
   └──▶ GDPRService.delete_user_data(..., confirmed=True)

7. AuditLogger.log_gdpr_deletion(...)
   └──▶ Compliance audit trail

8. User: "Your data has been deleted per GDPR Article 17."
```

---

## Consequences

### Positive

- **Single source of truth** for cross-ADR integration
- **Clear protocol definitions** for all extension points
- **Phase alignment** prevents implementation conflicts
- **Compliance clarity** by deployment type
- **Unified status tracking** across all ADRs

### Negative

- **Additional ADR to maintain** when underlying ADRs change
- **Risk of drift** if ADRs are updated without updating this document

### Mitigations

| Risk | Mitigation |
|------|------------|
| ADR drift | Add "Related Decisions" section to each ADR pointing here |
| Protocol changes | Semantic versioning on protocol definitions |
| Status staleness | Automated test count extraction in CI |

---

## Council Decisions (Resolved)

The LLM Council reviewed ADR-007 and provided the following decisions:

### Q1: Protocol Versioning
**Decision**: YES (Critical)

All protocols must use Semantic Versioning (SemVer) for cross-repo compatibility:
- Allows chatbot adapters to lag behind core orchestrator without breaking service
- Minimum 6-month support for deprecated versions
- Version constants added to `protocols.py`

### Q2: Phase Dependencies
**Decision**: YES - Hard blockers exist

| Blocker | Rationale |
|---------|-----------|
| Memory Phase 1b → Chatbot Phase 2 | Cannot persist context across platforms without storage layer |
| Memory Phase 2 → Chatbot Phase 4 | Advanced context engineering requires retrieval infrastructure |

Added "Dependencies" column to Phase Alignment Matrix.

### Q3: GDPR Auto-Deletion
**Decision**: CONDITIONAL

| Tier | Auto-Delete | Rationale |
|------|-------------|-----------|
| Free (OSS) | No | User controls data; auto-deletion risks unexpected loss |
| Team (Cloud) | **Yes** | Amiable is Data Controller; minimize liability |
| Enterprise | Configurable | Legal retention requirements may supersede |

Implementation via webhooks triggered by workspace exit events.

### Q4: Status Automation
**Decision**: HYBRID APPROACH

- **Automated**: Test count and coverage from CI (Codecov)
- **Manual**: Architectural validation sign-off
- **Rationale**: Pure test coverage is a vanity metric; having a test doesn't mean ADR requirement is met functionally

---

## Council Review Summary

**Review Date**: 2025-12-28
**Council Configuration**: High confidence tier (2 of 4 models responded)
**Models Responding**: GPT-4o, Grok-4
**Models Errored**: Gemini-3-Pro, Claude Opus 4.5

### Verdict

The Council finds ADR-007 **fundamentally sound and highly effective** at resolving structural fragmentation between ADRs 003-006. It successfully acts as the necessary "glue" document.

### Unanimous Recommendations (All Incorporated)

1. **Add Security Overlay** - Show distinct enforcement points in architecture diagram
2. **Add Error Handling & Resilience** - Define failure modes and behavior
3. **Add Migration Strategy** - Guide for transitioning to new Extension Registry
4. **Update Phase Matrix with Dependencies** - Explicit hard/soft blockers
5. **Protocol Versioning (SemVer)** - Critical for cross-repo compatibility
6. **Hybrid Status Tracking** - Automated coverage + manual validation

### Key Insights by Model

- **GPT-4o**: "The unified diagram resolves siloed thinking; add security overlay for enforcement points"
- **Grok-4**: "Phase Alignment Matrix is the strongest addition; add Dependencies column for explicit blockers"

### Actions Taken

| Recommendation | Section Updated |
|----------------|-----------------|
| Security Overlay | Section 1a added |
| Error Handling | Section 1b added |
| Migration Strategy | Section 1c added |
| Phase Dependencies | Section 3 updated |
| Protocol Versioning | Section 2 updated |
| GDPR Conditional | Section 4 updated |
| Hybrid Status | Section 5 updated |

---

## Related Decisions

- **ADR-003**: Project Intent (Memory Architecture) - Defines tiers and phases
- **ADR-004**: Monetization Strategy - Defines pricing tiers referenced in compliance section
- **ADR-005**: Repository Organization - Defines dual-repo and protocol pattern
- **ADR-006**: Chatbot Platform Integrations - Defines adapters and gateway

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-28 | Initial draft: Integration map, protocol consolidation, phase alignment, compliance matrix |
| 1.1 | 2025-12-28 | **Council Validated**: Added Security Overlay (1a), Error Handling & Resilience (1b), Migration Strategy (1c). Updated Phase Matrix with explicit dependencies. Added Protocol Versioning (SemVer). Added GDPR auto-deletion policy by tier. Updated status tracking with hybrid approach. Resolved all 4 open questions. |
| 1.2 | 2025-12-28 | **Implementation Complete**: All protocol layer changes (OSS) and cloud implementations (Private) completed via TDD. All issues closed. |
| 1.3 | 2026-01-08 | **Maintenance**: Updated test counts (1168 OSS, 135 cloud). Consolidated duplicate MemoryProvider to single source in extensions. |

---

## Implementation Tracker

### luminescent-cluster (OSS)

| Issue | Title | Status | Tests | Notes |
|-------|-------|--------|-------|-------|
| #71 | Add Protocol Version Constants | ✅ Complete | 20 | Version constants for all protocols |
| #72 | Consolidate ContextStore | ✅ Complete | 18 | Moved to protocols.py, added to registry |
| #73 | Add GDPR Audit Methods | ✅ Complete | 7 | log_gdpr_deletion, log_gdpr_export |
| #74 | Integrate Response Filtering | ✅ Complete | 10 | ResponseFilter protocol, registry slot |
| #75 | Add Usage Tracking | ✅ Complete | 7 | usage_tracker.track() in gateway |
| #76 | Fix Gateway Fail-Closed | ✅ Complete | 6 | CRITICAL security fix |

**Total OSS Tests**: 1168 (all passing)

### luminescent-cloud (Private)

| Issue | Title | Status | Tests | Notes |
|-------|-------|--------|-------|-------|
| #5 | GDPR Methods in CloudAuditLogger | ✅ Complete | 9 | Protocol compliance verified |
| #6 | Workspace Event Webhooks | ✅ Complete | 12 | Team tier auto-deletion via webhooks |
| #7 | Implement CloudContextStore | ✅ Complete | 19 | Tenant-isolated persistence |
| #8 | Register CloudAccessController | ✅ Complete | - | Added to startup.py |
| #9 | Update GDPRService | ✅ Complete | - | Already uses audit methods |

**Total Cloud Tests**: 135 (all passing)
