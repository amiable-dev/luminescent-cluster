# ADR-001: Python Version Requirement for MCP Servers

## Status
**Accepted v6** (reviewed by LLM Council 2025-12-22)

## Date
2025-12-22 (v6)

## Deciders
- Development Team
- LLM Council (Gemini-3-Pro, Claude-Opus-4.5, Grok-4)

## Context

### The Problem
The luminescent-cluster project provides MCP (Model Context Protocol) servers that enable AI assistants to access:
- **session-memory**: Git context, commits, diffs, branch info
- **pixeltable-memory**: Long-term organizational knowledge with semantic search

These servers use Pixeltable with sentence-transformers for computing embeddings during document ingestion.

### Issue Discovered
When running with Python 3.13.2 against a Pixeltable database created with Python 3.11, the MCP servers crash with a segmentation fault (exit code 139) during document ingestion.

### Root Cause Investigation

**Initial Hypothesis (Incorrect):**
Python 3.13 has compatibility issues with torch/sentence-transformers.

**Investigation Results:**

| Test | Python 3.13 Result |
|------|-------------------|
| sentence-transformers directly | ✅ Works |
| Pixeltable simple table (no embedding) | ✅ Works |
| Fresh Pixeltable table with embedding index | ✅ Works |
| Fresh Pixeltable table with UDFs + embedding | ✅ Works |
| **Existing table created on Python 3.11** | ❌ Segfaults |

### Actual Root Cause: UDF Serialization Incompatibility

Pixeltable serializes (pickles) User Defined Functions (UDFs) when creating computed columns. When a table is created on Python 3.11 and then accessed from Python 3.13:

1. The pickled UDF bytecode is incompatible
2. Deserialization during query/insert triggers a segfault
3. No Python exception is raised - the process crashes silently

**Why This Happens:**
Python's `pickle` protocol embeds bytecode that references interpreter internals. Major/minor version changes alter these internals (opcodes, AST structures), making cross-version deserialization unsafe for code objects. This is a fundamental limitation of pickling executable code, not a bug in Pixeltable.

**What This Is NOT:**
- ❌ PyTorch Python 3.13 incompatibility (PyTorch 2.6+ fully supports 3.13)
- ❌ Apple Silicon libomp issue (tested and ruled out)
- ❌ sentence-transformers bug

**What This IS:**
- ✅ Pixeltable UDF pickle format incompatibility across Python minor versions
- ✅ A data/environment coupling issue, not a code compatibility issue
- ✅ The database becomes bound to the Python version that created it

### Version Compatibility Matrix

| Created With | Safe to Run | Unsafe (Will Segfault) |
|--------------|-------------|------------------------|
| 3.10.x       | 3.10.0 - 3.10.99 | 3.9.x, 3.11+      |
| 3.11.x       | 3.11.0 - 3.11.99 | 3.10.x, 3.12+     |
| 3.12.x       | 3.12.0 - 3.12.99 | 3.11.x, 3.13+     |

**Key Insight:** Patch version upgrades (3.11.0 → 3.11.9) are **SAFE**. Only **minor/major** version changes cause pickle bytecode incompatibility.

### Critical: The Failure Mode is Silent

This issue does NOT raise a Python exception. The process segfaults, meaning:
- No `try/except` can catch it
- No logging occurs before the crash
- Supervisor processes see only an exit code (139)
- Users may blame hardware, OOM, or unrelated causes
- **A warning is insufficient - the app must refuse to start**

### Impact
- **Tables created on one Python version may not work on another**
- **MCP server crashes** are silent (segfault), making debugging extremely difficult
- **No warning** at table access time - crash only occurs during operations that invoke UDFs
- **"Works Fresh, Fails Existing"** - New tests pass while production data fails (counterintuitive)
- **Affects any Pixeltable deployment** with computed columns across Python versions

## Decision Drivers
- Eliminate silent segfaults - users should never see a crash without explanation
- Ensure consistent Python version across table creation and usage
- Provide clear guidance for multi-version environments
- Enable safe migration path when Python upgrades are needed
- Prevent the "chicken and egg" problem during upgrades

## Options Considered

### Option 1: Pin Python Version (Development Environment)
Use `.python-version` to ensure consistent version.

**Pros:** Simple, works with pyenv/uv/mise
**Cons:** Doesn't help if database already created on different version

### Option 2: Recreate Tables on Version Upgrade
When upgrading Python, recreate Pixeltable tables.

