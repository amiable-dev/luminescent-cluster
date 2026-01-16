---
name: Test Gap
about: Track missing or incomplete test coverage for a requirement
title: '[TEST GAP] REQ-XXX-NNN: '
labels: 'type: test-gap, priority: medium'
assignees: ''
---

## Requirement
- **ID**: REQ-XXX-NNN
- **Title**:
- **Source**: ADR-NNN
- **Priority**: critical / high / medium / low

## Current State
Describe the current test coverage status:
- [ ] No tests exist
- [ ] Tests exist but are incomplete
- [ ] Tests exist but paths are incorrect in ledger.yml
- [ ] Tests exist but are skipped/marked xfail

## Missing Tests
List the specific tests that need to be created or fixed:

1. `tests/path/to/test.py::test_function_one`
   - Description of what this test should verify

2. `tests/path/to/test.py::test_function_two`
   - Description of what this test should verify

## Acceptance Criteria
- [ ] All listed tests are implemented
- [ ] Tests pass in CI
- [ ] spec/ledger.yml is updated with correct paths
- [ ] `python spec/validation/reconcile.py` passes

## Related Issues
<!-- Link any related issues -->

## Notes
Any additional context or implementation guidance.
