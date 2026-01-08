# ADR-003: Project Intent - Persistent Technical Context for AI Development

**Status**: Accepted
**Date**: 2025-12-22
**Decision Makers**: Development Team
**Owners**: @christopherjoseph
**Version**: 4.6 (Security Hardening)

## Decision Summary

We adopt a **Memory-First** architecture using **MCP**, implementing a phased approach that prioritizes foundations and quick wins before architectural complexity:

1. **Phase 0**: Evaluation, governance, and observability foundations
2. **Phase 1**: Mem0 for immediate personalization and conversational memory
3. **Phase 2**: Context Engineering for optimized retrieval
4. **Phase 3**: HybridRAG with Knowledge Graph for complex queries
5. **Phase 4**: Advanced features (Hindsight, MaaS) as needed

We reject simple Vector-only RAG as insufficient for code logic and dependency reasoning.

---

## Critical Architecture Decision: Build vs. Integrate (Mem0)

### The Question

Should we integrate Mem0 for conversational memory, or build equivalent capabilities on Pixeltable?

| Capability | Pixeltable | Mem0 |
|------------|------------|------|
| Vector embeddings | ✓ | ✓ |
| Semantic search | ✓ | ✓ |
| Structured metadata | ✓ | ✓ |
| Graph relationships | Partial | ✓ (Mem0g) |
| User/session scoping | Manual | Built-in |
| Memory extraction | Manual | Automatic |

### Council Decision: Build on Pixeltable (Option B)

**All 4 models unanimously agreed**: Pixeltable must remain the canonical source of truth.

#### The "Split Brain" Problem

Integrating Mem0 creates two vector databases:
```
User Query → MCP Server → ???
                         ├→ Pixeltable (code, ADRs, incidents)
                         └→ Mem0 (conversations, preferences)
                                  └→ Its own vector DB
```

**Problems this creates:**
- Two sources of truth with different consistency models
- Cross-system queries for "What did we decide about auth?" are complex
- Different score scales make result merging difficult
- Debugging spans two systems with different logging

#### Why Pixeltable Can Replace Mem0

Mem0's primary value (extraction + scoping) can be replicated using Pixeltable's computed columns:

```python
# Memory extraction via LLM UDF (computed column)
@pt.computed_column
def extract_memory_facts(row) -> list[dict]:
    """Extract memorable facts from conversation."""
    prompt = """
    Analyze this conversation and extract:
    1. User preferences (explicit and implicit)
    2. Decisions made
    3. Facts learned about the codebase
    4. Corrections to previous understanding
    Return as structured JSON with confidence scores.
    """
    return llm_extract(prompt, row.content)

# User/session scoping
@pt.computed_column
def memory_scope(row) -> dict:
    return {
        "user_id": row.user_id,
        "project_id": row.project_id,
        "scope_hierarchy": [
            f"user:{row.user_id}",
            f"project:{row.project_id}",
            "global"
        ]
    }

# Memory consolidation (dedup, merge, supersede)
class MemoryConsolidator:
    async def consolidate(self, new_memory: Memory) -> ConsolidationResult:
        similar = await self.find_similar(new_memory, threshold=0.85)
        if not similar:
            return ConsolidationResult(action="insert", memory=new_memory)
        # Handle contradictions, merges, supersedes...
```

#### Decision Matrix

| Criteria | A) Integrate Mem0 | B) Build on Pixeltable |
|----------|------------------|----------------------|
| Time to MVP | 2-3 weeks | 4-6 weeks |
| Maintenance burden | High (two systems) | Low (one system) |
| Feature velocity | Fast initially, slows | Slower initially, compounds |
| Architectural simplicity | Poor | **Excellent** |
| Long-term flexibility | Limited by Mem0's roadmap | **Full control** |
| Debugging | High complexity | **Low complexity** |
| Data consistency | Two sources of truth | **Single source** |

### Accepted Trade-offs

- **Longer initial development** (6 weeks vs 2-3 weeks)
- **Must build extraction/consolidation logic** ourselves
- **No access to Mem0's ongoing R&D**

### Validation Criteria (Phase 1 Exit)

- Memory retrieval latency < 200ms p95
- Extraction accuracy > 80% (manual evaluation)
- Zero cross-user memory leakage

---

## Context

### The Problem: Ephemeral AI Context

Large Language Models (LLMs) suffer from a fundamental limitation: **context window amnesia**. Each conversation starts fresh, forcing developers to repeatedly explain:

- Project architecture and design decisions
- Coding conventions and patterns
- Past incidents and their resolutions
- Domain-specific terminology
- Team decisions and their rationale

This creates three significant pain points:

1. **Repetitive Context Loading**: Developers waste time re-establishing context every session
2. **Lost Institutional Knowledge**: Valuable decisions and learnings evaporate between conversations
3. **Inconsistent Assistance**: Without historical context, AI suggestions may contradict past decisions

### The Vision: Persistent Technical Memory

Luminescent Cluster aims to give AI assistants **persistent technical memory** - the ability to recall project context, architectural decisions, incident history, and codebase knowledge across sessions and even across different LLM providers.

### Industry Context (December 2025)

The LLM memory landscape has evolved rapidly. Key developments:

- **MCP Standardization**: The Model Context Protocol is now the de-facto standard, adopted by OpenAI, Google DeepMind, Microsoft, and AWS. In December 2025, Anthropic donated MCP to the Linux Foundation's Agentic AI Foundation (AAIF).
- **Beyond RAG**: Traditional RAG is being challenged by agentic memory architectures that maintain context over time, track evolving beliefs, and perform temporal reasoning.
- **Production Scale**: Systems like Mem0 have achieved 26% accuracy improvements with 91% lower latency and 90% token savings at enterprise scale (186M API calls/Q3 2025).
- **Context Engineering**: A new discipline focused on "the delicate art and science of filling the context window with just the right information" (Andrej Karpathy).

## Decision Drivers (Ranked)

| Priority | Driver | Weight | Rationale |
|----------|--------|--------|-----------|
| 1 | **Developer Experience** | 30% | Reduce repetition friction; faster onboarding |
| 2 | **Accuracy** | 25% | Retrieved context must be relevant and correct |
| 3 | **Token Efficiency** | 20% | Context window is expensive; minimize waste |
| 4 | **Implementation Velocity** | 15% | Need wins this quarter to validate approach |
| 5 | **Future Flexibility** | 10% | Don't lock in prematurely; enable pivots |

## Non-Goals

This ADR explicitly does **not** address:

- **Multi-tenant implementation details**: Multi-tenancy is technically supported via the Extension Registry (ADR-005) and unified in the integration layer (ADR-007). This ADR remains focused strictly on memory architecture; tenant isolation is treated here as an external constraint rather than a core feature
- **General documentation RAG**: Focus is on technical context, not help docs
- **AGI-style continuous learning**: Memory is curated, not autonomous
- **PII/secrets storage**: Sensitive data excluded by policy
- **Training custom models**: Memory augments existing LLMs, doesn't train new ones