**Pros:** Clean solution, ensures compatibility
**Cons:** Requires data migration, downtime

### Option 3: Runtime Version Check + Documentation
Check Python version at startup and document the constraint.

**Pros:** Catches issues early
**Cons:** Warning alone is insufficient for segfault scenarios

### Option 4: Defense in Depth (Combined Approach)
Combine version pinning, hard startup checks, and migration procedures.

**Pros:** Multiple layers of protection, covers all scenarios
**Cons:** More complex setup

## Decision

**Multi-layered Defense in Depth (Option 4)**

### Quick Start (TL;DR)

**New Project Setup:**
```bash
# 1. Use Python 3.11 (or your chosen version)
pyenv install 3.11.9
pyenv local 3.11.9

# 2. Create venv and install
python -m venv .venv && source .venv/bin/activate
pip install -e .

# 3. Verify
python -c "import sys; print(f'Python {sys.version_info.major}.{sys.version_info.minor}')"
```

**Existing Project (Check Version):**
```bash
# Check what version the database expects
cat ~/.pixeltable/.python_version

# If mismatch, either switch Python or migrate (see Layer 6)
```

**Decision Tree:**
```
START
  │
  ├─ New project? → Use Python 3.11, follow Quick Start
  │
  ├─ Existing project, working fine? → Don't change Python version
  │
  ├─ Getting exit code 78? → Version mismatch detected
  │     └─ Either switch Python or run migration (Layer 6)
  │
  ├─ Getting exit code 65? → Legacy database without marker
  │     └─ Add marker manually: echo '3.11' > ~/.pixeltable/.python_version
  │
  └─ Getting exit code 139 (segfault)? → Guard was bypassed
        └─ Restore from backup, ensure guard runs before pixeltable import
```

### Preventive Layers

#### Layer 1: Version Pinning (.python-version)
```
3.11
```
Ensures development tools use consistent Python version.

#### Layer 2: Package Constraint (pyproject.toml)
```toml
[project]
# CAUTION: See ADR-001 - databases are locked to their creation Python version!
# This range is for NEW installations only. Existing databases WILL segfault
# if accessed from a different Python minor version than they were created with.
requires-python = ">=3.10,<3.14"
```

**Why intentionally loose?**
We allow `>=3.10,<3.14` rather than pinning to `~=3.11` because:
1. **New installations**: Users starting fresh can use any supported version
2. **Migration support**: Users migrating need to install the package on the new Python version first
3. **Layer 3 enforcement**: The runtime guard catches mismatches before segfault

If we pinned to `~=3.11`, users couldn't even install the package to run the migration procedure on Python 3.12+.

**⚠️ WARNING:** This constraint creates false confidence. A user seeing `>=3.10,<3.14` might assume they can freely upgrade from 3.10 to 3.13—but this will segfault if the database was created on 3.10. This layer does NOT protect existing databases from version mismatch. **Layer 3 is the real protection.**

