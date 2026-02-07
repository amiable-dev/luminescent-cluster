# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
TDD: Tests for Golden Dataset validity.

These tests verify that the Golden Dataset for memory evaluation
is properly structured and contains the required question categories.

Related GitHub Issues:
- #77: Create Golden Dataset for Memory Evaluation

ADR Reference: ADR-003 Memory Architecture, Phase 0 (Foundations)
"""

import json
from pathlib import Path

import pytest


class TestGoldenDatasetStructure:
    """TDD: Tests for Golden Dataset JSON structure."""

    @pytest.fixture
    def golden_dataset(self) -> dict:
        """Load the golden dataset from JSON file."""
        dataset_path = Path(__file__).parent / "golden_dataset.json"
        with open(dataset_path) as f:
            return json.load(f)

    def test_dataset_has_required_fields(self, golden_dataset: dict):
        """Golden Dataset should have version, description, and questions.

        GitHub Issue: #77
        ADR Reference: ADR-003 Phase 0 (Golden Dataset)
        """
        assert "version" in golden_dataset
        assert "description" in golden_dataset
        assert "questions" in golden_dataset

    def test_dataset_has_50_questions(self, golden_dataset: dict):
        """Golden Dataset should contain exactly 50 evaluation questions.

        GitHub Issue: #77
        ADR Reference: ADR-003 Phase 0 (Golden Dataset)
        """
        assert len(golden_dataset["questions"]) == 50

    def test_each_question_has_required_fields(self, golden_dataset: dict):
        """Each question should have id, category, question, expected_memory_type,
        expected_scope, and expected_source fields.

        GitHub Issue: #77
        ADR Reference: ADR-003 Phase 0 (Golden Dataset)
        """
        required_fields = {
            "id",
            "category",
            "question",
            "expected_memory_type",
            "expected_scope",
            "expected_source",
        }

        for i, question in enumerate(golden_dataset["questions"]):
            missing = required_fields - set(question.keys())
            assert not missing, f"Question {i} missing fields: {missing}"


class TestGoldenDatasetCategories:
    """TDD: Tests for question category distribution."""

    @pytest.fixture
    def golden_dataset(self) -> dict:
        """Load the golden dataset from JSON file."""
        dataset_path = Path(__file__).parent / "golden_dataset.json"
        with open(dataset_path) as f:
            return json.load(f)

    def test_has_factual_recall_questions(self, golden_dataset: dict):
        """Golden Dataset should have 20 factual recall questions.

        GitHub Issue: #77
        ADR Reference: ADR-003 Phase 0 (Golden Dataset)
        Category: "What database do we use?"
        """
        factual = [q for q in golden_dataset["questions"] if q["category"] == "factual_recall"]
        assert len(factual) == 20, f"Expected 20 factual_recall, got {len(factual)}"

    def test_has_preference_recall_questions(self, golden_dataset: dict):
        """Golden Dataset should have 10 preference recall questions.

        GitHub Issue: #77
        ADR Reference: ADR-003 Phase 0 (Golden Dataset)
        Category: "Should I use tabs or spaces?"
        """
        prefs = [q for q in golden_dataset["questions"] if q["category"] == "preference_recall"]
        assert len(prefs) == 10, f"Expected 10 preference_recall, got {len(prefs)}"

    def test_has_decision_recall_questions(self, golden_dataset: dict):
        """Golden Dataset should have 10 decision recall questions.

        GitHub Issue: #77
        ADR Reference: ADR-003 Phase 0 (Golden Dataset)
        Category: "Why did we reject MongoDB?"
        """
        decisions = [q for q in golden_dataset["questions"] if q["category"] == "decision_recall"]
        assert len(decisions) == 10, f"Expected 10 decision_recall, got {len(decisions)}"

    def test_has_temporal_query_questions(self, golden_dataset: dict):
        """Golden Dataset should have 5 temporal query questions.

        GitHub Issue: #77
        ADR Reference: ADR-003 Phase 0 (Golden Dataset)
        Category: "What did we discuss about caching?"
        """
        temporal = [q for q in golden_dataset["questions"] if q["category"] == "temporal_query"]
        assert len(temporal) == 5, f"Expected 5 temporal_query, got {len(temporal)}"

    def test_has_cross_context_questions(self, golden_dataset: dict):
        """Golden Dataset should have 5 cross-context questions.

        GitHub Issue: #77
        ADR Reference: ADR-003 Phase 0 (Golden Dataset)
        Category: "What projects use auth-service?"
        """
        cross = [q for q in golden_dataset["questions"] if q["category"] == "cross_context"]
        assert len(cross) == 5, f"Expected 5 cross_context, got {len(cross)}"


class TestGoldenDatasetMemoryTypes:
    """TDD: Tests for expected memory type distribution."""

    @pytest.fixture
    def golden_dataset(self) -> dict:
        """Load the golden dataset from JSON file."""
        dataset_path = Path(__file__).parent / "golden_dataset.json"
        with open(dataset_path) as f:
            return json.load(f)

    def test_memory_types_are_valid(self, golden_dataset: dict):
        """All expected_memory_type values should be valid.

        GitHub Issue: #77
        ADR Reference: ADR-003 Phase 0 (Memory Types)
        Valid types: preference, fact, decision
        """
        valid_types = {"preference", "fact", "decision"}

        for q in golden_dataset["questions"]:
            assert q["expected_memory_type"] in valid_types, (
                f"Question {q['id']} has invalid memory_type: {q['expected_memory_type']}"
            )


class TestGoldenDatasetScopes:
    """TDD: Tests for expected scope values."""

    @pytest.fixture
    def golden_dataset(self) -> dict:
        """Load the golden dataset from JSON file."""
        dataset_path = Path(__file__).parent / "golden_dataset.json"
        with open(dataset_path) as f:
            return json.load(f)

    def test_scopes_are_valid(self, golden_dataset: dict):
        """All expected_scope values should be valid.

        GitHub Issue: #77
        ADR Reference: ADR-003 Phase 0 (Scope Hierarchy)
        Valid scopes: user, project, global
        """
        valid_scopes = {"user", "project", "global"}

        for q in golden_dataset["questions"]:
            assert q["expected_scope"] in valid_scopes, (
                f"Question {q['id']} has invalid scope: {q['expected_scope']}"
            )