## Success Metrics (Quantified)

| Metric | Baseline | Target | Measurement |
|--------|----------|--------|-------------|
| Context re-explanation frequency | ~5/session | <1/session | User survey |
| Context retrieval latency | N/A | <500ms p95 | Instrumentation |
| Retrieval precision@5 | N/A | >85% | LongMemEval subset |
| Token efficiency | N/A | <30% of window for memory | Context analysis |
| Multi-hop query accuracy | N/A | >75% | Internal benchmark |
| Developer satisfaction (NPS) | N/A | >50 | Quarterly survey |

## Decision

We implement a **three-tier memory architecture** exposed via the Model Context Protocol (MCP):

### Tier 1: Session Memory (Hot Context)
**Purpose**: Fast access to current development state
**Implementation**: `session_memory_server.py`
**Data Sources**:
- Git repository state (current branch, status)
- Recent commits (last 200)
- Current diff (staged/unstaged changes)
- File change history
- Active task context (set by user/agent)

**Characteristics**:
- Latency: <10ms (in-memory)
- Scope: Current repository
- Persistence: Ephemeral (session-bound)
- Cost: Zero (local computation)

### Tier 2: Long-term Memory (Persistent Knowledge)
**Purpose**: Semantic search over organizational knowledge
**Implementation**: `pixeltable_mcp_server.py` + `pixeltable_setup.py`
**Data Sources**:
- Code repositories (multi-service)
- Architectural Decision Records (ADRs)
- Production incident history
- Meeting transcripts
- Documentation

**Characteristics**:
- Latency: 100-500ms (semantic search)
- Scope: Entire organization, cross-project
- Persistence: Durable (survives restarts)
- Cost: Embedding generation (local sentence-transformers by default)

### Tier 3: Intelligent Orchestration
**Purpose**: Efficient multi-tool coordination
**Mechanisms**:
- **Tool Search**: On-demand tool discovery (85% token reduction)
- **Programmatic Tool Calling**: Batch operations in sandbox (37% token reduction)
- **Deferred Loading**: Heavy tools loaded only when needed

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     AI Assistant (Claude, etc.)                  │
├─────────────────────────────────────────────────────────────────┤
│                    Model Context Protocol (MCP)                  │
├────────────────┬────────────────────────┬───────────────────────┤
│   Tier 1       │       Tier 2           │      Tier 3           │
│ Session Memory │   Long-term Memory     │   Orchestration       │
├────────────────┼────────────────────────┼───────────────────────┤
│ • Git state    │ • Pixeltable DB        │ • Tool Search         │
│ • Recent commits│ • Semantic embeddings │ • Programmatic Calls  │
│ • Current diff │ • Multi-project index  │ • Deferred Loading    │
│ • Task context │ • ADRs, incidents      │                       │
└────────────────┴────────────────────────┴───────────────────────┘
```

## Interface Contract (MCP)

> **Implementation Note**: These interface definitions represent the conceptual architectural vision. For live, versioned protocol signatures (including `ContextStore`, `TenantProvider`, and `AuditLogger`), refer to `src/extensions/protocols.py` as consolidated in ADR-007. Chatbot-specific implementations of these interfaces are provided by the adapters defined in ADR-006.

The memory system exposes the following MCP resources and tools:

### Resources (Read-Only Context)
```
project://memory/recent_decisions     # Last N architectural decisions
project://memory/active_incidents     # Open incidents affecting this service
project://memory/conventions          # Coding patterns and team standards
project://memory/dependency_graph     # Service relationships (Phase 3+)
```

### Tools (Actions)
```python
# Session Memory Tools
set_task_context(task: str, details: dict)  # Set current work context
get_task_context() -> TaskContext           # Retrieve current context
search_commits(query: str) -> list[Commit]  # Search commit history

# Long-term Memory Tools
semantic_search(query: str, limit: int) -> list[Result]
ingest_code(path: str, service: str)        # Index codebase
ingest_adr(path: str, service: str)         # Index decision record
ingest_incident(summary: str, severity: str, lessons: str)

# Memory Management (Phase 0+)
update_memory(key: str, value: Any, source: str)  # With provenance
invalidate_memory(key: str, reason: str)          # Explicit expiration
get_memory_provenance(key: str) -> Provenance     # Audit trail
```

## Key Design Principles

### 1. LLM-Agnostic via MCP
The system uses the Model Context Protocol (MCP), making it portable across:
- Claude (via Claude Code)
- OpenAI ChatGPT (MCP support added March 2025)
- Google Gemini (MCP support announced April 2025)
- Custom agents via programmatic access

### 2. Semantic Search over Keyword Matching
Long-term memory uses sentence-transformer embeddings for semantic similarity:
```python
# Find conceptually related code, not just keyword matches
"authentication flow" → finds OAuth, JWT, session handling code
```

### 3. Multi-Project Awareness
Knowledge is indexed by `service_name`, enabling:
- Cross-project searches ("How does auth-service handle tokens?")
- Project-specific filtering ("Show incidents for payment-api only")
- Organizational patterns ("What database patterns do we use?")

### 4. Automatic Embedding Maintenance
Pixeltable's computed columns automatically recompute embeddings when content changes:
```python
# Embeddings stay in sync - no manual refresh needed
embedding=kb.content.apply(embed_text)
```

### 5. Defense in Depth (Python Version)
Per ADR-001, the system includes 7 layers of protection against Python version mismatch issues that could corrupt the Pixeltable database.

## Use Cases

### 1. Architectural Continuity
```
User: "Why did we choose PostgreSQL over MongoDB?"
AI: [Queries ADRs] "ADR-005 documents this decision from March 2024..."
```

### 2. Incident-Aware Development
```
User: "I'm adding rate limiting to the auth service"
AI: [Queries incidents] "Note: We had an outage in November due to rate limiter
     misconfiguration. The post-mortem recommended..."
```

### 3. Cross-Session Context
```
Session 1: User sets task context "Implementing OAuth2 PKCE flow"
Session 2: AI recalls task context and relevant ADRs automatically
```

### 4. Codebase Navigation
```
User: "How do we handle database connections?"
AI: [Semantic search] "Based on auth-service/db/pool.py and the connection
     pooling ADR, you use..."