#### Layer 3: Runtime Guard - HARD EXIT (Not Warning)
```python
# At MCP server entry points, BEFORE importing pixeltable
import sys
import os
from pathlib import Path

# Cross-platform file locking (Critical: fcntl is Unix-only)
try:
    import fcntl
    def lock_file(f):
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    def unlock_file(f):
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
except ImportError:
    # Windows fallback
    import msvcrt
    def lock_file(f):
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
    def unlock_file(f):
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)

# Exit codes (following sysexits.h convention)
EX_CONFIG = 78  # Configuration error - version mismatch
EX_DATAERR = 65  # Legacy database without version marker

def get_pixeltable_dir() -> Path:
    """Get Pixeltable directory, respecting PIXELTABLE_HOME if set."""
    return Path(os.environ.get('PIXELTABLE_HOME', Path.home() / '.pixeltable'))

def has_existing_database(pixeltable_dir: Path) -> bool:
    """Check if a Pixeltable database already exists (legacy or current)."""
    # Pixeltable stores data in subdirectories - check for any database artifacts
    if not pixeltable_dir.exists():
        return False
    # Check for common Pixeltable artifacts (metadata, data directories)
    indicators = ['metadata', 'data', 'pgdata', '.pixeltable.db']
    return any((pixeltable_dir / ind).exists() for ind in indicators)

def enforce_python_version():
    """
    Check for Python version mismatch with Pixeltable database.
    EXIT immediately if mismatch detected - do not proceed to segfault.

    Exit Codes:
    - 0: Success (version matches or fresh install)
    - 78 (EX_CONFIG): Version mismatch detected
    - 65 (EX_DATAERR): Legacy database without version marker

    Handles four scenarios:
    1. Version marker exists and matches: proceed
    2. Version marker exists but mismatches: exit 78
    3. No marker but DB exists (legacy): exit 65
    4. No marker and no DB: create marker (fresh install)

    Note: Patch version changes (3.11.0 → 3.11.9) are SAFE.
    Only minor/major version changes cause pickle incompatibility.
    """
    pixeltable_dir = get_pixeltable_dir()
    version_marker = pixeltable_dir / '.python_version'
    lock_file_path = pixeltable_dir / '.version.lock'
    current_version = f"{sys.version_info.major}.{sys.version_info.minor}"

    # Ensure directory exists for lock file
    pixeltable_dir.mkdir(parents=True, exist_ok=True)

    # Use file locking to prevent race conditions in parallel environments
    with open(lock_file_path, 'w') as lock:
        lock_file(lock)
        try:
            if version_marker.exists():
                stored_version = version_marker.read_text().strip().split('\n')[0]
                if stored_version != current_version:
                    print(
                        f"FATAL: Pixeltable database was created with Python {stored_version}, "
                        f"but you are running Python {current_version}.\n"
                        f"\n"
                        f"This WILL cause a segmentation fault. You must either:\n"
                        f"  1. Use Python {stored_version} (recommended)\n"
                        f"  2. Migrate data using the procedure in ADR-001\n"
                        f"\n"
                        f"To use Python {stored_version}:\n"
                        f"  uv venv --python {stored_version}\n"
                        f"  source .venv/bin/activate\n"
                        f"\n"
                        f"Marker file: {version_marker}",
                        file=sys.stderr
                    )
                    sys.exit(EX_CONFIG)  # 78
            elif has_existing_database(pixeltable_dir):
                # CRITICAL: Legacy database exists without version marker
                # We cannot safely determine what version created it
                print(
                    f"FATAL: Legacy Pixeltable database detected at {pixeltable_dir}\n"
                    f"but no Python version marker exists.\n"
                    f"\n"
                    f"This database was created before version tracking was implemented.\n"
                    f"Running with Python {current_version} may cause a segmentation fault.\n"
                    f"\n"
                    f"To fix this, you must:\n"
                    f"  1. Identify the Python version that created this database\n"
                    f"  2. Create the marker manually:\n"
                    f"     echo '3.11' > {version_marker}\n"
                    f"  3. Run again with that Python version, OR migrate per ADR-001\n",
                    file=sys.stderr
                )
                sys.exit(EX_DATAERR)  # 65
            else:
                # Fresh install - safe to create marker
                version_marker.write_text(f"{current_version}\n{sys.version}")
        finally:
            unlock_file(lock)

enforce_python_version()

# Only import pixeltable AFTER version check passes
import pixeltable as pxt
```

#### Layer 4: Docker Pinning (Critical for Production)
```dockerfile
# Pin to EXACT version matching your Pixeltable database
# This is the most important layer for production deployments
FROM python:3.11-slim-bookworm

# NEVER use these - they will eventually break:
# FROM python:3-slim
# FROM python:latest
```

#### Layer 5: CI Matrix with Cross-Version Testing
```yaml
# Standard matrix tests each version in isolation
strategy:
  matrix:
    python-version: ["3.10", "3.11", "3.12"]

# IMPORTANT: Add a dedicated cross-version test job
# This catches the actual failure mode (version mismatch on existing DB)
jobs:
  cross-version-guard-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Create DB on Python 3.11
        run: |
          uv venv --python 3.11
          source .venv/bin/activate
          uv pip install -r requirements.txt
          python -c "from pixeltable_setup import setup_knowledge_base; setup_knowledge_base()"

      - name: Verify guard blocks Python 3.12
        run: |
          uv venv --python 3.12
          source .venv/bin/activate
          uv pip install -r requirements.txt
          # The runtime guard should exit 1, NOT segfault
          if python -c "from pixeltable_mcp_server import main"; then
            echo "ERROR: Guard did not block version mismatch!"
            exit 1
          else
            echo "SUCCESS: Guard correctly blocked version mismatch"
          fi
```
Test across supported versions. The cross-version test validates the runtime guard works correctly. Consider adding Python beta/RC for early warning.

