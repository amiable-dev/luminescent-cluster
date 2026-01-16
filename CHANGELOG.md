# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Workflow Integration (ADR-002)**
  - Agent Skills for session management (open standard, portable across LLMs)
    - `session-init`: Load context, check KB freshness, query organizational knowledge
    - `session-save`: Persist session state, update task context, prepare for commit
  - Git hooks for automatic KB synchronization
    - `post-commit`: Auto-ingest committed documentation files
    - `post-merge`: Sync KB after merge/pull operations
    - `post-rewrite`: Clear ingestion state on rebase/amend
  - Support scripts
    - `scripts/install_hooks.sh`: Install git hooks with backup of existing hooks
    - `scripts/init_memory.py`: Bootstrap KB for fresh clones
  - Core workflow infrastructure (`src/workflows/`)
    - `WorkflowConfig`: Include/exclude patterns, max file size, secrets detection
    - `ingest_file()`: Single-file ingestion with content hash idempotency
    - `should_ingest_file()`: Pattern-based filtering for allowlist/denylist
    - `is_secret_file()`: Secrets detection to prevent sensitive file ingestion
  - Configuration via `.agent/config.yaml`
  - 115 new workflow tests (TDD approach)

### Security
- **Secrets Protection (ADR-002)**
  - Pattern-based filtering: `.env`, `*.key`, `*.pem`, `*secret*`, `*password*`, `*token*`
  - Content never ingested for files matching secrets patterns
  - Audit logging for skipped files

- **Ingestion Security Hardening (10 LLM Council reviews)**
  - Path traversal prevention with canonical path resolution (fail-closed)
  - Commit SHA validation (7-40 hex character regex)
  - Null byte injection prevention
  - Hyphen prefix rejection (git argument injection prevention)
  - Blob type verification (prevents directory listing ingestion)
  - Git object database reading (provenance integrity, no working tree access)
  - Size check before content load (DoS prevention)
  - Binary file handling with explicit UTF-8 decode (errors='replace')
  - Config validation with hard limits (max 10MB file size)
  - Safe pattern matching without regex (fnmatch-based, no ReDoS)

## [0.3.0] - 2026-01-16

### Added
- **Memory as a Service - MaaS (ADR-003 Phase 4.2)**
  - Multi-agent collaboration infrastructure for shared memory
  - `AgentType` enum: CLAUDE_CODE, GPT_AGENT, CUSTOM_PIPELINE, HUMAN
  - `AgentCapability` enum: MEMORY_READ, MEMORY_WRITE, MEMORY_DELETE, KB_SEARCH, HANDOFF_INITIATE, HANDOFF_RECEIVE
  - `SharedScope` enum: AGENT_PRIVATE, USER, PROJECT, TEAM, GLOBAL (hierarchical visibility)
  - `AgentIdentity` dataclass with capability checking and serialization
  - `AgentRegistry` singleton: register, deactivate, session management (thread-safe)
  - `PoolRegistry` singleton: shared memory pools with membership and permissions
  - `HandoffManager` singleton: task handoffs between specialized agents
  - `MaaSMemoryProvider`: provider wrapper with agent context
  - `CodeKBService`, `DecisionService`, `IncidentService`: knowledge base services
  - MCP tools: 15 async functions for agent/pool/handoff management
  - Security: `MEXTRAValidator` (injection detection), `MemoryPoisoningDefense` (output filtering), `AgentRateLimiter`, `MaaSAuditLogger`
  - `MaaSProvider` protocol added to extensions
  - 149 MaaS tests (TDD approach, including 12 security tests)
  - Exit criteria benchmarks: sync <500ms p95, handoff <2s p95, registry lookup <50ms

### Changed
- ADR-003 updated to v6.7 with Phase 4.2 implementation tracker

### Security
- **MaaS Security Hardening (LLM Council verified)**
  - ID entropy increased from 48-bit to 128-bit (full UUID hex) for agents, sessions, pools, handoffs
  - DoS prevention with configurable capacity limits:
    - `RegistryCapacityError`: max agents (10,000), max sessions (50,000)
    - `PoolCapacityError`: max pools (10,000), max memberships per pool (1,000), max shared memories (100,000)
    - `HandoffCapacityError`: max handoffs (50,000), max pending per target (100)
  - DoS recovery methods: `unregister_agent()`, `cleanup_terminal_handoffs()`
  - Audit logging integration with TOCTOU-safe access pattern
  - Defensive copies on all inputs (capabilities, metadata, context, result)
  - Defensive copies on all outputs (agents, pools, handoffs, sessions)
  - Integrity check: `join_pool` verifies agent exists in registry
  - 12 new security tests for capacity limits, defensive copies, audit integration

## [0.2.0] - 2026-01-16

### Added
- **Entity Extraction Async Pipeline (ADR-003 Phase 3)**
  - `EntityType` enum: SERVICE, DEPENDENCY, API, PATTERN, FRAMEWORK, CONFIG
  - `Entity` dataclass with confidence scoring and metadata
  - `EntityExtractor` protocol (runtime_checkable)
  - `MockEntityExtractor`: pattern-based extraction for testing
  - `HaikuEntityExtractor`: LLM-based extraction with Claude Haiku
  - `EntityExtractionPipeline` with `process()` and `process_async()` methods
  - Entities stored in `Memory.metadata["entities"]` for knowledge graph support
  - 81 entity extraction tests (TDD approach)

### Fixed
- `LocalMemoryProvider.update()` now supports metadata merge updates
- Security: user_id authorization check in EntityExtractionPipeline prevents cross-user modification

### Changed
- ADR-003 updated to v6.2

## [0.1.0] - 2026-01-09

### Added
- **Two-Stage Retrieval Architecture (ADR-003 Phase 3)**
  - BM25 sparse keyword search with tokenization and IDF
  - Dense vector search with sentence-transformers
  - RRF (Reciprocal Rank Fusion) algorithm
  - Cross-encoder reranking with ms-marco-MiniLM-L-6-v2
  - HybridRetriever orchestrator with parallel Stage 1
  - Provider integration with LocalMemoryProvider

- **Grounded Memory Ingestion (ADR-003 Phase 2)**
  - 3-tier provenance model to prevent hallucination write-back
  - Citation detection (ADR/commit/URL regex)
  - Hedge detection (speculative language blocking)
  - Deduplication checker (Jaccard similarity >0.92)
  - Review queue for Tier 2 pending memories

- **Memory Blocks Architecture (ADR-003 Phase 2)**
  - 5-block layout: System, Project, Task, History, Knowledge
  - Provenance tracking on all retrievals
  - Line-preserving truncation
  - 40% token efficiency

- **HNSW Recall Health Monitoring (ADR-003 Phase 0)**
  - RecallHealthMonitor with Recall@k computation
  - Brute-force exact search baseline
  - Drift detection with atomic writes
  - Embedding version tracking
  - Auto-reindex trigger on threshold breach

- **Core Memory Infrastructure (ADR-003 Phase 0-1)**
  - Memory schema with Pydantic validation
  - LocalMemoryProvider for in-memory storage
  - Async extraction pipeline with confidence scoring
  - Janitor process for deduplication and expiration
  - Session Memory MCP server
  - Pixeltable MCP server for organizational knowledge

### Security
- Memory isolation: zero cross-user leakage
- Grounded ingestion security hardening (8 vulnerability fixes)
- HNSW security: symlink protection, path containment, PII exclusion

[0.3.0]: https://github.com/amiable-dev/luminescent-cluster/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/amiable-dev/luminescent-cluster/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/amiable-dev/luminescent-cluster/releases/tag/v0.1.0