```

## Rationale

### Why Not Just Use RAG?
Traditional RAG (Retrieval Augmented Generation) typically:
- Requires manual chunk management
- Needs explicit embedding refresh
- Lacks structured metadata (service, type, severity)
- Doesn't integrate with development workflow

Luminescent Cluster adds:
- **Computed columns**: Auto-updating embeddings
- **Typed knowledge**: Code vs ADR vs incident with different schemas
- **Git integration**: Session memory tied to repository state
- **MCP exposure**: Native tool integration with AI assistants

### Why MCP over Custom APIs?
- **Standardized**: Works with any MCP-compatible client
- **Discoverable**: Tools are self-documenting
- **Composable**: Clients can orchestrate multiple MCP servers
- **Future-proof**: Now backed by Linux Foundation with industry-wide adoption

### Why Pixeltable?
- **Computed columns**: Embeddings auto-update on content change
- **Multimodal ready**: Can extend to images, videos
- **Snapshot/restore**: Built-in versioning for knowledge base
- **Python-native**: Fits development workflow

---

## Improvement Options (December 2025 Research)

Based on current industry developments, the following enhancement options are presented for council review:

### Option A: HybridRAG - Knowledge Graph Integration

**What**: Combine vector embeddings with a knowledge graph for multi-hop reasoning.

**Industry Evidence**:
- Microsoft Research shows 2.8x accuracy improvement with hybrid approaches
- GraphRAG (Microsoft) constructs knowledge graphs from unstructured data
- Cedars-Sinai's AlzKB demonstrates real-world HybridRAG success

**Implementation**:
```
┌─────────────────────────────────────────────────────────────────┐
│                      HybridRAG Architecture                     │
├────────────────────────┬────────────────────────────────────────┤
│   Vector Search        │      Graph Traversal                   │
│   (Pixeltable)         │      (Neo4j/Memgraph)                  │
├────────────────────────┼────────────────────────────────────────┤
│ • Semantic similarity  │ • Entity relationships                 │
│ • Fuzzy matching       │ • Multi-hop reasoning                  │
│ • Fast retrieval       │ • Causal chains                        │
└────────────────────────┴────────────────────────────────────────┘
                         │
                         ▼
              Reciprocal Rank Fusion
                         │
                         ▼
                  Neural Reranker
```

**Benefits**:
- Multi-hop reasoning: "What services depend on the auth module that had the incident?"
- Explicit relationships: Code → ADR → Incident → Resolution chains
- Better temporal reasoning: Track how decisions evolved

**Tradeoffs**:
- Additional infrastructure (graph database)
- Data modeling complexity
- Sync between vector and graph stores

**Effort**: Medium-High
**Impact**: High for complex organizational queries

---

### Option B: Mem0 Integration

**What**: Integrate Mem0's production-proven memory layer alongside Pixeltable.

**Industry Evidence**:
- 26% accuracy improvement, 91% lower p95 latency, 90% token savings
- 41K GitHub stars, 14M downloads, 186M API calls/quarter
- AWS chose Mem0 as exclusive memory provider for Agent SDK
- SOC 2 & HIPAA compliant

**Architecture**:
```
┌─────────────────────────────────────────────────────────────────┐
│                        Memory Layer                             │
├────────────────────────┬────────────────────────────────────────┤
│   Pixeltable           │      Mem0                              │
│   (Long-term KB)       │      (Conversational Memory)           │
├────────────────────────┼────────────────────────────────────────┤
│ • Codebase index       │ • User preferences                     │
│ • ADRs & incidents     │ • Conversation facts                   │
│ • Static knowledge     │ • Dynamic learning                     │
│ • Service-scoped       │ • User/session-scoped                  │
└────────────────────────┴────────────────────────────────────────┘
```

**Benefits**:
- Production-proven scale and performance
- Graph-based memory variant (Mem0g) for relational knowledge
- Three-line integration
- Enterprise compliance built-in

**Tradeoffs**:
- External dependency (cloud or self-hosted)
- Potential overlap with Pixeltable functionality
- Additional cost for hosted version

**Effort**: Low-Medium
**Impact**: High for personalization and learning

---

### Option C: Hindsight Agentic Memory

**What**: Adopt the four-network memory architecture that achieved 91.4% on LongMemEval.

**Industry Evidence**:
- Highest accuracy on LongMemEval benchmark (December 2025)
- Designed specifically for agents needing temporal/causal reasoning
- TEMPR retrieval: semantic + keyword + graph + temporal filtering

**Four Network Architecture**:
```
┌──────────────────────────────────────────────────────────────────┐
│                    Hindsight Memory Networks                      │
├─────────────────┬─────────────────┬─────────────────┬────────────┤
│   World         │   Bank          │   Opinion       │ Observation│
│   Network       │   Network       │   Network       │ Network    │
├─────────────────┼─────────────────┼─────────────────┼────────────┤
│ External facts  │ Agent's own     │ Subjective      │ Neutral    │
│ about the world │ experiences &   │ judgments with  │ entity     │
│                 │ actions         │ confidence      │ summaries  │
└─────────────────┴─────────────────┴─────────────────┴────────────┘
```

**Mapped to Luminescent Cluster**:
- **World Network**: Codebase structure, API contracts, dependencies
- **Bank Network**: What the AI has done, commits made, PRs reviewed
- **Opinion Network**: Code quality assessments, architecture preferences
- **Observation Network**: Service summaries, team conventions

**Benefits**:
- Separates facts from opinions (prevents hallucination bleed)
- Tracks agent's own actions (audit trail)
- Temporal filtering for time-sensitive queries
- Open source (Apache 2.0)

**Tradeoffs**:
- Significant architectural change
- New data model required
- Less mature than Mem0 (newer project)

**Effort**: High
**Impact**: Very High for long-horizon agent tasks

---

### Option D: Context Engineering Enhancements

**What**: Implement advanced context management strategies.

**Industry Evidence**:
- ACE framework: +10.6% on agents, +8.6% on finance benchmarks
- Google ADK's Context Compaction reduces latency/tokens
- Anthropic found isolated contexts outperform single-agent approaches

**Strategies**:

1. **Memory Blocks**: Structure context into discrete functional units
```
┌─────────────────────────────────────────────────────────────────┐
│                      Memory Block Layout                        │
├─────────────────────────────────────────────────────────────────┤
│ [System Block]     │ Core instructions, persona                 │
│ [Project Block]    │ Current project context, conventions       │
│ [Task Block]       │ Active task, goals, constraints            │
│ [History Block]    │ Compressed conversation history            │
│ [Knowledge Block]  │ Retrieved ADRs, incidents, code            │
└─────────────────────────────────────────────────────────────────┘
```

2. **Context Compaction**: Auto-summarize when threshold reached
3. **Selective Retrieval**: Pull only relevant knowledge per query
4. **Context Isolation**: Split complex tasks across subagents

**Benefits**:
- Reduces "context rot" from oversized windows
- Clear separation of concerns
- Enables monitoring and debugging
- Works with existing infrastructure

**Tradeoffs**:
- Requires client-side coordination
- MCP servers may not have visibility into full context
- Summarization can lose nuance

**Effort**: Medium
**Impact**: Medium-High for efficiency

---

### Option E: Memory as a Service (MaaS)

**What**: Shift from agent-bound memory to shared memory services for multi-agent collaboration.

**Industry Evidence**:
- Research shows agent memory silos hinder collaboration
- MaaS paradigm emerging for multi-agent systems
- Enables organizational memory shared across tools/agents

**Architecture**:
```
┌─────────────────────────────────────────────────────────────────┐
│                    Memory as a Service (MaaS)                    │
├─────────────────────────────────────────────────────────────────┤
│                        Shared Memory Layer                       │
│   ┌───────────┐  ┌───────────┐  ┌───────────┐                   │
│   │ Code KB   │  │ Decision  │  │ Incident  │                   │
│   │ Service   │  │ Service   │  │ Service   │                   │
│   └─────┬─────┘  └─────┬─────┘  └─────┬─────┘                   │
│         │              │              │                          │
├─────────┼──────────────┼──────────────┼──────────────────────────┤
│         ▼              ▼              ▼                          │
│   ┌───────────┐  ┌───────────┐  ┌───────────┐                   │
│   │ Claude    │  │ GPT Agent │  │ Custom    │                   │
│   │ Code      │  │           │  │ Pipeline  │                   │
│   └───────────┘  └───────────┘  └───────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