#### Layer 7: Monitoring and Observability
```python
# Add to enforce_python_version() for production monitoring
import logging

logger = logging.getLogger("pixeltable.version_guard")

def enforce_python_version():
    # ... existing code ...

    # Log successful checks (not just failures)
    if version_marker.exists():
        stored_version = version_marker.read_text().strip().split('\n')[0]
        if stored_version == current_version:
            logger.info(
                "version_check_passed",
                extra={
                    "stored_version": stored_version,
                    "current_version": current_version,
                    "pixeltable_home": str(pixeltable_dir)
                }
            )
```

**Metrics to emit:**
- `pixeltable_version_check{result="pass|fail|legacy"}` - Counter for each check type
- `pixeltable_version_guard_duration_seconds` - Guard execution time

**Alerts to configure:**
- Any `result="fail"` or `result="legacy"` in production
- Guard duration > 1 second (indicates lock contention)

### Corrective Layer

#### Layer 6: Migration Procedure

**CRITICAL: You must export data BEFORE upgrading Python. If you have already upgraded and the app segfaults, you cannot export - you must first downgrade Python.**

##### Prerequisites
- [ ] Identify all tables with computed columns/UDFs
- [ ] Estimate data volume and migration time
- [ ] Ensure sufficient disk space for export files
- [ ] Schedule maintenance window if production

##### Procedure

