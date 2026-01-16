# Memory System Operations Runbook

**Version**: 1.0
**Last Updated**: 2026-01-16
**ADR Reference**: ADR-003 Memory Architecture

## Overview

This runbook covers operational procedures for the memory system, including monitoring, troubleshooting, and scaling guidelines.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    HybridRetriever                          │
│  ┌──────────────┬──────────────┬──────────────────────────┐ │
│  │   BM25       │   Vector     │   GraphSearch            │ │
│  │   (Stage 1)  │   (Stage 1)  │   (Stage 1)              │ │
│  └──────┬───────┴──────┬───────┴──────────┬───────────────┘ │
│         └──────────────┼──────────────────┘                 │
│                        ▼                                    │
│                   RRF Fusion                                │
│                        │                                    │
│                        ▼                                    │
│              Cross-Encoder Reranking                        │
│                   (Stage 2)                                 │
└─────────────────────────────────────────────────────────────┘
```

## Monitoring

### Key Metrics

| Metric | Location | Threshold | Action |
|--------|----------|-----------|--------|
| Recall@10 | `ScaleMilestoneTracker` | < 0.90 | Reindex HNSW |
| Query Latency p95 | `GraphMetricsCollector` | > 1000ms | Scale infrastructure |
| Cache Hit Rate | `RetrievalCache.get_metrics()` | < 50% | Increase TTL or size |
| Graph Node Count | `GraphSizeSnapshot` | > 100k | Monitor query latency |

### Scale Milestones

The system tracks scale milestones at 10k, 50k, and 100k items:

```python
from src.memory.observability import ScaleMilestoneTracker, STANDARD_MILESTONES

tracker = ScaleMilestoneTracker(
    milestones=STANDARD_MILESTONES,
    on_milestone_reached=run_health_check,
)

# Record current item count
tracker.record_item_count("user-123", current_count)

# Get stats
stats = tracker.get_stats("user-123")
print(f"Current milestone: {stats['current_milestone']}")
print(f"Next milestone: {stats['next_milestone']}")
```

**Standard Thresholds**:
| Milestone | Items | Recall Threshold | Latency Threshold |
|-----------|-------|------------------|-------------------|
| Small | 10,000 | 0.95 | 500ms |
| Medium | 50,000 | 0.92 | 750ms |
| Large | 100,000 | 0.90 | 1000ms |

### Graph Query Monitoring

Monitor graph traversal performance:

```python
from src.memory.observability import GraphMetricsCollector

collector = GraphMetricsCollector()

# Measure queries
with collector.measure_query("user-123", "auth-service") as ctx:
    # Direct matches
    ctx.add_hop("direct", direct_latency_ms, direct_count)
    # Neighbor traversal
    ctx.add_hop("neighbor", neighbor_latency_ms, neighbor_count)
    ctx.set_results_count(len(results))

# Get hop-level latency breakdown
hop_stats = collector.get_latency_by_hop_type("user-123")
print(f"Direct match avg: {hop_stats['direct']['avg_latency_ms']:.2f}ms")
print(f"Neighbor avg: {hop_stats['neighbor']['avg_latency_ms']:.2f}ms")
```

## Troubleshooting

### Issue: High Query Latency

**Symptoms**:
- p95 latency > 1000ms
- User-reported slow responses

**Diagnosis**:
1. Check which hop type is slow:
   ```python
   stats = collector.get_stats("user-id")
   for hop_type, metrics in stats["hop_stats"].items():
       print(f"{hop_type}: {metrics['avg_latency_ms']:.2f}ms")
   ```

2. Check graph size:
   ```python
   snapshots = collector.get_size_history("user-id")
   latest = snapshots[-1]
   print(f"Nodes: {latest.node_count}, Edges: {latest.edge_count}")
   ```

**Resolution**:
- If graph is large (>50k nodes): Consider graph pruning
- If neighbor hop is slow: Reduce traversal depth or cache common paths
- If direct match is slow: Optimize node lookup index

### Issue: Low Recall

**Symptoms**:
- MilestoneCheckResult.passed_recall is False
- Users report missing relevant results

**Diagnosis**:
1. Check recall at current scale:
   ```python
   history = tracker.get_check_history("user-id")
   for check in history:
       if not check.passed_recall:
           print(f"Recall {check.recall:.2%} < threshold {check.milestone.recall_threshold:.2%}")
   ```

2. Check if milestone was recently crossed:
   ```python
   stats = tracker.get_stats("user-id")
   print(f"Crossed milestones: {stats['crossed_milestones']}")
   ```

**Resolution**:
- Trigger HNSW reindex at current scale
- Consider increasing ef_construction parameter
- Review RRF weights if one source dominates

### Issue: Low Cache Hit Rate

**Symptoms**:
- hit_rate < 0.50
- High latency due to repeated computations

**Diagnosis**:
```python
metrics = provider.get_cache_metrics()
print(f"Hit rate: {metrics['hit_rate']:.2%}")
print(f"Size: {metrics['size']}")
```

**Resolution**:
- Increase cache TTL: `LocalMemoryProvider(use_cache=True, cache_ttl_seconds=300)`
- Increase cache size: `LocalMemoryProvider(use_cache=True, cache_max_size=2000)`
- Verify cache isn't being invalidated by frequent writes

### Issue: RRF Results Biased to One Source

**Symptoms**:
- Results dominated by BM25 or vector search
- Graph results rarely appear

**Diagnosis**:
```python
from src.memory.retrieval import RRFFusion