**Benefits**:
- Memory persists regardless of which agent/LLM is used
- Enables handoff between specialized agents
- Organizational knowledge accessible to all tools
- Natural fit for MCP's server architecture

**Tradeoffs**:
- Access control complexity
- Consistency across agents
- Security considerations (MEXTRA attack vulnerabilities)

**Effort**: Medium
**Impact**: High for multi-agent workflows

---

### Option F: LangMem Integration

**What**: Integrate LangChain's LangMem SDK for procedural, episodic, and semantic memory types.

**Industry Evidence**:
- Native integration with LangGraph (popular agent framework)
- DeepLearning.AI course validates approach
- MongoDB, Redis integrations available
- Part of LangChain's production ecosystem

**Memory Types**:
```
┌─────────────────────────────────────────────────────────────────┐
│                      LangMem Memory Types                        │
├─────────────────┬─────────────────┬─────────────────────────────┤
│   Procedural    │   Episodic      │   Semantic                  │
├─────────────────┼─────────────────┼─────────────────────────────┤
│ How to do tasks │ Specific events │ General facts               │
│ (coding styles, │ (this PR, that  │ (architecture,              │
│ conventions)    │ incident)       │ team knowledge)             │
└─────────────────┴─────────────────┴─────────────────────────────┘
```

**Benefits**:
- Well-documented, production-ready
- Multiple persistence backends
- Checkpointing and time-travel
- Large community support

**Tradeoffs**:
- LangChain dependency
- May not integrate directly with MCP
- Overlaps with Pixeltable functionality

**Effort**: Medium
**Impact**: Medium for LangGraph users

---

## Options Comparison Matrix

### Weighted Decision Matrix

| Criterion (Weight) | A: HybridRAG | B: Mem0 | C: Hindsight | D: Context Eng | E: MaaS | F: LangMem |
|-------------------|--------------|---------|--------------|----------------|---------|------------|
| Accuracy (25%) | ★★★★★ | ★★★☆☆ | ★★★★★ | ★★☆☆☆ | ★★★☆☆ | ★★★☆☆ |
| Dev Experience (30%) | ★★★☆☆ | ★★★★★ | ★★★☆☆ | ★★★★☆ | ★★★★☆ | ★★★★☆ |
| Effort/Risk (20%) | ★☆☆☆☆ | ★★★★☆ | ★☆☆☆☆ | ★★★★★ | ★★★☆☆ | ★★★★☆ |
| Maturity (15%) | ★★★☆☆ | ★★★★☆ | ★★☆☆☆ | ★★★★★ | ★★★☆☆ | ★★★★☆ |
| Flexibility (10%) | ★★★★☆ | ★★★☆☆ | ★★★☆☆ | ★★★★★ | ★★★★☆ | ★★★★☆ |
| **Weighted Score** | **2.95** | **3.70** | **2.80** | **3.80** | **3.35** | **3.60** |

### Quantitative Metrics (Hypotheses)

| Option | Accuracy Gain | Latency Impact | Effort | Infrastructure | Best For |
|--------|---------------|----------------|--------|----------------|----------|
| A. HybridRAG | +180% (2.8x)* | +50ms | High | Graph DB | Multi-hop code queries |
| B. Mem0 | +26% | -91% p95 | Low-Med | Cloud/Self-host | User personalization |
| C. Hindsight | +40%** | Neutral | High | New data model | Long-horizon agents |
| D. Context Eng | +10-30% | -30% | Medium | None | Immediate optimization |
| E. MaaS | N/A | Neutral | Medium | API layer | Multi-agent workflows |
| F. LangMem | Moderate | Neutral | Medium | LangChain | LangGraph integration |

*Based on Microsoft GraphRAG research (2024); requires validation on code domains
**Estimated from LongMemEval 91.4% vs ~65% baseline RAG

---

## Additional Industry Developments (Council Additions)

Based on council feedback, the following December 2025 developments were identified as missing:

### Option G: Context Caching (Provider-Side)

**What**: Leverage provider-side context caching (Anthropic, OpenAI, Google) to avoid re-sending stable project context.

**Industry Evidence**:
- By late 2025, all major providers offer context caching
- Cost reduction: 75-90% for repeated project context
- Latency reduction: Eliminate round-trip for cached prefixes

**Implementation**:
```
┌─────────────────────────────────────────────────────────────────┐
│                     Context Caching Flow                        │
├─────────────────────────────────────────────────────────────────┤
│ [Stable Context]          │  [Dynamic Context]                  │
│ • Project architecture    │  • Current task                     │
│ • ADRs & conventions      │  • Recent code changes              │
│ • Team patterns           │  • User query                       │
│        ↓                  │         ↓                           │
│ CACHED (TTL: 1 hour)      │  SENT FRESH                         │
└─────────────────────────────────────────────────────────────────┘
```

**Effort**: Low
**Impact**: High for cost/latency

---

### Option H: Episodic Rollback ("Git for Memory")

**What**: Version control for memory state, enabling rollback when agents go wrong.

**Industry Evidence**:
- Developer expectation from git workflows
- Critical for debugging agent mistakes
- Enables "what if" exploration

**Implementation**:
```python
# Memory checkpoint API
checkpoint = memory.create_checkpoint("before-refactor")
# ... agent makes decisions ...
memory.rollback_to(checkpoint)  # Undo bad decisions
memory.diff(checkpoint, "HEAD")  # Compare states
```

**Effort**: Medium
**Impact**: High for agent reliability

---

### Option I: Provenance & Governance

**What**: Every memory item carries source links, timestamps, confidence, and validity scope.

**Industry Evidence**:
- Enterprise requirement for audit trails
- Prevents hallucination from unverified sources
- Enables "why does the AI think this?" debugging

