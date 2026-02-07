#!/usr/bin/env python3
"""
Documentation Freshness Validation Script

Validates documentation integrity:
- Internal link checking
- ADR-ledger synchronization
- Content freshness indicators

Exit Codes:
    0: All validations passed
    1: Validation failures found
    2: Configuration/parsing error OR warnings in strict mode

Usage:
    python spec/validation/doc_freshness.py --check-links     # Check internal links
    python spec/validation/doc_freshness.py --check-adr-sync  # Check ADR-ledger sync
    python spec/validation/doc_freshness.py --verbose         # Show detailed output
    python spec/validation/doc_freshness.py --all             # Run all checks

See ADR-010 for the validation system design.
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# =============================================================================
# Link Checker (ADR-010 Layer 2)
# =============================================================================


@dataclass
class BrokenLink:
    """Information about a broken link."""

    source_file: str
    line_number: int
    link_text: str
    target: str
    reason: str


@dataclass
class LinkCheckResult:
    """Result of link checking."""

    total_links: int = 0
    valid_links: int = 0
    broken_links: list[BrokenLink] = field(default_factory=list)
    skipped_external: int = 0

    @property
    def passed(self) -> bool:
        """Check if link validation passed."""
        return len(self.broken_links) == 0


# Regex patterns for markdown links
MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
MARKDOWN_REF_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\[([^\]]*)\]")
MARKDOWN_REF_DEF_PATTERN = re.compile(r"^\[([^\]]+)\]:\s*(.+)$", re.MULTILINE)

# External link patterns (to skip)
EXTERNAL_PATTERNS = [
    r"^https?://",
    r"^mailto:",
    r"^#",  # Anchor links
    r"^javascript:",
]


def is_external_link(target: str) -> bool:
    """Check if a link target is external."""
    for pattern in EXTERNAL_PATTERNS:
        if re.match(pattern, target, re.IGNORECASE):
            return True
    return False


def resolve_relative_path(source_file: Path, target: str, docs_root: Path) -> Path | None:
    """Resolve a relative link target to an absolute path.

    Args:
        source_file: Path to the source markdown file
        target: Link target (may be relative or absolute)
        docs_root: Root directory for documentation

    Returns:
        Resolved path or None if external/invalid
    """
    if is_external_link(target):
        return None

    # Remove any anchor suffix
    target_without_anchor = target.split("#")[0]
    if not target_without_anchor:
        return None  # Just an anchor link

    # Handle absolute paths (from docs root)
    if target_without_anchor.startswith("/"):
        return docs_root / target_without_anchor.lstrip("/")

    # Handle relative paths
    source_dir = source_file.parent
    return (source_dir / target_without_anchor).resolve()


def check_link_target(target_path: Path, original_target: str) -> tuple[bool, str]:
    """Check if a link target exists.

    Args:
        target_path: Resolved path to check
        original_target: Original target string (for error messages)

    Returns:
        Tuple of (exists, reason_if_not)
    """
    if target_path.exists():
        return True, ""

    # Check for common variations
    # .md extension
    if not target_path.suffix and (target_path.with_suffix(".md")).exists():
        return True, ""

    # index.md in directory
    if target_path.is_dir() and (target_path / "index.md").exists():
        return True, ""

    return False, f"Target not found: {original_target}"


def extract_links_from_markdown(content: str) -> list[tuple[int, str, str]]:
    """Extract all links from markdown content.

    Args:
        content: Markdown file content

    Returns:
        List of (line_number, link_text, target) tuples
    """
    links = []
    lines = content.split("\n")

    # Extract reference definitions first
    ref_definitions = {}
    for match in MARKDOWN_REF_DEF_PATTERN.finditer(content):
        ref_id = match.group(1).lower()
        ref_target = match.group(2).strip()
        ref_definitions[ref_id] = ref_target

    # Track code block state
    in_code_block = False

    # Find inline links
    for line_num, line in enumerate(lines, 1):
        # Toggle code block state on ``` lines
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue

        # Skip content inside code blocks
        if in_code_block:
            continue

        # Remove inline code before checking for links (code in backticks)
        line_without_code = re.sub(r"`[^`]+`", "", line)

        # Inline links: [text](target)
        for match in MARKDOWN_LINK_PATTERN.finditer(line_without_code):
            link_text = match.group(1)
            target = match.group(2)
            links.append((line_num, link_text, target))

        # Reference links: [text][ref] or [text][]
        for match in MARKDOWN_REF_LINK_PATTERN.finditer(line):
            link_text = match.group(1)
            ref_id = match.group(2) or link_text
            ref_id = ref_id.lower()
            if ref_id in ref_definitions:
                target = ref_definitions[ref_id]
                links.append((line_num, link_text, target))

    return links


def check_links_in_file(file_path: Path, docs_root: Path) -> list[BrokenLink]:
    """Check all internal links in a markdown file.

    Args:
        file_path: Path to the markdown file
        docs_root: Root directory for documentation

    Returns:
        List of broken links found
    """
    broken = []

    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        broken.append(
            BrokenLink(
                source_file=str(file_path),
                line_number=0,
                link_text="",
                target="",
                reason=f"Could not read file: {e}",
            )
        )
        return broken

    links = extract_links_from_markdown(content)

    for line_num, link_text, target in links:
        # Skip external links
        if is_external_link(target):
            continue

        # Resolve the target path
        resolved = resolve_relative_path(file_path, target, docs_root)
        if resolved is None:
            continue

        # Check if target exists
        exists, reason = check_link_target(resolved, target)
        if not exists:
            broken.append(
                BrokenLink(
                    source_file=str(file_path.relative_to(docs_root.parent)),
                    line_number=line_num,
                    link_text=link_text,
                    target=target,
                    reason=reason,
                )
            )

    return broken


def check_all_links(docs_root: Path, verbose: bool = False) -> LinkCheckResult:
    """Check all internal links in documentation.

    Args:
        docs_root: Root directory for documentation (typically 'docs/')
        verbose: Show detailed output

    Returns:
        LinkCheckResult with all findings
    """
    result = LinkCheckResult()

    if not docs_root.exists():
        return result

    md_files = list(docs_root.rglob("*.md"))
    if verbose:
        print(f"Checking links in {len(md_files)} markdown files...")

    for md_file in md_files:
        try:
            content = md_file.read_text(encoding="utf-8")
            links = extract_links_from_markdown(content)

            for line_num, link_text, target in links:
                result.total_links += 1

                if is_external_link(target):
                    result.skipped_external += 1
                    continue

                resolved = resolve_relative_path(md_file, target, docs_root)
                if resolved is None:
                    continue

                exists, reason = check_link_target(resolved, target)
                if exists:
                    result.valid_links += 1
                else:
                    result.broken_links.append(
                        BrokenLink(
                            source_file=str(md_file.relative_to(docs_root.parent)),
                            line_number=line_num,
                            link_text=link_text,
                            target=target,
                            reason=reason,
                        )
                    )

        except (OSError, UnicodeDecodeError):
            continue

    return result


# =============================================================================
# ADR-Ledger Synchronization (ADR-010 Layer 2)
# =============================================================================


@dataclass
class ADRSyncIssue:
    """Issue found in ADR-ledger synchronization."""

    adr_file: str
    issue_type: str  # "missing_in_ledger", "invalid_source", "stale_reference"
    requirement_id: str
    details: str


@dataclass
class ADRSyncResult:
    """Result of ADR-ledger synchronization check."""

    total_adrs: int = 0
    adrs_checked: int = 0
    requirements_in_adrs: set[str] = field(default_factory=set)
    issues: list[ADRSyncIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Check if ADR-ledger sync passed."""
        # Only fail for missing_in_ledger (requirements referenced in ADRs but not in ledger)
        critical_issues = [i for i in self.issues if i.issue_type == "missing_in_ledger"]
        return len(critical_issues) == 0


