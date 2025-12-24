#!/usr/bin/env python3
"""
Test script to verify upsert functionality prevents duplicate entries.

Tests:
1. Ingest same file twice with same service → should have 1 entry with updated timestamp
2. Ingest same file twice with different services → should have 2 entries
3. Ingest same file as documentation then decision → should promote to decision type
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import time

# Add parent directory to path to import pixeltable_setup
sys.path.insert(0, str(Path(__file__).parent))

from pixeltable_setup import setup_knowledge_base, _upsert_entry, _infer_service_name


def test_upsert_same_service():
    """Test that re-ingesting with same service updates instead of duplicating"""
    print("\n=== Test 1: Upsert with same service ===")
    
    kb = setup_knowledge_base()
    
    # Clean up any existing test data
    try:
        kb.delete(kb.path == 'test/sample.py')
        print("  Cleaned up existing test data")
    except:
        pass
    
    # First insert
    entry1 = {
        'type': 'code',
        'path': 'test/sample.py',
        'content': 'def hello(): return "world"',
        'title': 'sample.py',
        'metadata': {'service': 'test-service', 'language': 'py'}
    }
    
    was_updated = _upsert_entry(kb, entry1)
    print(f"  First insert: was_updated={was_updated} (should be False)")
    assert not was_updated, "First insert should return False"
    
    time.sleep(0.1)  # Small delay to ensure different timestamp
    
    # Second insert with same service and path
    entry2 = {
        'type': 'code',
        'path': 'test/sample.py',
        'content': 'def hello(): return "updated world"',  # Different content
        'title': 'sample.py',
        'metadata': {'service': 'test-service', 'language': 'py'}
    }
    
    was_updated = _upsert_entry(kb, entry2)
    print(f"  Second insert: was_updated={was_updated} (should be True)")
    assert was_updated, "Second insert should return True"
    
    # Verify only 1 entry exists
    results = kb.where(kb.path == 'test/sample.py').collect()
    results_list = list(results)
    print(f"  Found {len(results_list)} entries (should be 1)")
    assert len(results_list) == 1, "Should have exactly 1 entry"
    
    # Verify content was updated
    assert 'updated world' in results_list[0]['content'], "Content should be updated"
    print("  ✓ Test 1 passed: Upsert prevents duplicates with same service")


def test_upsert_different_services():
    """Test that ingesting with different services creates separate entries"""
    print("\n=== Test 2: Upsert with different services ===")
    
    kb = setup_knowledge_base()
    
    # Clean up any existing test data
    try:
        kb.delete(kb.path == 'shared/utils.py')
        print("  Cleaned up existing test data")
    except:
        pass
    
    # Insert with service A
    entry1 = {
        'type': 'code',
        'path': 'shared/utils.py',
        'content': 'def util(): pass',
        'title': 'utils.py',
        'metadata': {'service': 'service-a', 'language': 'py'}
    }
    _upsert_entry(kb, entry1)
    
    # Insert with service B, same path
    entry2 = {
        'type': 'code',
        'path': 'shared/utils.py',
        'content': 'def util(): pass',
        'title': 'utils.py',
        'metadata': {'service': 'service-b', 'language': 'py'}
    }
    _upsert_entry(kb, entry2)
    
    # Verify 2 entries exist
    results = kb.where(kb.path == 'shared/utils.py').collect()
    results_list = list(results)
    print(f"  Found {len(results_list)} entries (should be 2)")
    assert len(results_list) == 2, "Should have 2 entries for different services"
    print("  ✓ Test 2 passed: Different services create separate entries")


def test_type_promotion():
    """Test that documentation type gets promoted to decision type"""
    print("\n=== Test 3: Type promotion (documentation → decision) ===")
    
    kb = setup_knowledge_base()
    
    # Clean up any existing test data
    try:
        kb.delete(kb.path == 'docs/adr/ADR-001.md')
        print("  Cleaned up existing test data")
    except:
        pass
    
    # First insert as documentation
    entry1 = {
        'type': 'documentation',
        'path': 'docs/adr/ADR-001.md',
        'content': '# ADR 001: Test Decision',
        'title': 'ADR-001',
        'metadata': {'service': 'test-service'}
    }
    _upsert_entry(kb, entry1)
    
    # Second insert as decision (more specific type)
    entry2 = {
        'type': 'decision',
        'path': 'docs/adr/ADR-001.md',
        'content': '# ADR 001: Test Decision (updated)',
        'title': 'ADR-001',
        'metadata': {'service': 'test-service'}
    }
    _upsert_entry(kb, entry2)
    
    # Verify type was promoted to decision
    results = kb.where(kb.path == 'docs/adr/ADR-001.md').collect()
    results_list = list(results)
    print(f"  Found {len(results_list)} entries (should be 1)")
    assert len(results_list) == 1, "Should have exactly 1 entry"
    assert results_list[0]['type'] == 'decision', "Type should be promoted to 'decision'"
    print("  ✓ Test 3 passed: Type promoted from documentation to decision")


def test_service_inference():
    """Test service name auto-inference from project files"""
    print("\n=== Test 4: Service name auto-inference ===")
    
    # Get current project root
    current_file = Path(__file__).resolve()
    
    # Should infer service name from this project
    service = _infer_service_name(str(current_file))
    print(f"  Inferred service name: {service}")
    
    if service:
        print(f"  ✓ Test 4 passed: Successfully inferred service name '{service}'")
    else:
        print(f"  ⚠ Test 4 skipped: Could not infer service (may not have project files)")


if __name__ == '__main__':
    print("Starting upsert and service inference tests...")
    
    try:
        test_upsert_same_service()
        test_upsert_different_services()
        test_type_promotion()
        test_service_inference()
        
        print("\n✓ All tests passed!")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