**Schema**:
```python
@dataclass
class MemoryItem:
    content: str
    source: str           # "PR #402", "ADR-005", "user:chris"
    created_at: datetime
    expires_at: datetime  # TTL-based expiration
    confidence: float     # 0.0-1.0
    verified_by: str      # Human approval if required
```

**Effort**: Medium
**Impact**: High for enterprise trust

---

### Option J: Retrieval-Augmented Thoughts (RAT)

**What**: Interleave retrieval *during* chain-of-thought, not just before generation.

**Industry Evidence**:
- Research shows improved reasoning with mid-thought retrieval
- Addresses "lost in the middle" problem
- More accurate for complex technical queries

**Flow**:
```
Traditional RAG:  [Retrieve] → [Think] → [Respond]
RAT:              [Think] → [Retrieve] → [Think more] → [Retrieve] → [Respond]
```

**Effort**: High (requires reasoning model integration)
**Impact**: High for complex queries

---

### Option K: Temporal Memory Decay (Forgetting Curve)

**What**: Implement forgetting mechanisms so old/unused memories decay in relevance.

**Industry Evidence**:
- "Relevance pollution" is a real problem at scale
- Old decisions may conflict with new ones
- Memory systems need pruning strategies

**Implementation**:
```python
# Decay function
relevance = base_relevance * exp(-λ * days_since_access)
# Re-access refreshes relevance
# Low-relevance items deprioritized in retrieval
```

**Effort**: Low-Medium
**Impact**: Medium for long-term maintenance

## Recommended Roadmap (Council Revised)

**Critical Change**: The council unanimously agreed the original roadmap was "Optimization before Foundation." The revised roadmap prioritizes quick wins and foundations before heavy architectural lifts.

### Phase 0: Foundations (Required First)

**Purpose**: Cannot optimize what you cannot measure

**Deliverables**:
1. **Evaluation Harness**
   - Fixed task set + automated scoring
   - Retrieval quality metrics (precision@k, citation correctness)
   - Latency/cost instrumentation
   - Contradiction/hallucination tests

2. **Memory Schema & Lifecycle**
   - Define memory types (decisions, facts, procedures, preferences)
   - TTL and expiration policies
   - Versioning strategy (Option H foundation)
   - "Source of truth" policy

3. **Governance & Observability**
   - Trace: retrieval → context assembly → model output
   - Log which memories were used and why
   - Audit trail for memory changes
   - Access control framework

**Exit Criteria**: Baseline metrics established, governance policies documented

---

### Phase 1: Conversational Memory (Pixeltable Native) - 8 WEEKS

**Decision**: Build on Pixeltable (not Mem0 integration - see Architecture Decision above)

**Purpose**: Unified memory store with extraction capabilities

**Critical Architecture**: The "Janitor" Pattern (Council Mandated)

Running LLM extraction synchronously kills latency. We adopt a tiered approach:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     HOT / WARM / COLD MEMORY ARCHITECTURE                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  TIER 1: HOT MEMORY (Real-time)                                             │
│  ─────────────────────────────                                              │
│  • Raw chat history retrieval                                               │
│  • No extraction cost                                                        │
│  • Latency: <50ms                                                           │
│                                                                              │
│  TIER 2: WARM MEMORY (Async Extraction)                                     │
│  ──────────────────────────────────────                                     │
│  • Pixeltable computed columns with SMALL model (Llama-3-8B, Haiku)         │
│  • Extraction runs AFTER response sent to user                              │
│  • Latency: Background (no user impact)                                     │
│                                                                              │
│  TIER 3: COLD MEMORY (Scheduled Consolidation)                              │
│  ─────────────────────────────────────────────                              │
│  • "Janitor Process" - nightly batch job                                    │
│  • Uses REASONING model (GPT-4o, Opus) for complex dedup                    │
│  • Merges facts, resolves contradictions, expires old data                  │
│  • Latency: Nightly (no user impact)                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Deliverables** (Extended to 8 Weeks per Council):

1. **Phase 1a: Storage & Hot Memory (Weeks 1-2)**
   - Add `user_memory` table to Pixeltable schema
   - Add `conversation_memory` table with TTL support
   - Implement user/project scoping
   - Basic CRUD through MCP tools
   - Raw retrieval (Hot Memory tier)

2. **Phase 1b: Async Extraction (Weeks 3-4)**
   - Create `extract_memory_facts()` UDF using **small model** (Haiku/Llama-3-8B)
   - **Async execution**: Extract AFTER response sent
   - Confidence scoring and thresholds
   - Extraction determinism: `temperature=0`
   - Store raw source alongside extracted facts for re-processing

3. **Phase 1c: Retrieval & Ranking (Weeks 5-6)**
   - Ranking logic: Hot facts vs Extracted facts
   - Query rewriting for memory search
   - Scope-aware retrieval (user vs project vs global)

4. **Phase 1d: Janitor Process (Weeks 7-8)**
   - Nightly consolidation job using **reasoning model** (GPT-4o)
   - Basic deduplication (>85% similarity threshold)
   - Simple contradiction handling: newer wins, flag for review
   - Memory decay: reduce relevance of unaccessed items
   - **Defer complex contradiction resolution to Phase 2**

**Schema Definition**:
```python
# Pixeltable tables for conversational memory
user_memory = pt.Table(
    "user_memory",
    columns={
        "user_id": pt.String,
        "content": pt.String,
        "memory_type": pt.String,  # preference, fact, decision
        "confidence": pt.Float,
        "source": pt.String,  # conversation_id, manual
        "raw_source": pt.String,  # Original text for re-extraction
        "extraction_version": pt.Int,  # For re-processing on prompt updates
        "created_at": pt.Timestamp,
        "last_accessed_at": pt.Timestamp,  # For decay scoring
        "expires_at": pt.Timestamp,  # TTL support
    },
    computed_columns={
        "embedding": embed_text(content),
        "scope": memory_scope(user_id, project_id),
    }
)
```

**Validation Metrics** (Council Required):

| Metric | Target | Measurement |
|--------|--------|-------------|
| Hot memory latency | <50ms p95 | Instrumentation |
| Extraction precision | >85% | Golden Dataset eval |
| Retrieval relevance | >90% rated "helpful" | Blind evaluation |
| Storage efficiency | <10% duplicates post-consolidation | Automated check |
| Query latency | <200ms p95 | Instrumentation |

**Golden Dataset** (Council Required):
Create 50 static questions representing real project queries:
- "What database do we use?"
- "Why did we reject MongoDB?"
- "What's our logging convention?"
- "Who approved the Kafka decision?"

Run regression tests against Golden Dataset on every PR.

**Exit Criteria**:
- >85% accuracy on Golden Dataset
- Zero cross-user memory leakage
- Janitor process completes in <10 minutes for 10k memories

