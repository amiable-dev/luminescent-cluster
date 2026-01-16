# Memory System Requirements

Requirements for memory storage, retrieval, lifecycle, and evaluation.

**Primary ADR**: ADR-003

---

## Phase 0: Foundations

### REQ-MEM-001: Evaluation Harness
**Source**: ADR-003 Phase 0
**Status**: Active
**Priority**: Critical

The memory system MUST provide an evaluation harness with:
- Fixed task set for automated scoring
- Retrieval quality metrics (precision@k, recall@k)
- Latency/cost instrumentation
- Contradiction/hallucination tests

**Test Mapping**:
- `tests/memory/test_evaluation.py::test_evaluation_harness_metrics`
- `tests/memory/test_evaluation.py::test_precision_at_k`
- `tests/memory/test_evaluation.py::test_recall_at_k`

---

### REQ-MEM-002: Golden Dataset
**Source**: ADR-003 Phase 0
**Status**: Active
**Priority**: High

The memory system MUST maintain a golden dataset of 50+ static questions for regression testing against real project queries.

**Test Mapping**:
- `tests/memory/test_evaluation.py::test_golden_dataset_exists`
- `tests/memory/test_evaluation.py::test_golden_dataset_coverage`

---

### REQ-MEM-003: HNSW Recall Monitoring
**Source**: ADR-003 Phase 0
**Status**: Active
**Priority**: Critical

The memory system MUST monitor HNSW recall@k against brute-force exact search with:
- Absolute threshold: Recall@10 >= 0.90
- Relative drift: <= 5% drop from baseline
- Filtered search evaluation (tenant/tag filters)

**Test Mapping**:
- `tests/memory/test_recall_health.py::test_recall_threshold`
- `tests/memory/test_recall_health.py::test_drift_detection`
- `tests/memory/test_recall_health.py::test_filtered_recall`

---

### REQ-MEM-004: Embedding Version Tracking
**Source**: ADR-003 Phase 0
**Status**: Active
**Priority**: High

All embeddings MUST be version-tagged with the model identifier. On model change, embeddings MUST be flagged for re-embedding.

**Test Mapping**:
- `tests/memory/test_embedding_version.py::test_version_tag`
- `tests/memory/test_embedding_version.py::test_reembedding_flag`

---

### REQ-MEM-005: Reindex Trigger
**Source**: ADR-003 Phase 0
**Status**: Active
**Priority**: High

The system MUST automatically trigger reindexing when recall drops below the configured threshold.

**Test Mapping**:
- `tests/memory/test_reindex_trigger.py::test_auto_reindex`

---

## Phase 1: Conversational Memory

### REQ-MEM-010: Hot Memory Latency
**Source**: ADR-003 Phase 1
**Status**: Active
**Priority**: Critical

Hot memory (raw chat history retrieval) MUST have latency <50ms p95.

**Test Mapping**:
- `tests/memory/test_performance.py::test_hot_memory_latency`

---

### REQ-MEM-011: Extraction Precision
**Source**: ADR-003 Phase 1
**Status**: Active
**Priority**: High

Memory extraction MUST achieve >85% precision on the golden dataset.

**Test Mapping**:
- `tests/memory/test_extraction.py::test_extraction_precision`

---

### REQ-MEM-012: Query Latency
**Source**: ADR-003 Phase 1
**Status**: Active
**Priority**: Critical

Memory query latency MUST be <200ms p95.

**Test Mapping**:
- `tests/memory/test_performance.py::test_query_latency`

---

### REQ-MEM-013: User Isolation
**Source**: ADR-003 Phase 1
**Status**: Active
**Priority**: Critical

Memory retrieval MUST enforce user isolation with zero cross-user memory leakage.

**Test Mapping**:
- `tests/memory/test_isolation.py::test_user_isolation`
- `tests/memory/test_isolation.py::test_no_cross_user_leakage`

---

### REQ-MEM-014: Memory Consolidation
**Source**: ADR-003 Phase 1d
**Status**: Active
**Priority**: High

The janitor process MUST deduplicate memories with >85% similarity threshold.

