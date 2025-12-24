# Known Issue: Ingestion MCP Response Delay

## Symptom

When running `ingest_codebase` via Claude Code, the prompt does not regain control even though ingestion completes successfully.

## Evidence

**From logs** (`~/.mcp-servers/logs/pixeltable-memory.log`):
```
16:00:07.026 [DEBUG] ingest_codebase called
16:00:26,084 [INFO] Ingested 530 files in 19.1s  
16:00:26,086 [DEBUG] Response sent  ← Server completes and sends response!
```

**User experience**: Must wait ~48 seconds total before hitting ESC.

**Result**: Data successfully ingested (verified via `check-status.sh`).

## Root Cause

29-second delay AFTER our server sends response but BEFORE Claude Code processes it.

Our code is correct - this is a **Claude Code/MCP framework issue**.

## Workaround

After starting ingestion, wait 25-30 seconds, then press **ESC**. The data will be fully ingested.

Verify with:
```bash
./scripts/check-status.sh
```

## Details

- ✅ Ingestion completes in ~19 seconds
- ✅ MCP server sends response immediately
- ✅ No errors in our code
- ❌ Claude Code doesn't process response for 29+ more seconds

Other tools work because they complete in < 1 second (delay not noticeable).

## References

- Commit fixing event loop blocking: `0fba74b`
- Debug logs: `~/.mcp-servers/logs/pixeltable-memory.log`

---

# Known Issue: Ingestion Creates Duplicate Entries

> **✅ RESOLVED** - Fixed in commit implementing [GitHub Issue #2](https://github.com/amiable-dev/context-aware-ai-system/issues/2). Upsert logic now prevents duplicates using `(service, path)` as composite unique key.

## Symptom

Running `ingest_codebase` or `ingest_architectural_decision` multiple times creates duplicate entries in the knowledge base rather than updating existing ones.

## Evidence

After multiple ingestion runs, `get_architectural_decisions` returns the same ADR multiple times:

```
ADR-011-local-development.md  (type: decision, created: 08:51:06)
ADR-011-local-development.md  (type: documentation, created: 09:05:50)
ADR-011-local-development.md  (type: documentation, created: 08:47:19)
```

Same file appears 3+ times with different timestamps and types.

## Root Causes

### 1. No Upsert Logic
The server INSERTs new rows each time rather than UPSERTing based on `(service, path)` key. Each ingestion creates new entries.

### 2. Code + ADR Overlap
- `ingest_codebase` picks up ADR `.md` files as `documentation` type
- `ingest_architectural_decision` adds them as `decision` type
- Same file appears twice with different types

### 3. Service Name Inconsistency
Different ingestion runs may use different service names (e.g., `llm-council-mcp` vs `llm-council`), creating separate entries for the same files.

## Workarounds

### Before Re-ingesting
Delete existing service data first:
```python
delete_service_data(service_name="my-service", confirm=True)
```

### Choose One ADR Ingestion Method
Either:
- Use `ingest_codebase` only (ADRs indexed as `documentation`)
- OR use `ingest_architectural_decision` for each ADR (indexed as `decision`)

Don't use both on the same files.

### Consistent Service Names
Always use the same service name across ingestion calls:
```python
# Good - consistent
ingest_codebase(repo_path=".", service_name="llm-council")
ingest_architectural_decision(adr_path="docs/adr/ADR-001.md", title="...", service="llm-council")

# Bad - inconsistent
ingest_codebase(repo_path=".", service_name="llm-council-mcp")  # Different name!
```

## Recommended Fix (Server Enhancement)

Implement upsert logic in `pixeltable_mcp_server.py`:

```python
# Pseudo-code for ingest_codebase
for file in files:
    existing = kb.where(kb.service == service_name, kb.path == file.path).collect()
    if existing:
        kb.update({kb.path == file.path, kb.service == service_name}, {
            'content': file.content,
            'updated_at': datetime.now()
        })
    else:
        kb.insert(...)
```

Key changes needed:
1. Use `(service, path)` as composite unique key
2. UPDATE existing entries instead of INSERT
3. Track `updated_at` timestamp for freshness

## Impact

- Duplicate entries waste storage
- Search results return same content multiple times
- `get_knowledge_base_stats` shows inflated counts
- Semantic search may weight duplicates higher

---

# Known Issue: Service Name Not Auto-Inferred for ADRs

> **✅ RESOLVED** - Fixed in commit implementing [GitHub Issue #3](https://github.com/amiable-dev/context-aware-ai-system/issues/3). Service names now auto-inferred from `pyproject.toml`, `package.json`, or git remote URL.

## Symptom

When using `ingest_architectural_decision` without specifying `service`, the ADR is not associated with any service, making it harder to filter by project.

## Workaround

Always specify the `service` parameter:
```python
ingest_architectural_decision(
    adr_path="docs/adr/ADR-001.md",
    title="ADR 001: Database Choice",
    service="my-service"  # Always include this
)
```

## Recommended Fix

Auto-infer service from the nearest `pyproject.toml`, `package.json`, or git remote name.

---

# Known Issue: UDF Corruption After Python Version Change

## Symptom

**Segmentation fault (exit code 139)** when running INSERT operations on the knowledge base.

The MCP server crashes without error messages, and the Claude Code terminal shows:
```
shell process exited with code 139
```

Other operations (queries, searches) may work fine - only INSERT fails.

## Root Cause

Pixeltable stores User-Defined Functions (UDFs) as pickled Python bytecode. When the Python version changes (e.g., 3.11 → 3.13), the pickled UDFs become incompatible and cause segmentation faults when triggered.

Affected computed columns:
- `is_adr` (is_architecture_decision UDF)
- `summary` (generate_summary UDF)

These columns are computed automatically on INSERT, triggering the corrupted UDFs.

## Prevention (Recommended)

The **Version Guard (ADR-001)** prevents this issue by blocking startup when Python versions mismatch. If the version guard is working correctly, you should never encounter this issue.

1. **Pin Python Version**: Set `.python-version` to match your database:
   ```
   3.13
   ```

2. **Check Before Upgrading**: Run the health check before Python upgrades:
   ```bash
   python -m scripts.db_repair --check
   ```

## Diagnosis

If you encounter segfaults, run the health check:
```bash
python -m scripts.db_repair --check
```

Expected output for corrupted database:
```
Database health check: ISSUES FOUND
  - [version_mismatch] Marker: 3.11, Current: 3.13
```

## Recovery Options

### Option 1: Use Correct Python Version (Recommended)

Switch back to the Python version that created the database:
```bash
uv venv --python 3.11
source .venv/bin/activate
```

### Option 2: Backup and Restore (Preserves Data)

Use the backup/restore utility to migrate to a new Python version:
```bash
# Backup only (safe, no modifications)
python -m scripts.backup_restore --backup --export-dir ./backup

# Full backup and restore (requires confirmation)
python -m scripts.backup_restore --backup-restore --confirm
```

This:
1. Backs up all data to Parquet files
2. Drops and recreates the table with fresh UDFs
3. Restores data (embeddings are recomputed)
4. Updates the version marker

### Option 3: Fresh Install (Deletes All Data)

If you don't need to preserve data:
```bash
rm -rf ~/.pixeltable/
```

Then restart the MCP server - it will create a fresh database.

## References

- ADR-001: Python Version Guard
- GitHub Issue #8: Database health check utility