**Decision Reversal Trigger**:
If Week 4 checkpoint shows extraction precision <70%, evaluate:
1. Scoping down consolidation features
2. Revisiting Mem0 for extraction-only (not storage)

---

### Phase 2: Context Engineering Optimization

**Options**: D (Context Engineering) + I (Provenance) + K (Temporal Decay)

**Purpose**: Optimize retrieval and context assembly

**Deliverables**:
1. **Memory Blocks Architecture**
   ```
   [System Block]     │ Core instructions, persona
   [Project Block]    │ Current project context, conventions
   [Task Block]       │ Active task, goals, constraints
   [History Block]    │ Compressed conversation history
   [Knowledge Block]  │ Retrieved ADRs, incidents, code
   ```

2. **Retrieval Improvements**
   - Query rewriting for better matches
   - Reranking layer for relevance
   - Selective injection based on query type
   - Contextual compression for long memories

3. **Provenance Tracking**
   - Source links for all memories
   - Confidence scoring
   - Temporal decay implementation

**Exit Criteria**:
- 30% token efficiency improvement
- Provenance available for all retrieved items
- Stale memory detection operational

---

### Phase 3: Knowledge Structure (HybridRAG)

**Options**: A (HybridRAG with Knowledge Graph)

**Purpose**: Multi-hop reasoning for complex code queries

**Prerequisites**: Stable data from Phase 1-2, validated need for graph queries

**Deliverables**:
- Knowledge graph for code dependencies
- Entity extraction pipeline (async, not blocking)
- Reciprocal Rank Fusion (vector + graph)
- Neural reranker for final results

**Target Queries** (justify the investment):
```
"What services depend on auth that had incidents last month?"
"Show me all code that changed because of ADR-005"
"Which team owns the service that calls the failing endpoint?"
```

**Exit Criteria**:
- Multi-hop queries outperform pure vector by >50%
- Latency <1s for graph-augmented queries
- Entity extraction runs async (no chat blocking)

---

### Phase 4: Advanced Capabilities

**Options**: C (Hindsight), E (MaaS), J (RAT)

**Purpose**: Future-state capabilities based on validated needs

**Conditional Entry**:
- **Hindsight (C)**: Only if Phase 3 reveals need for temporal/causal reasoning
- **MaaS (E)**: Only if multi-agent architecture is adopted
- **RAT (J)**: Only if complex reasoning queries dominate usage

**Approach**: Cherry-pick techniques from Hindsight rather than wholesale adoption

---

### Roadmap Visualization

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ROADMAP TIMELINE                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Phase 0          Phase 1         Phase 2          Phase 3       Phase 4    │
│  Foundations      Mem0            Context Eng      HybridRAG     Advanced   │
│  ┌────────┐      ┌────────┐      ┌────────┐      ┌────────┐    ┌────────┐  │
│  │ Eval   │      │ Memory │      │ Blocks │      │ Graph  │    │Hindsight│  │
│  │ Schema │─────▶│ Policy │─────▶│ Rerank │─────▶│ Vector │───▶│ MaaS   │  │
│  │ Govern │      │ Cache  │      │ Decay  │      │ Fusion │    │ RAT    │  │
│  └────────┘      └────────┘      └────────┘      └────────┘    └────────┘  │
│                                                                              │
│  [Must Have]     [Quick Win]     [Optimization]  [Conditional] [Future]     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

> **Tier Constraints (ADR-004)**: Memory persistence depth and retention policies vary by monetization tier. Free tier has local-only storage; Team tier includes cloud persistence with GDPR auto-deletion; Enterprise tier supports configurable retention with legal hold. See ADR-004 for tier definitions and ADR-007 for implementation details.

---

## Implementation Tracker

| Phase | Component | Status | Notes |
|-------|-----------|--------|-------|
| **Phase 0** | Evaluation Harness | ✅ Complete | `src/memory/evaluation/` - 28 tests |
| Phase 0 | Golden Dataset | ✅ Complete | `tests/memory/golden_dataset.json` - 50 questions |
| Phase 0 | Memory Schema & Lifecycle | ✅ Complete | `src/memory/schemas/`, `src/memory/lifecycle/` - 36 tests |
| Phase 0 | Governance & Observability | ✅ Complete | `src/memory/observability/` - 27 tests |
| Phase 0 | MemoryProvider Protocol | ✅ Complete | `src/memory/protocols.py` - ADR-007 compliant |
| **Phase 1** | Session Memory MCP | ✅ Complete | `session_memory_server.py` - 45 tests |
| Phase 1 | Pixeltable MCP | ✅ Complete | `pixeltable_mcp_server.py` - 62 tests |
| Phase 1a | Hot Memory Storage | ✅ Complete | `src/memory/storage/`, `src/memory/providers/local.py` - 27 tests |
| Phase 1a | Memory MCP Tools | ✅ Complete | `src/memory/mcp/tools.py` - 21 tests |
| Phase 1a | Hot Memory Latency | ✅ Complete | <50ms p95 target met - 6 tests |
| Phase 1b | Async Extraction | ✅ Complete | `src/memory/extraction/` - 36 tests |
| Phase 1b | Extraction Precision | ✅ Complete | >85% target met (100% achieved) - 5 tests |
| Phase 1c | Retrieval & Ranking | ✅ Complete | `src/memory/retrieval/` - 31 tests |
| Phase 1c | Query Rewriting | ✅ Complete | Synonym expansion for better recall |
| Phase 1c | Scope-Aware Retrieval | ✅ Complete | user > project > global hierarchy |
| Phase 1c | Retrieval Latency | ✅ Complete | <200ms p95 target met - 6 tests |
| Phase 1d | Janitor Process | ✅ Complete | `src/memory/janitor/` - 24 tests |
| Phase 1d | Deduplication | ✅ Complete | >85% similarity threshold |
| Phase 1d | Contradiction Handling | ✅ Complete | "newer wins" with flagging |
| Phase 1d | Expiration Cleanup | ✅ Complete | TTL-based expiration |
| Phase 1d | Janitor Performance | ✅ Complete | <10 min for 10k target met - 5 tests |
| **CI/Security** | Memory Isolation | ✅ Complete | Zero cross-user leakage - 8 tests |
| CI/Security | Protocol Compliance | ✅ Complete | Three-layer testing - 23 tests |
| CI/Security | CI Workflow | ✅ Complete | `.github/workflows/memory-evaluation.yml` |
| **Phase 2** | Memory Blocks Architecture | ✅ Complete | 5-block layout with XML delimiters |
| Phase 2 | Provenance Tracking | ✅ Complete | Full provenance on all retrievals |
| Phase 2 | Temporal Decay | ✅ Complete | Integrated in retrieval ranking |
| Phase 2 | History Compression | ✅ Complete | Line-preserving truncation |
| Phase 2 | Token Efficiency | ✅ Complete | 40% efficiency (>30% target) |
| Phase 2 | Exit Criteria Tests | ✅ Complete | 6 benchmark tests passing |
| **Phase 3** | Knowledge Graph | 📝 Not Started | HybridRAG |
| Phase 3 | Entity Extraction | 📝 Not Started | Async pipeline |
| **Phase 4** | Hindsight Integration | 📝 Not Started | Conditional on Phase 3 |
| Phase 4 | MaaS Architecture | 📝 Not Started | Multi-agent support |

