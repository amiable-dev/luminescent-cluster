# Chatbot Integration Requirements

Requirements for chatbot adapters, gateway, and platform integrations.

**Primary ADR**: ADR-006

---

## Gateway Architecture

### REQ-BOT-001: Central Gateway
**Source**: ADR-006 Architecture
**Status**: Active
**Priority**: High

All chatbot adapters MUST route through a central Chat Gateway that handles:
- Message normalization
- Context retrieval
- LLM orchestration
- Response formatting

**Test Mapping**:
- `tests/chatbot/test_gateway.py::test_central_routing`
- `tests/chatbot/test_gateway.py::test_message_normalization`

---

### REQ-BOT-002: Thin Adapter Pattern
**Source**: ADR-006 Architecture
**Status**: Active
**Priority**: High

Platform adapters MUST be thin (~300 LOC), handling only:
- Platform-specific authentication
- Message format conversion
- Platform API calls

**Test Mapping**:
- `tests/chatbot/test_adapters.py::test_adapter_simplicity`

---

### REQ-BOT-003: Platform Parity
**Source**: ADR-006 Decision
**Status**: Active
**Priority**: High

All four platforms (Slack, Discord, Telegram, WhatsApp) MUST have feature parity for core functionality.

**Test Mapping**:
- `tests/chatbot/test_adapters.py::test_feature_parity`

---

## Thread Context

### REQ-BOT-010: Thread Context Persistence
**Source**: ADR-006 Council Decisions
**Status**: Active
**Priority**: High

Thread context MUST persist with:
- Last 10 messages
- 24-hour TTL
- Per-thread isolation

**Test Mapping**:
- `tests/chatbot/test_context.py::test_message_limit`
- `tests/chatbot/test_context.py::test_ttl_expiration`
- `tests/chatbot/test_context.py::test_thread_isolation`

---

### REQ-BOT-011: Context Store Backend
**Source**: ADR-006 Context Persistence
**Status**: Active
**Priority**: High

Thread context MUST be storable in Pixeltable with 90-day retention (configurable).

**Test Mapping**:
- `tests/chatbot/test_context.py::test_pixeltable_storage`
- `tests/chatbot/test_context.py::test_retention_policy`

---

## Rate Limiting

### REQ-BOT-020: Free Tier Limits
**Source**: ADR-006 Tier Definitions
**Status**: Active
**Priority**: High

Free tier MUST enforce 100 queries/month limit.

**Test Mapping**:
- `tests/chatbot/test_rate_limiting.py::test_free_tier_limit`
- `tests/chatbot/test_rate_limiting.py::test_limit_enforcement`

---

### REQ-BOT-021: Rate Limit Feedback
**Source**: ADR-006 User Experience
**Status**: Active
**Priority**: Medium

When rate limited, users MUST receive a clear message with:
- Current usage
- Limit details
- Upgrade options

**Test Mapping**:
- `tests/chatbot/test_rate_limiting.py::test_limit_message`

---

## Access Control

### REQ-BOT-030: Default Access Policy
**Source**: ADR-006 Access Control
**Status**: Active
**Priority**: High

DefaultAccessControlPolicy (OSS) MUST allow all channels and commands by default.

**Test Mapping**:
- `tests/chatbot/test_access_control.py::test_default_policy`

---

### REQ-BOT-031: Configurable Access Policy
**Source**: ADR-006 Access Control
**Status**: Active
**Priority**: High

ConfigurableAccessControlPolicy MUST support:
- `allowed_channels`
- `blocked_channels`
- `allowed_commands`

**Test Mapping**:
- `tests/chatbot/test_access_control.py::test_configurable_policy`
- `tests/chatbot/test_access_control.py::test_channel_filtering`
- `tests/chatbot/test_access_control.py::test_command_filtering`

---

### REQ-BOT-032: Response Filtering
**Source**: ADR-006 Access Control
**Status**: Active
**Priority**: High

ResponseFilterPolicy MUST filter sensitive data patterns (passwords, API keys) in public channels.

**Test Mapping**:
- `tests/chatbot/test_access_control.py::test_response_filtering`
- `tests/chatbot/test_access_control.py::test_sensitive_pattern_redaction`

---

## Observability

### REQ-BOT-040: Chat Metrics
**Source**: ADR-006 Observability
**Status**: Active
**Priority**: Medium

ChatMetrics MUST record:
- Platform
- User ID
- Query type
- Latency (ms)
- Tokens used
- Memory hits

**Test Mapping**:
- `tests/chatbot/test_metrics.py::test_metric_recording`
- `tests/chatbot/test_metrics.py::test_metric_fields`

---

## Negative Obligations

### NEG-BOT-001: No True Streaming (V1)
**Source**: ADR-006 Council Decisions
**Status**: Active
**Priority**: Medium

V1 MUST NOT use true streaming. Use batched with pseudo-streaming ("Thinking..." placeholders).

**Test Mapping**:
- `tests/chatbot/test_gateway.py::test_no_true_streaming`
- `tests/chatbot/test_gateway.py::test_pseudo_streaming`

---

### NEG-BOT-002: No Voice Processing (V1)
**Source**: ADR-006 Council Decisions
**Status**: Active
**Priority**: Low

V1 MUST NOT process voice/audio attachments. API should accept but not process.

**Test Mapping**:
- `tests/chatbot/test_gateway.py::test_no_voice_processing`
