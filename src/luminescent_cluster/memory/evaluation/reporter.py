# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Evaluation report generation for memory system.

Provides report generation in JSON and Markdown formats for
evaluation results.

Related GitHub Issues:
- #78: Create Evaluation Harness

ADR Reference: ADR-003 Memory Architecture, Phase 0 (Foundations)
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class EvaluationReport:
    """Summary report of an evaluation run.

    Attributes:
        total_questions: Total number of questions evaluated.
        passed: Number of questions that passed.
        failed: Number of questions that failed.
        accuracy: Overall accuracy (passed / total).
        precision: Precision score.
        recall: Recall score.
        f1: F1 score.
        category_breakdown: Per-category results.
        latency_stats: Latency statistics (p50, p95, p99).
        timestamp: When the evaluation was run.
    """

    total_questions: int
    passed: int
    failed: int
    accuracy: float
    precision: float
    recall: float
    f1: float
    category_breakdown: dict[str, Any] = field(default_factory=dict)
    latency_stats: dict[str, float] = field(default_factory=dict)
    timestamp: Optional[str] = None

    def __post_init__(self):
        """Set timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()


def generate_json_report(report: EvaluationReport) -> str:
    """Generate a JSON report from evaluation results.

    Args:
        report: EvaluationReport to serialize.

    Returns:
        JSON string representation of the report.

    Example:
        >>> report = EvaluationReport(total_questions=50, passed=45, ...)
        >>> json_str = generate_json_report(report)
    """
    report_dict = asdict(report)
    return json.dumps(report_dict, indent=2)


def generate_markdown_report(report: EvaluationReport) -> str:
    """Generate a Markdown report from evaluation results.

    Args:
        report: EvaluationReport to format.

    Returns:
        Markdown string representation of the report.

    Example:
        >>> report = EvaluationReport(total_questions=50, passed=45, ...)
        >>> md_str = generate_markdown_report(report)
    """
    lines = [
        "# Memory Evaluation Report",
        "",
        f"**Timestamp**: {report.timestamp}",
        "",
        "## Summary",
        "",
        f"- **Total Questions**: {report.total_questions}",
        f"- **Passed**: {report.passed}",
        f"- **Failed**: {report.failed}",
        f"- **Accuracy**: {report.accuracy:.2%}",
        "",
        "## Metrics",
        "",
        f"- **Precision**: {report.precision:.2%}",
        f"- **Recall**: {report.recall:.2%}",
        f"- **F1 Score**: {report.f1:.2%}",
        "",
    ]

    if report.category_breakdown:
        lines.append("## Category Breakdown")
        lines.append("")
        lines.append("| Category | Passed | Failed | Accuracy |")
        lines.append("|----------|--------|--------|----------|")

        for cat, data in report.category_breakdown.items():
            cat_accuracy = data.get("accuracy", 0.0)
            lines.append(
                f"| {cat} | {data['passed']} | {data['failed']} | {cat_accuracy:.2%} |"
            )
        lines.append("")

    if report.latency_stats:
        lines.append("## Latency Statistics")
        lines.append("")
        for stat, value in report.latency_stats.items():
            lines.append(f"- **{stat}**: {value:.2f}ms")
        lines.append("")

    return "\n".join(lines)