**Test Summary**: 490 tests passing (as of 2026-01-08)

**Legend**: ✅ Complete | 🔄 Partial | 📝 Not Started | ❌ Blocked

---

## Consequences

### Positive
- AI assistants maintain context across sessions
- Reduced repetitive context loading (estimated 60-80% reduction)
- Institutional knowledge becomes searchable
- Consistent AI suggestions aligned with past decisions
- Multi-project organizational awareness
- Foundation for advanced multi-agent workflows

### Negative
- Requires initial setup and ingestion
- Python version binding (mitigated by ADR-001)
- Storage growth with codebase size
- Embedding computation cost (mitigated by local models)
- New infrastructure to maintain (Pixeltable, MCP servers)
- Team learning curve on memory-augmented AI patterns

### Neutral
- Requires MCP-compatible client
- Team adoption needed for full benefit
- ADR/incident discipline improves value
- Commits us to MCP protocol (reasonable bet given industry adoption)
- May require revisiting if context windows grow significantly larger

---

## Risks and Mitigations (Council Additions)

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Memory Poisoning** | Medium | High | Provenance tracking, confidence scoring, human approval gates for "decision-grade" memories |
| **Staleness & Drift** | High | High | Link memories to repo commits, TTL policies, periodic revalidation jobs, git hook triggers |
| **Contradictions** | Medium | Medium | Conflict resolution policy (prefer newer? prefer docs?), show both with citations |
| **Latency Blowups** | Medium | High | Budgets per tier, caching, "fast path" vs "deep reasoning path" separation |
| **Relevance Pollution** | High | Medium | Temporal decay (Option K), ranking algorithms, "forgetting curve" implementation |
| **Schema Drift** | High | Medium | Async re-indexing on commit, version migrations, schema evolution plan |

### Organizational Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Scope Creep via Options** | High | High | Hard constraint: Pick ≤3 options for 2025, phase gates required |
| **Benchmark Gaming** | Low | Medium | Include qualitative user feedback, test against real project history |
| **Vendor Lock-in** | Medium | Medium | Define internal memory APIs and adapters, avoid proprietary-only features |
| **Operational Complexity** | Medium | Medium | Document backup/migration procedures, plan embedding model upgrades |

### Security & Privacy Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Memory Leakage** | Medium | High | Strict namespace isolation, MCP scoping, audit logs for cross-project retrievals |
| **MEXTRA Attacks** | Low | High | Output filtering, memory de-identification, input validation |
| **Secret Exposure** | Low | Critical | Secret redaction in ingestion, .gitignore-style exclusion patterns |

### Risk Assessment by Council Model

> **Gemini**: "Memory update triggers (Git hooks) are required to keep memory synchronized. Without them, the Knowledge Graph becomes a hallucination source."

> **Claude**: "Wrong context is worse than no context. Memory poisoning needs confidence scoring and human approval gates."

> **Grok**: "Ensure memory systems don't perpetuate biases in persistent context via biased knowledge graphs."

> **GPT**: "Memory systems need pruning strategies - relevance pollution is a real problem at scale."

## Security Considerations

Per recent research (MEXTRA attack, February 2025), memory systems are vulnerable to:
- Prompt injection extracting stored memories
- Cross-session data leakage

**Mitigations** (to implement):
- User/session-level isolation
- Memory de-identification
- Output filtering
- Audit logging

## Related Decisions

- **ADR-001**: Python Version Requirement (database integrity)
- **ADR-002**: Workflow Integration (automated ingestion)

## References

