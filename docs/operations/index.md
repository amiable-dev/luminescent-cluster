# Operations

Operational guides for running Luminescent Cluster in production.

---

## Runbooks

<div class="grid cards" markdown>

-   :material-memory:{ .lg .middle } **Memory Runbook**

    ---

    Monitoring, troubleshooting, and maintenance for the memory system.

    [:octicons-arrow-right-24: Memory Runbook](memory-runbook.md)

</div>

---

## Quick Reference

### Health Checks

```bash
# Check knowledge base stats
python -c "from pixeltable_mcp_server import *; print(get_knowledge_base_stats())"

# Check Python version alignment
cat ~/.pixeltable/.python_version
python --version
```

### Common Issues

| Symptom | Likely Cause | Resolution |
|---------|--------------|------------|
| Exit code 78 | Python version mismatch | Switch Python version or migrate |
| Exit code 65 | Legacy database | Add version marker |
| Exit code 139 | Segfault from bad UDFs | Restore from backup |
| Slow retrieval | HNSW recall degradation | Reindex or tune ef_search |

### Backup Commands

```bash
# Create backup
cp -r ~/.pixeltable ~/.pixeltable.backup.$(date +%Y%m%d)

# Create snapshot (via MCP)
# > "Create a snapshot called 'pre-upgrade'"
```

---

## Monitoring

### Key Metrics

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Retrieval latency (p95) | <500ms | >1s |
| HNSW Recall@10 | >0.90 | <0.85 |
| Memory store latency | <50ms | >100ms |
| Janitor runtime | <10min | >30min |

### Scale Milestones

| Items | Action |
|-------|--------|
| 10k | Benchmark and log |
| 50k | Alert, consider ef_search tuning |
| 100k | Mandatory review, consider index rebuild |

---

## Related Documentation

- [ADR-001](../adrs/ADR-001-python-version-requirement-for-mcp-servers.md) - Python version safety
- [ADR-003](../adrs/ADR-003-project-intent-persistent-context.md) - Memory architecture
- [Known Issues](../KNOWN_ISSUES.md)
