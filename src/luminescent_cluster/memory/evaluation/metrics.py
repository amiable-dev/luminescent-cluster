# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Evaluation metrics for memory system.

Provides precision, recall, F1 score, and other metrics for
evaluating memory retrieval quality.

Related GitHub Issues:
- #78: Create Evaluation Harness

ADR Reference: ADR-003 Memory Architecture, Phase 0 (Foundations)
"""


def precision(true_positives: int, false_positives: int) -> float:
    """Calculate precision: TP / (TP + FP).

    Precision measures how many of the retrieved memories were relevant.

    Args:
        true_positives: Number of correctly retrieved relevant memories.
        false_positives: Number of incorrectly retrieved irrelevant memories.

    Returns:
        Precision score between 0.0 and 1.0.
        Returns 0.0 if denominator is 0.

    Example:
        >>> precision(true_positives=8, false_positives=2)
        0.8
    """
    denominator = true_positives + false_positives
    if denominator == 0:
        return 0.0
    return true_positives / denominator


def recall(true_positives: int, false_negatives: int) -> float:
    """Calculate recall: TP / (TP + FN).

    Recall measures how many of the relevant memories were retrieved.

    Args:
        true_positives: Number of correctly retrieved relevant memories.
        false_negatives: Number of relevant memories that were not retrieved.

    Returns:
        Recall score between 0.0 and 1.0.
        Returns 0.0 if denominator is 0.

    Example:
        >>> recall(true_positives=8, false_negatives=2)
        0.8
    """
    denominator = true_positives + false_negatives
    if denominator == 0:
        return 0.0
    return true_positives / denominator


def f1_score(precision_val: float, recall_val: float) -> float:
    """Calculate F1 score: 2 * (precision * recall) / (precision + recall).

    F1 score is the harmonic mean of precision and recall.

    Args:
        precision_val: Precision score (0.0 to 1.0).
        recall_val: Recall score (0.0 to 1.0).

    Returns:
        F1 score between 0.0 and 1.0.
        Returns 0.0 if precision + recall = 0.

    Example:
        >>> f1_score(precision_val=0.8, recall_val=0.8)
        0.8
    """
    denominator = precision_val + recall_val
    if denominator == 0:
        return 0.0
    return 2 * (precision_val * recall_val) / denominator


def accuracy(correct: int, total: int) -> float:
    """Calculate accuracy: correct / total.

    Args:
        correct: Number of correct predictions.
        total: Total number of predictions.

    Returns:
        Accuracy score between 0.0 and 1.0.
        Returns 0.0 if total is 0.

    Example:
        >>> accuracy(correct=45, total=50)
        0.9
    """
    if total == 0:
        return 0.0
    return correct / total