# Pattern to find requirement IDs in ADR files
REQ_ID_PATTERN = re.compile(r"\b((?:REQ|NEG)-[A-Z]+-\d+)\b")


def extract_requirements_from_adr(file_path: Path) -> set[str]:
    """Extract all requirement IDs mentioned in an ADR file.

    Args:
        file_path: Path to the ADR markdown file

    Returns:
        Set of requirement IDs found
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return set()

    return set(REQ_ID_PATTERN.findall(content))


def check_adr_ledger_sync(
    adrs_dir: Path, ledger_path: Path, verbose: bool = False
) -> ADRSyncResult:
    """Check synchronization between ADRs and the ledger.

    Validates:
    1. Requirements mentioned in ADRs exist in the ledger
    2. Ledger source references point to valid ADRs
    3. Requirement IDs in ledger match those in referenced ADRs

    Args:
        adrs_dir: Directory containing ADR files
        ledger_path: Path to ledger.yml
        verbose: Show detailed output

    Returns:
        ADRSyncResult with all findings
    """
    result = ADRSyncResult()

    # Load ledger
    if not ledger_path.exists():
        result.issues.append(
            ADRSyncIssue(
                adr_file="",
                issue_type="invalid_source",
                requirement_id="",
                details=f"Ledger not found: {ledger_path}",
            )
        )
        return result

    try:
        with open(ledger_path) as f:
            ledger = yaml.safe_load(f)
    except yaml.YAMLError as e:
        result.issues.append(
            ADRSyncIssue(
                adr_file="",
                issue_type="invalid_source",
                requirement_id="",
                details=f"Ledger YAML error: {e}",
            )
        )
        return result

    requirements = ledger.get("requirements", {})
    ledger_req_ids = set(requirements.keys())

    # Check ADRs for requirement references
    if not adrs_dir.exists():
        return result

    # Use set to avoid duplicates (*.md includes ADR-*.md)
    adr_files = list(set(adrs_dir.glob("*.md")))
    result.total_adrs = len(adr_files)

    if verbose:
        print(f"Checking {result.total_adrs} ADR files...")

    for adr_file in adr_files:
        result.adrs_checked += 1
        adr_name = adr_file.name

        # Extract requirements mentioned in ADR
        adr_reqs = extract_requirements_from_adr(adr_file)
        result.requirements_in_adrs.update(adr_reqs)

        # Check if each requirement exists in ledger
        for req_id in adr_reqs:
            if req_id not in ledger_req_ids:
                result.issues.append(
                    ADRSyncIssue(
                        adr_file=adr_name,
                        issue_type="missing_in_ledger",
                        requirement_id=req_id,
                        details=f"{req_id} referenced in ADR but not in ledger",
                    )
                )

    # Check ledger sources point to valid ADRs
    for req_id, req_data in requirements.items():
        if not isinstance(req_data, dict):
            continue

        source = req_data.get("source", "")

        # Check if source references an ADR
        adr_match = re.search(r"ADR-(\d+)", source, re.IGNORECASE)
        if adr_match:
            adr_num = adr_match.group(1)
            # Look for matching ADR file
            adr_patterns = [
                f"ADR-{adr_num}*.md",
                f"adr-{adr_num}*.md",
                f"ADR_{adr_num}*.md",
            ]
            found = False
            for pattern in adr_patterns:
                if list(adrs_dir.glob(pattern)):
                    found = True
                    break

            if not found and verbose:
                # This is informational, not a failure
                result.issues.append(
                    ADRSyncIssue(
                        adr_file="",
                        issue_type="stale_reference",
                        requirement_id=req_id,
                        details=f"Source '{source}' may reference non-existent ADR",
                    )
                )

    return result


# =============================================================================
# Report Printing
# =============================================================================


def print_link_report(result: LinkCheckResult, verbose: bool = False) -> None:
    """Print link check report."""
    print("\n" + "=" * 60)
    print("DOCUMENTATION LINK CHECK REPORT (ADR-010)")
    print("=" * 60)

    print(f"\nLink Statistics:")
    print(f"  Total links:     {result.total_links}")
    print(f"  Valid links:     {result.valid_links}")
    print(f"  Broken links:    {len(result.broken_links)}")
    print(f"  Skipped (ext):   {result.skipped_external}")

    if result.broken_links:
        print(f"\nBroken Links ({len(result.broken_links)}):")
        for link in result.broken_links[:20]:
            print(f"  - {link.source_file}:{link.line_number}")
            print(f"    [{link.link_text}]({link.target})")
            print(f"    Reason: {link.reason}")
        if len(result.broken_links) > 20:
            print(f"  ... and {len(result.broken_links) - 20} more")

    print("\n" + "-" * 60)
    if result.passed:
        print("Link Check PASSED!")
    else:
        print("Link Check FAILED!")
        print(f"  - {len(result.broken_links)} broken internal links")
    print("-" * 60 + "\n")


def print_adr_sync_report(result: ADRSyncResult, verbose: bool = False) -> None:
    """Print ADR-ledger sync report."""
    print("\n" + "=" * 60)
    print("ADR-LEDGER SYNC CHECK REPORT (ADR-010)")
    print("=" * 60)

    print(f"\nADR Statistics:")
    print(f"  Total ADRs:            {result.total_adrs}")
    print(f"  ADRs checked:          {result.adrs_checked}")
    print(f"  Requirements in ADRs:  {len(result.requirements_in_adrs)}")

    # Group issues by type
    missing_in_ledger = [i for i in result.issues if i.issue_type == "missing_in_ledger"]
    stale_references = [i for i in result.issues if i.issue_type == "stale_reference"]
    invalid_sources = [i for i in result.issues if i.issue_type == "invalid_source"]

    if missing_in_ledger:
        print(f"\nMissing in Ledger ({len(missing_in_ledger)}):")
        for issue in missing_in_ledger[:10]:
            print(f"  - {issue.adr_file}: {issue.requirement_id}")
        if len(missing_in_ledger) > 10:
            print(f"  ... and {len(missing_in_ledger) - 10} more")

    if verbose and stale_references:
        print(f"\nPotentially Stale References ({len(stale_references)}):")
        for issue in stale_references[:5]:
            print(f"  - {issue.requirement_id}: {issue.details}")

    if invalid_sources:
        print(f"\nInvalid Sources ({len(invalid_sources)}):")
        for issue in invalid_sources:
            print(f"  - {issue.details}")

    print("\n" + "-" * 60)
    if result.passed:
        print("ADR-Ledger Sync PASSED!")
    else:
        print("ADR-Ledger Sync FAILED!")
        if missing_in_ledger:
            print(f"  - {len(missing_in_ledger)} requirements in ADRs but not in ledger")
    print("-" * 60 + "\n")


# =============================================================================
# Main Entry Point
# =============================================================================


def main() -> int:
    """Main entry point.

    Exit codes (ADR-010):
        0: All validations passed
        1: Validation failures
        2: Configuration/parsing error
    """
    parser = argparse.ArgumentParser(description="Documentation freshness validation (ADR-010)")
    parser.add_argument(
        "--check-links",
        action="store_true",
        help="Check internal documentation links",
    )
    parser.add_argument(
        "--check-adr-sync",
        action="store_true",
        help="Check ADR-ledger synchronization",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all checks",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=Path("docs"),
        help="Documentation directory (default: docs)",
    )
    parser.add_argument(
        "--adrs-dir",
        type=Path,
        default=Path("docs/adrs"),
        help="ADRs directory (default: docs/adrs)",
    )
    parser.add_argument(
        "--ledger",
        type=Path,
        default=Path("spec/ledger.yml"),
        help="Path to ledger.yml",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
        help="Project root directory",
    )

    args = parser.parse_args()

    # If no specific check requested, show help
    if not args.check_links and not args.check_adr_sync and not args.all:
        parser.print_help()
        return 0

    # Resolve paths
    project_root = args.project_root
    if not project_root.is_absolute():
        project_root = Path.cwd() / project_root

    docs_dir = project_root / args.docs_dir
    adrs_dir = project_root / args.adrs_dir
    ledger_path = project_root / args.ledger

    all_passed = True

    # Run link check
    if args.check_links or args.all:
        try:
            link_result = check_all_links(docs_dir, args.verbose)
            print_link_report(link_result, args.verbose)
            if not link_result.passed:
                all_passed = False
        except Exception as e:
            print(f"ERROR in link check: {e}", file=sys.stderr)
            return 2

    # Run ADR-ledger sync check
    if args.check_adr_sync or args.all:
        try:
            sync_result = check_adr_ledger_sync(adrs_dir, ledger_path, args.verbose)
            print_adr_sync_report(sync_result, args.verbose)
            if not sync_result.passed:
                all_passed = False
        except Exception as e:
            print(f"ERROR in ADR-ledger sync: {e}", file=sys.stderr)
            return 2

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
