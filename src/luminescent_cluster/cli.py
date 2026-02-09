"""CLI entry point for luminescent-cluster.

Usage:
    luminescent-cluster              # Combined MCP server (session + pixeltable if available)
    luminescent-cluster session      # Session-memory MCP server only
    luminescent-cluster pixeltable   # Pixeltable MCP server only (requires [pixeltable] extra)
    luminescent-cluster validate     # Run spec/ledger reconciliation
    luminescent-cluster install-skills  # Install bundled skills to .claude/skills
    luminescent-cluster --version    # Show version
"""

import argparse
import sys

from luminescent_cluster import __version__


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="luminescent-cluster",
        description="Luminescent Cluster - Context-aware AI development system",
    )
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command")

    # Session memory server
    subparsers.add_parser(
        "session",
        help="Start session-memory MCP server only",
    )

    # Pixeltable memory server
    subparsers.add_parser(
        "pixeltable",
        help="Start Pixeltable MCP server only (requires [pixeltable] extra)",
    )

    # Validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Run spec/ledger reconciliation",
    )
    validate_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output",
    )

    # Install skills command
    install_parser = subparsers.add_parser(
        "install-skills",
        help="Install bundled skills to a target directory",
    )
    install_parser.add_argument(
        "--target",
        type=str,
        default=".claude/skills",
        help="Target directory for skills (default: .claude/skills)",
    )
    install_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing skills",
    )
    install_parser.add_argument(
        "--list",
        action="store_true",
        dest="list_only",
        help="List available skills without installing",
    )

    args = parser.parse_args()

    if args.command == "session":
        serve_session()
    elif args.command == "pixeltable":
        serve_pixeltable()
    elif args.command == "validate":
        run_validate(verbose=args.verbose)
    elif args.command == "install-skills":
        install_skills(
            target=args.target,
            force=args.force,
            list_only=args.list_only,
        )
    else:
        # Default: combined MCP server
        serve_combined()


def serve_session():
    """Start the session-memory MCP server."""
    import asyncio

    from luminescent_cluster.servers.session_memory import serve

    asyncio.run(serve())


def serve_pixeltable():
    """Start the Pixeltable MCP server.

    Requires the [pixeltable] extra which includes pixeltable, torch, and
    sentence-transformers (~500MB on macOS, larger on Linux/CUDA).
    Not included in the base install.
    """
    try:
        import pixeltable  # noqa: F401
    except ImportError:
        print("Error: Pixeltable dependencies not installed.", file=sys.stderr)
        print(
            "\nThe Pixeltable server requires heavy dependencies (torch, sentence-transformers).",
            file=sys.stderr,
        )
        print("These are NOT included in the base install.", file=sys.stderr)
        print("\nInstall method depends on how you installed luminescent-cluster:", file=sys.stderr)
        print(
            '    uv tool install "luminescent-cluster[pixeltable]"   # if installed via uv tool',
            file=sys.stderr,
        )
        print(
            '    pipx install "luminescent-cluster[pixeltable]"      # if installed via pipx',
            file=sys.stderr,
        )
        print(
            '    pip install "luminescent-cluster[pixeltable]"       # if installed via pip',
            file=sys.stderr,
        )
        print(
            "\nNote: The session memory server works without these dependencies:", file=sys.stderr
        )
        print("    luminescent-cluster session", file=sys.stderr)
        sys.exit(1)

    import asyncio

    from luminescent_cluster.servers.pixeltable import serve

    asyncio.run(serve())


def serve_combined():
    """Start the combined MCP server.

    Always includes session-memory tools. If pixeltable dependencies
    are installed, also includes pixeltable tools.
    """
    import asyncio

    from luminescent_cluster.servers.session_memory import serve

    # TODO: In a future iteration, merge pixeltable tools into a single
    # FastMCP instance. For now, default to the session memory server.
    asyncio.run(serve())


def run_validate(verbose: bool = False):
    """Run spec/ledger reconciliation."""
    import subprocess
    from pathlib import Path

    script = Path(__file__).parent.parent.parent / "spec" / "validation" / "reconcile.py"
    if not script.exists():
        print("Error: reconcile.py not found. Are you in the project root?", file=sys.stderr)
        sys.exit(1)

    cmd = [sys.executable, str(script)]
    if verbose:
        cmd.append("--verbose")

    result = subprocess.run(cmd)
    sys.exit(result.returncode)


def install_skills(
    target: str = ".claude/skills",
    force: bool = False,
    list_only: bool = False,
):
    """Install bundled skills to a target directory.

    Args:
        target: Target directory for skills (default: .claude/skills)
        force: Overwrite existing skills
        list_only: List available skills without installing
    """
    import shutil
    from importlib.resources import as_file, files
    from pathlib import Path

    target = str(Path(target).expanduser())

    bundled_ref = files("luminescent_cluster.skills") / "bundled"

    with as_file(bundled_ref) as bundled_path:
        if not bundled_path.exists():
            print("Error: Bundled skills not found in package.", file=sys.stderr)
            print("This may indicate a packaging issue.", file=sys.stderr)
            sys.exit(1)

        # Find available skills
        skills = []
        for item in bundled_path.iterdir():
            if item.is_dir() and (item / "SKILL.md").exists():
                skills.append(item.name)

        if list_only:
            print("Available bundled skills:")
            for skill in sorted(skills):
                print(f"  - {skill}")
            return

        if not skills:
            print("No bundled skills found.", file=sys.stderr)
            sys.exit(1)

        # Create target directory
        target_path = Path(target)
        target_path.mkdir(parents=True, exist_ok=True)

        # Copy skills
        installed = []
        skipped = []
        for skill in sorted(skills):
            src = bundled_path / skill
            dst = target_path / skill

            if dst.exists() and not force:
                skipped.append(skill)
                continue

            if dst.exists():
                shutil.rmtree(dst)

            shutil.copytree(src, dst)
            installed.append(skill)

        # Copy marketplace.json if it exists
        marketplace_src = bundled_path / "marketplace.json"
        marketplace_dst = target_path / "marketplace.json"
        if marketplace_src.exists():
            if not marketplace_dst.exists() or force:
                shutil.copy2(marketplace_src, marketplace_dst)

        # Report results
        if installed:
            print(f"Installed {len(installed)} skill(s) to {target}:")
            for skill in installed:
                print(f"  + {skill}")

        if skipped:
            print(f"\nSkipped {len(skipped)} existing skill(s) (use --force to overwrite):")
            for skill in skipped:
                print(f"  ~ {skill}")

        if not installed and not skipped:
            print("No skills to install.")


if __name__ == "__main__":
    main()