- [Mem0 Research: 26% Accuracy Boost](https://mem0.ai/research)
- [Hindsight Agentic Memory - 91.4% LongMemEval](https://venturebeat.com/data/with-91-accuracy-open-source-hindsight-agentic-memory-provides-20-20-vision)
- [HybridRAG: Integrating Knowledge Graphs](https://arxiv.org/html/2408.04948v1)
- [MCP One Year Anniversary - November 2025 Spec](https://blog.modelcontextprotocol.io/posts/2025-11-25-first-mcp-anniversary/)
- [Context Engineering for Agents](https://rlancemartin.github.io/2025/06/23/context_engineering/)
- [LangMem SDK Launch](https://blog.langchain.com/langmem-sdk-launch/)
- [Beyond RAG: Context Engineering](https://towardsdatascience.com/beyond-rag/)
- [ACE: Agentic Context Engineering](https://arxiv.org/abs/2510.04618)
- [Memory as a Service (MaaS)](https://arxiv.org/html/2506.22815v1)

## Open Questions

The following questions have been investigated and resolved:

1. **Single-tenant vs Multi-tenant**: ✅ **Resolved** - Multi-tenancy is supported via the `TenantProvider` protocol (ADR-005) and `CloudTenantProvider` implementation (ADR-007). See ADR-007 Section 1a for tenant isolation enforcement points.

2. **Memory Approval Workflows**: ✅ **Resolved** - The `AuditLogger` protocol (ADR-007) provides provenance tracking. GDPR compliance workflows in `GDPRService` (luminescent-cloud) implement approval gates for data deletion.

3. **Retention Policies**: ✅ **Resolved** - ADR-007 Section 4 defines tier-specific retention:
   - **Free (OSS)**: User's responsibility (no auto-deletion)
   - **Team (Cloud)**: Auto-delete on workspace exit (GDPR Article 17)
   - **Enterprise**: Configurable (legal hold support)

4. **Embedding Model Upgrades**: 🔄 **Partially Resolved** - Pixeltable computed columns support re-indexing. Full migration strategy deferred to Phase 3 (HybridRAG).

5. **Conflict Resolution**: 🔄 **Partially Resolved** - Phase 1d Janitor Process implements "newer wins" with flagging for review. Complex contradiction handling deferred to Phase 2 (Context Engineering).

## Council Review Summary

### Design Review (2025-12-22)

**Council Configuration**: High confidence (all 4 models)
**Models**: Gemini-3-Pro, Claude Opus 4.5, Grok-4, GPT-5.2-Pro

#### Unanimous Recommendations (All 4 Models)
1. Add Phase 0 for foundations, evaluation, and governance
2. Reorder roadmap: Mem0 before HybridRAG
3. Add quantified success metrics
4. Add provenance/governance as core requirement
5. Include context caching for cost optimization

#### Key Insights by Model
- **Gemini**: "Optimization before Foundation" is the core flaw
- **Claude**: "Wrong context is worse than no context"
- **Grok**: Emphasized bias prevention in knowledge graphs
- **GPT**: Highlighted need for "Phase 0" evaluation harness

---

### Implementation Verification (2026-01-07)

**Council Configuration**: High confidence (all 4 models)
**Models**: GPT-5.2-Pro, Gemini-3-Pro, Claude Opus 4.5, Grok-4
**Transcripts**: `.council/logs/2026-01-07T21-25-55-87316c79/`, `2026-01-07T21-41-43-284ed67c/`, `2026-01-07T21-49-29-4db02c46/`

#### Round 1 (Commit 0c8c41a) - REJECTED
| Issue | Severity | Fix Applied |
|-------|----------|-------------|
| `EvaluationHarness` defaulted `success=True` when no `evaluate_fn` | Critical | Changed to `success=False` |
| Precision/recall/F1 aliased to accuracy (not calculated) | Critical | Now uses `metrics.py` functions |
| O(N²) janitor complexity | High | Documented as known trade-off (meets <10min target) |
| Silent exception swallowing | High | Added error collection and reporting |

#### Round 2 (Commit e448f22) - REJECTED
| Issue | Severity | Fix Applied |
|-------|----------|-------------|
| Janitor fallback modified metadata but didn't persist | Critical | Removed broken fallback, use invalidate/delete only |
| FP/FN indistinguishable (both set to `failed`) | Critical | Now tracks by `retrieved_memories` presence |
| `invalidated` count incremented without action | Critical | Only increment on successful operation |

#### Round 3 (Commit 720a61b) - UNCLEAR (Confidence 0.54)
| Remaining Concern | Status | Rationale |
|-------------------|--------|-----------|
| O(N²) complexity | Acceptable | Meets ADR-003 target (<10min for 10k memories, actual: <3s) |
| `resolve_duplicates` unused | By Design | Used internally by `find_duplicates` workflow |
| Keyword-based contradiction detection | Phase 1 Scope | Semantic analysis deferred to Phase 2 |
| Hard-coded `limit=10000` | Acceptable | Documented limitation for Phase 1 |

#### Round 4 (Commit 0efa8a2) - UNCLEAR (Confidence 0.61, No Blocking Issues)
**Focus**: ADR-005 Dual-Repo Compliance Fix

| Issue | Severity | Fix Applied |
|-------|----------|-------------|
| `MemoryProvider` not exported from `extensions` module | Critical | Added to `__init__.py` imports and `__all__` |
| `ResponseFilter` not exported | Critical | Added to `__init__.py` imports and `__all__` |
| `MEMORY_PROVIDER_VERSION` not exported | Critical | Added to `__init__.py` imports and `__all__` |
| Misleading docstring import path | Medium | Fixed to use `src.extensions` |
| Brittle `_is_runtime_protocol` check | Medium | Changed to `isinstance()` test |

**Outcome**: No blocking issues. Rationale "approved" at 0.9 confidence.
**Transcript**: `.council/logs/2026-01-07T22-43-42-b3f93afd/`

#### Final Scores (Round 4)
- Accuracy: 10.0/10
- Completeness: 6.3/10
- Clarity: 7.0/10
- Blocking Issues: None

#### Split Decision (Rounds 1-3)
- GPT-5.2-Pro: **REJECTED** (strictest interpretation)
- Gemini-3-Pro: **REJECTED** (completeness concerns)
- Claude Opus 4.5: **NEEDS REVIEW** (acceptable for Phase 1)
- Grok-4: **APPROVED** (most lenient)

## Related Decisions

- **ADR-001**: Python Version Requirement (database integrity)
- **ADR-002**: Workflow Integration (automated ingestion)
- **ADR-004**: Monetization Strategy (tier-based memory constraints)
- **ADR-005**: Repository Organization Strategy (OSS vs Paid separation, Extension Registry)
- **ADR-006**: Chatbot Platform Integrations (adapters implementing memory I/O)
- **ADR-007**: Cross-ADR Integration Guide (Phase Alignment Matrix, protocol consolidation)

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-22 | Initial draft |
| 2.0 | 2025-12-22 | Added industry research and 6 improvement options |
| 3.0 | 2025-12-22 | **Council Review**: Revised roadmap (Phase 0 + reordering), added decision drivers, non-goals, success metrics table, interface contract, 5 additional options (G-K), comprehensive risk matrix, council feedback summary |
| 4.0 | 2025-12-22 | **Council Review #2**: Rejected Mem0 integration in favor of Pixeltable-native memory. Added "Build vs Integrate" decision section with code examples. Updated Phase 1 to Pixeltable Native approach. Added reference to ADR-004 (Monetization). |
| 4.1 | 2025-12-23 | **Council Validation**: Extended Phase 1 to 8 weeks. Added "Janitor" (Hot/Warm/Cold) architecture for async extraction. Added Golden Dataset requirement. Added validation metrics and decision reversal triggers. |
| 4.2 | 2025-12-28 | **Cross-ADR Synchronization**: Added ADR-006 and ADR-007 to Related Decisions. Updated Non-Goals to reflect multi-tenancy via Extension Registry. Added Interface Contract admonition linking to consolidated protocols. Marked Open Questions as resolved with references. Added Implementation Tracker section. Added tier constraints note to Roadmap. Council review (Grok-4, GPT-4o). |
| 4.3 | 2026-01-07 | **Implementation Verification**: Council reviewed Phase 0-1d implementation across 3 rounds. Fixed critical bugs in EvaluationHarness (metrics calculation) and Janitor (persistence, error handling). Added dry-run mode and soft-delete to janitor. Updated test count to 330. Added Implementation Verification section with Council transcripts. Phase 2+ remains NOT STARTED. |
| 4.4 | 2026-01-07 | **ADR-005 Compliance Fix**: Exported `MemoryProvider`, `ResponseFilter`, `MEMORY_PROVIDER_VERSION` from `src/extensions/__init__.py`. Council Round 4: No blocking issues, 10.0/10 accuracy. Fixed #117, unblocked #114. Test count: 1008 total (336 memory-specific). |
| 4.5 | 2026-01-08 | **Phase 2 Complete**: Implemented Memory Blocks Architecture with 5-block layout (System, Project, Task, History, Knowledge). Added provenance tracking on all retrievals, line-preserving truncation, XML-safe delimiters. Met all exit criteria: 40% token efficiency (>30% target), provenance on all items, stale detection operational. Test count: 436 memory tests. Council verified across 8 rounds. |
| 4.6 | 2026-01-08 | **Security Hardening (Council Rounds 13-19)**: Comprehensive DoS prevention in ProvenanceService. Added: bounded LRU storage, string identifier length limits, metadata bounds validation, recursive nested structure validation with early termination, strict JSON type safety, cycle detection, UTF-8 byte size validation, TOCTOU prevention via deep copy, score range validation (0.0-1.0). Test count: 490 memory tests (64 provenance-specific security tests). |