```bash
# ============================================
# STEP 1: FREEZE WRITES (if production)
# ============================================
# Stop any processes writing to Pixeltable

# ============================================
# STEP 2: BACKUP (before any destructive operation)
# ============================================
cp -r ~/.pixeltable ~/.pixeltable.backup.$(date +%Y%m%d)

# ============================================
# STEP 3: EXPORT DATA using OLD Python version
# ============================================
# IMPORTANT: Use Parquet - NOT pickle or JSON!
# - Pickle just moves the version problem to a file
# - JSON fails on binary data (images, embeddings) and complex types
# - Parquet preserves types and handles large datasets efficiently

OLD_PYTHON=python3.11
$OLD_PYTHON << 'EOF'
import pixeltable as pxt
import pandas as pd

kb = pxt.get_table('org_knowledge')

# Export raw columns only (not computed columns - they will regenerate)
# Record pre-export count for later verification
data = list(kb.select(
    kb.type, kb.path, kb.content, kb.title,
    kb.created_at, kb.updated_at, kb.metadata
).collect())

df = pd.DataFrame(data)
df.to_parquet('kb_backup.parquet', index=False)

# Save count for verification
with open('kb_backup_count.txt', 'w') as f:
    f.write(str(len(data)))

print(f"Exported {len(data)} rows to kb_backup.parquet")
EOF

# ============================================
# STEP 4: VERIFY EXPORT (before any destructive operation)
# ============================================
$OLD_PYTHON << 'EOF'
import pandas as pd

df = pd.read_parquet('kb_backup.parquet')
print(f"Parquet file contains {len(df)} rows")
print(f"Columns: {list(df.columns)}")
print(f"\nSample data:")
print(df.head(3).to_string())

# Verify no data loss
with open('kb_backup_count.txt') as f:
    expected = int(f.read().strip())
assert len(df) == expected, f"Data loss! Expected {expected}, got {len(df)}"
print(f"\n✅ Export verified: {len(df)} rows intact")
EOF

# ============================================
# STEP 5: VERIFY NO DATA DRIFT (catch in-flight writes)
# ============================================
$OLD_PYTHON << 'EOF'
import pixeltable as pxt

kb = pxt.get_table('org_knowledge')
current_count = kb.count()

with open('kb_backup_count.txt') as f:
    exported_count = int(f.read().strip())

if current_count != exported_count:
    print(f"ERROR: Data changed during migration!")
    print(f"Exported: {exported_count}, Current: {current_count}")
    print("Re-run from STEP 3 after ensuring writes are frozen")
    exit(1)

print(f"✅ No data drift detected: {current_count} rows")
EOF

# ============================================
# STEP 6: DROP TABLES using OLD Python
# ============================================
$OLD_PYTHON -c "
import pixeltable as pxt
pxt.drop_table('org_knowledge', force=True)
pxt.drop_table('meetings', force=True)
print('Tables dropped')
"

# Remove version marker to allow new version
rm -f ~/.pixeltable/.python_version

# ============================================
# STEP 7: SWITCH TO NEW Python version
# ============================================
NEW_PYTHON=python3.13
uv venv --python 3.13
source .venv/bin/activate
uv pip install -r requirements.txt

# ============================================
# STEP 8: RECREATE TABLES with fresh UDFs
# ============================================
# IMPORTANT: This creates NEW table schemas with UDFs compiled for the new Python version.
# The old pickled UDFs are gone (dropped in step 6). Fresh UDFs will be pickle-compatible
# with the new Python version.
$NEW_PYTHON -c "
from pixeltable_setup import setup_knowledge_base, setup_meetings_table
kb = setup_knowledge_base()
meetings = setup_meetings_table()
print('Tables recreated with fresh UDFs')
"

# ============================================
# STEP 9: RE-IMPORT DATA (Embeddings are RE-COMPUTED, not imported)
# ============================================
# CRITICAL CLARIFICATION:
# - We import RAW data (text, metadata) from Parquet
# - Embeddings are NOT imported - they are RE-COMPUTED by the fresh UDFs
# - This is intentional: the embedding UDF is now compiled for the new Python version
# - Re-computation is CPU-intensive but ensures bytecode compatibility
# - If you need to preserve exact embeddings (e.g., for reproducibility), you must
#   also pin sentence-transformers version and model weights
$NEW_PYTHON << 'EOF'
import pixeltable as pxt
import pandas as pd

kb = pxt.get_table('org_knowledge')

df = pd.read_parquet('kb_backup.parquet')
data = df.to_dict('records')

# Insert raw data - embeddings will be computed by the fresh UDF
kb.insert(data)
print(f"Imported {len(data)} rows (embeddings being recomputed...)")
EOF

# ============================================
# STEP 10: COMPREHENSIVE VALIDATION
# ============================================
$NEW_PYTHON << 'EOF'
import pixeltable as pxt
import pandas as pd

kb = pxt.get_table('org_knowledge')

# 1. Verify row counts match
with open('kb_backup_count.txt') as f:
    expected_count = int(f.read().strip())
actual_count = kb.count()

assert actual_count == expected_count, \
    f"Row count mismatch! Expected {expected_count}, got {actual_count}"
print(f"✅ Row count verified: {actual_count}")

# 2. Verify embeddings were regenerated (computed columns work)
sample = list(kb.select(kb.title, kb.embedding).limit(1).collect())
assert sample[0]['embedding'] is not None, "Embedding not regenerated!"
assert len(sample[0]['embedding']) > 0, "Empty embedding!"
print(f"✅ Embeddings regenerated: {len(sample[0]['embedding'])} dimensions")

# 3. Verify semantic search works (end-to-end UDF test)
results = list(kb.order_by(
    kb.embedding.cosine_distance("test query")
).limit(5).collect())
assert len(results) == min(5, actual_count), "Semantic search failed!"
print(f"✅ Semantic search working: found {len(results)} results")

# 4. Spot check data integrity
sample_titles = [r['title'] for r in list(kb.select(kb.title).limit(5).collect())]
print(f"✅ Sample titles: {sample_titles}")

print("\n🎉 All validations passed! Migration successful.")
EOF

# ============================================
# STEP 11: CLEANUP (after validation period)
# ============================================
# Keep backup for a few days, then:
# rm -rf ~/.pixeltable.backup.*
# rm kb_backup.parquet kb_backup_count.txt
```

##### Rollback Procedure
If migration fails at any step:
```bash
# Restore from backup
rm -rf ~/.pixeltable
mv ~/.pixeltable.backup.* ~/.pixeltable

# Revert to old Python
uv venv --python 3.11
source .venv/bin/activate
uv pip install -r requirements.txt
```

## Additional Risks and Considerations

### Risk: Shared Environments / Volumes
If multiple developers share a Pixeltable database (e.g., mounted volume, NFS, cloud sync):
- Developer A (Python 3.11) and Developer B (Python 3.12) will corrupt each other's environment
- **Mitigation:** Document single-version requirement; use separate databases per developer

### Risk: Cloud Runners / CI Version Drift
GitHub Actions, AWS Lambda, etc. may update base Python versions:
- Your app will silently crash when the runner updates
- **Mitigation:** Explicit version pinning in CI config; runtime guard catches this

### Risk: Future Python Versions
Python 3.14, 3.15, etc. will have the same issue:
- **Mitigation:** Test against Python beta/RC in CI before adopting