**Test Mapping**:
- `tests/memory/test_janitor.py::test_deduplication`
- `tests/memory/test_janitor.py::test_similarity_threshold`

---

### REQ-MEM-015: Janitor Performance
**Source**: ADR-003 Phase 1d
**Status**: Active
**Priority**: High

The janitor process MUST complete in <10 minutes for 10k memories.

**Test Mapping**:
- `tests/memory/test_janitor.py::test_performance`

---

## Phase 2: Context Engineering

### REQ-MEM-020: Memory Blocks
**Source**: ADR-003 Phase 2
**Status**: Active
**Priority**: High

Context assembly MUST use the 5-block layout: System, Project, Task, History, Knowledge.

**Test Mapping**:
- `tests/memory/test_blocks.py::test_block_layout`
- `tests/memory/test_blocks.py::test_block_ordering`

---

### REQ-MEM-021: Provenance Tracking
**Source**: ADR-003 Phase 2
**Status**: Active
**Priority**: High

All retrieved memories MUST include provenance (source, timestamp, confidence).

**Test Mapping**:
- `tests/memory/test_provenance.py::test_provenance_attached`
- `tests/memory/test_provenance.py::test_provenance_fields`

---

### REQ-MEM-022: Token Efficiency
**Source**: ADR-003 Phase 2
**Status**: Active
**Priority**: Medium

Memory retrieval MUST achieve >30% token efficiency improvement over baseline.

**Test Mapping**:
- `tests/memory/test_performance.py::test_token_efficiency`

---

### REQ-MEM-023: Grounded Ingestion
**Source**: ADR-003 Phase 2
**Status**: Active
**Priority**: High

Memory ingestion MUST use 3-tier provenance model:
- Tier 1 (auto-approve): Content with citations
- Tier 2 (flag for review): AI-synthesized claims
- Tier 3 (block): Speculative content

**Test Mapping**:
- `tests/memory/test_ingestion.py::test_tier1_approval`
- `tests/memory/test_ingestion.py::test_tier2_flagging`
- `tests/memory/test_ingestion.py::test_tier3_blocking`

---

## Phase 3: HybridRAG

### REQ-MEM-030: Two-Stage Retrieval
**Source**: ADR-003 Phase 3
**Status**: Active
**Priority**: High

Retrieval MUST use two-stage architecture:
- Stage 1: Parallel candidate generation (BM25 + Vector + Graph)
- Stage 2: RRF fusion + cross-encoder reranking

**Test Mapping**:
- `tests/memory/test_hybrid.py::test_two_stage_retrieval`
- `tests/memory/test_hybrid.py::test_parallel_generation`

---

### REQ-MEM-031: RRF Fusion
**Source**: ADR-003 Phase 3
**Status**: Active
**Priority**: High

Retrieval MUST use Reciprocal Rank Fusion with formula `Σ 1/(k + rank_i)`.

**Test Mapping**:
- `tests/memory/test_fusion.py::test_rrf_formula`
- `tests/memory/test_fusion.py::test_weighted_fusion`

---

### REQ-MEM-032: HybridRAG Latency
**Source**: ADR-003 Phase 3
**Status**: Active
**Priority**: High

Full HybridRAG retrieval MUST complete in <1s.

**Test Mapping**:
- `tests/memory/test_performance.py::test_hybridrag_latency`

---

## Negative Obligations

### NEG-MEM-001: No Hallucination Write-back
**Source**: ADR-003 Phase 2
**Status**: Active
**Priority**: Critical

The memory system MUST NOT write AI-generated hallucinations to long-term storage. Speculative content MUST be blocked.

**Test Mapping**:
- `tests/memory/test_ingestion.py::test_no_hallucination_writeback`
- `tests/memory/test_ingestion.py::test_speculation_blocked`

---

### NEG-MEM-002: No Cross-User Access
**Source**: ADR-003 Phase 1
**Status**: Active
**Priority**: Critical

The memory system MUST NOT allow access to another user's memories, even with known memory IDs.

**Test Mapping**:
- `tests/memory/test_isolation.py::test_cross_user_blocked`