fusion = RRFFusion(k=60)
results = fusion.fuse_with_details(bm25=bm25_results, vector=vector_results, graph=graph_results)

for r in results[:10]:
    print(f"{r.item}: {r.source_ranks}")
```

**Resolution**:
Configure per-source weights:
```python
fusion = RRFFusion(k=60, weights={
    "bm25": 1.0,
    "vector": 1.2,  # Boost vector
    "graph": 1.5,   # Boost graph
})
```

## Scaling Guidelines

### When to Scale

| Indicator | Current State | Action |
|-----------|---------------|--------|
| p95 latency > 1s | Sustained | Add compute |
| Memory > 80% | Growing | Add memory |
| 100k milestone crossed | Alert | Review architecture |
| Cache evictions > 10%/min | High traffic | Increase cache |

### Horizontal Scaling

The memory system supports horizontal scaling via:

1. **User Sharding**: Route users to specific instances
2. **Index Sharding**: Distribute HNSW indexes across nodes
3. **Cache Distribution**: Use Redis for shared caching

### Vertical Scaling

For single-instance improvements:

1. **HNSW Parameters**:
   - `ef_construction`: Higher = better recall, slower indexing
   - `M`: Higher = better recall, more memory

2. **Cache Tuning**:
   - Increase `cache_max_size` for larger working sets
   - Adjust `cache_ttl_seconds` based on data freshness needs

## Health Checks

### Pre-deployment Checklist

- [ ] All tests pass: `pytest tests/memory/ -v`
- [ ] Recall meets threshold: Check MilestoneCheckResult
- [ ] Latency within SLO: Check GraphMetricsCollector.get_stats()
- [ ] Cache metrics healthy: Check RetrievalCache.get_metrics()

### Periodic Health Check

Run health checks when milestones are crossed:

```python
def run_health_check(user_id: str, milestone: ScaleMilestone):
    """Health check triggered at scale milestones."""
    # 1. Measure recall with test queries
    recall = measure_recall(user_id, test_queries)

    # 2. Measure latency
    latency_ms = measure_latency(user_id, test_queries)

    # 3. Record result
    result = MilestoneCheckResult(
        milestone=milestone,
        current_count=current_count,
        recall=recall,
        latency_ms=latency_ms,
        passed_recall=recall >= milestone.recall_threshold,
        passed_latency=latency_ms <= milestone.latency_threshold_ms,
        needs_reindex=recall < milestone.recall_threshold,
    )

    tracker.record_check_result(user_id, result)

    # 4. Alert if failed
    if not result.passed:
        alert_ops_team(user_id, result)
```

## Appendix

### API Reference

**Scale Milestones**:
- `ScaleMilestoneTracker`: Track item counts and trigger health checks
- `ScaleMilestone`: Define custom milestones
- `MilestoneCheckResult`: Record health check results

**Graph Metrics**:
- `GraphMetricsCollector`: Collect and analyze query metrics
- `GraphQueryMetrics`: Single query measurement
- `GraphSizeSnapshot`: Point-in-time graph size

**Cache**:
- `RetrievalCache`: LRU cache with TTL
- `LocalMemoryProvider(use_cache=True)`: Enable provider caching

**Fusion**:
- `RRFFusion(weights={...})`: Weighted rank fusion

### Related Documents

- [ADR-003: Memory Architecture](../adrs/ADR-003-project-intent-persistent-context.md)
- [ADR-007: Cross-ADR Integration](../adrs/ADR-007-cross-adr-integration-guide.md)
- [DEBUG_LOGGING.md](../DEBUG_LOGGING.md)