### Risk: Pixeltable Version Upgrades
Pixeltable itself may change serialization format:
- **Mitigation:** Pin Pixeltable version; test upgrades in staging

### Risk: Cross-Platform Database Portability
A database created on Linux **cannot** be used on Windows (and vice versa):
- Path separators differ (`/` vs `\`) in pickled paths
- File locking mechanisms differ (fcntl vs msvcrt)
- Potential NumPy ABI differences between platforms
- **Mitigation:** Treat databases as platform-specific. Use Parquet export for cross-platform data transfer.

### Risk: Database Corruption Recovery
If database is corrupted (incomplete migration, disk failure):
1. Check for backup: `~/.pixeltable.backup.*`
2. Check for Parquet exports: `./migration_backup/*.parquet`
3. If no backup: Data loss. Recreate from source.
- **Prevention:** Always complete Step 2 (backup) before any modification

### Risk: Security Implications of Pickle
Pickle can execute arbitrary code during deserialization:
- While internal here, it's an architectural fragility
- An attacker with write access to `~/.pixeltable` could inject malicious pickled code
- **Threat model:** Local privilege escalation via pickle injection
- **Mitigation:** Ensure UDF sources are trusted; restrict directory permissions; consider upstream alternatives

### Risk: Directory Permissions (Critical)
The `.pixeltable` directory contains executable code (serialized UDFs):
```bash
# Set restrictive permissions (owner-only read/write/execute)
chmod 700 ~/.pixeltable

# Verify permissions
ls -la ~ | grep pixeltable
# Expected: drwx------ ... .pixeltable

# Add to runtime guard for enforcement (optional)
import os
import stat
pixeltable_dir = Path.home() / '.pixeltable'
current_mode = pixeltable_dir.stat().st_mode & 0o777
if current_mode != 0o700:
    print(f"WARNING: ~/.pixeltable has permissions {oct(current_mode)}, should be 0700")
```
- **Why 0700?** Prevents other users from reading (stealing data) or writing (injecting malicious pickles)
- **Who is affected?** Multi-user systems, shared hosting, CI runners with shared caches

## Consequences

### Positive
- Clear understanding of root cause enables proper mitigation
- Hard exit prevents silent crashes - users always get actionable error
- Migration procedure allows safe Python upgrades
- Defense in depth catches issues at multiple stages

### Negative
- Python upgrades require data migration (downtime)
- Additional operational complexity
- Must coordinate Python versions across team/deployment

### Neutral
- This is a Pixeltable architectural constraint, not specific to this project
- May be resolved in future Pixeltable versions

## Recommendations for Pixeltable Upstream

1. **Version-stamp serialized UDFs**
   Store `sys.version_info[:2]` alongside pickled UDFs. Check on load BEFORE attempting deserialization.

2. **Detect-before-crash guard**
   Before calling `pickle.loads()`, check stored version against current. If mismatched, raise informative `PixeltableVersionError` instead of segfaulting.

3. **Provide migration tooling**
   Built-in commands like `pixeltable export-schema` / `pixeltable migrate` would automate the manual procedure above.

4. **Consider alternative serialization**
   For UDFs: store source code + AST hash instead of bytecode? This would eliminate version coupling (significant architectural change).

5. **Document prominently**
   This isn't a bug - it's a fundamental constraint. Should be in "Production Deployment" docs with clear warnings.

## Troubleshooting

### Exit Code 78: "Python version mismatch"
**Symptom:** MCP server exits immediately with code 78.
```
FATAL: Pixeltable database was created with Python 3.11, but you are running Python 3.13.
```
**Cause:** Runtime guard detected version mismatch.
**Fix:**
```bash
# Option 1: Switch to the correct Python version (recommended)
uv venv --python 3.11
source .venv/bin/activate

# Option 2: Run migration procedure (Layer 6)
```

### Exit Code 65: "Legacy database detected"
**Symptom:** MCP server exits with code 65.
```
FATAL: Legacy Pixeltable database detected but no Python version marker exists.
```
**Cause:** Database was created before version tracking was implemented.
**Fix:**
```bash
# If you know the Python version that created the database:
echo '3.11' > ~/.pixeltable/.python_version

# If unsure, use the oldest Python version you had installed when you started using Pixeltable
```

### Exit Code 139: Segmentation Fault
**Symptom:** Process crashes with no error message, exit code 139.
**Cause:** Version guard was bypassed or not installed, and incompatible pickle was deserialized.
**Fix:**
```bash
# 1. Restore from backup
rm -rf ~/.pixeltable
mv ~/.pixeltable.backup.* ~/.pixeltable

# 2. Ensure guard runs BEFORE pixeltable import
# Check your entry point - enforce_python_version() must be called first

# 3. Switch to correct Python version
cat ~/.pixeltable/.python_version  # Check expected version
uv venv --python <version>
```

### "No such file: .python_version" on fresh install
**Symptom:** Warning about missing version marker on first run.
**Cause:** Expected on first run - the marker is created automatically.
**Fix:** No action needed. The guard creates the marker on first successful run.

### File locking errors on Windows
**Symptom:** `ImportError: No module named 'fcntl'` or locking errors.
**Cause:** Using Unix-only code on Windows.
**Fix:** Ensure you're using ADR-001 v6+ which includes cross-platform locking with msvcrt fallback.

### Migration takes too long
**Symptom:** Step 9 (re-import with embedding recomputation) is slow.
**Cause:** Embeddings are being recomputed by sentence-transformers for all rows.
**Fix:**
```bash
# Check row count before migration
python -c "import pixeltable as pxt; print(pxt.get_table('org_knowledge').count())"

# For large datasets, consider:
# 1. Running migration on a GPU-enabled machine
# 2. Batching the import in chunks
# 3. Temporarily increasing compute resources
```

## References
- [Python Pickle Protocol](https://docs.python.org/3/library/pickle.html) - Bytecode compatibility varies across versions
- [PyTorch Python 3.13 Support](https://github.com/pytorch/pytorch/issues/130249) - Confirmed supported (not the issue)
- [PEP 440 - Version Specifiers](https://peps.python.org/pep-0440/)

## Changelog
- **2025-12-19 v1**: Initial ADR proposed based on assumed Python 3.13/PyTorch incompatibility
- **2025-12-19 v2**: LLM Council review recommended defense-in-depth approach
- **2025-12-19 v3**: Root cause investigation revealed actual issue is Pixeltable UDF serialization
- **2025-12-19 v4**: Council review of v3; upgraded Layer 3 from warning to hard exit; expanded migration procedure with freeze/backup/validate/rollback; added shared environment risks
- **2025-12-19 v5**: Council review (Gemini-3-Pro, Claude-Opus-4.5, Grok-4) identified critical bugs:
  - Fixed Layer 3 logic bug: detect legacy databases without version marker
  - Added file locking (`fcntl`) to prevent race conditions in parallel environments
  - Added `PIXELTABLE_HOME` environment variable support
  - Added warning about false confidence in Layer 2 (`requires-python`)
  - Changed migration export from JSON to Parquet (preserves binary data, types)
  - Added data drift detection (STEP 5) to catch in-flight writes
  - Enhanced validation (STEP 10): verify embeddings regenerated, semantic search works
  - Added cross-version CI test job
  - Added directory permissions security note
- **2025-12-22 v6**: Final council review (Gemini-3-Pro, Claude-Opus-4.5, Grok-4) - all critical issues resolved:
  - **CRITICAL FIX:** Cross-platform file locking (msvcrt fallback for Windows)
  - **CRITICAL FIX:** Documented intentional looseness of Layer 2 `requires-python`
  - Added exit codes (78=EX_CONFIG, 65=EX_DATAERR) following sysexits.h convention
  - Added Version Compatibility Matrix (patch versions safe, minor versions unsafe)
  - Clarified migration Steps 8/9: embeddings are RE-COMPUTED, not imported
  - Added Layer 7: Monitoring and Observability
  - Added Quick Start section with decision tree
  - Added comprehensive Troubleshooting section
  - Added cross-platform database portability warning
  - Added database corruption recovery guidance
  - Expanded directory permissions with code example (0700)

## Appendix: Test Results

```
# Python 3.13.2 test results

Test: sentence-transformers directly
Command: model.encode(['test'])
Result: SUCCESS

Test: Fresh pixeltable table with embedding index
Command: create table, add embedding index, insert
Result: SUCCESS

Test: Fresh pixeltable table with UDFs + embedding
Command: create table, add UDF computed columns, add embedding, insert
Result: SUCCESS

Test: Existing org_knowledge table (created on Python 3.11)
Command: kb.insert([...])
Result: SEGFAULT (exit code 139)

Conclusion: Issue is UDF serialization incompatibility, not Python/library compatibility
```
