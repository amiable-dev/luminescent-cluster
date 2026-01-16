# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
  - 150 MaaS tests (TDD approach)
  - Exit criteria benchmarks: sync <500ms p95, handoff <2s p95, registry lookup <50ms

### Changed
- ADR-003 updated to v6.7 with Phase 4.2 implementation tracker

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

[0.2.0]: https://github.com/amiable-dev/luminescent-cluster/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/amiable-dev/luminescent-cluster/releases/tag/v0.1.0
