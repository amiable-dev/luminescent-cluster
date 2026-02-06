"""CLI entry point for luminescent-cluster.

Usage:
    luminescent-cluster              # Combined MCP server (session + pixeltable if available)
    luminescent-cluster session      # Session-memory MCP server only
    luminescent-cluster pixeltable   # Pixeltable MCP server only (requires [pixeltable] extra)
    luminescent-cluster validate     # Run spec/ledger reconciliation
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

    args = parser.parse_args()

    if args.command == "session":
        serve_session()
    elif args.command == "pixeltable":
        serve_pixeltable()
    elif args.command == "validate":
        run_validate(verbose=args.verbose)
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

    Requires the [pixeltable] extra: pip install 'luminescent-cluster[pixeltable]'
    """
    try:
        import pixeltable  # noqa: F401
    except ImportError:
        print("Error: Pixeltable dependencies not installed.", file=sys.stderr)
        print("\nTo use the Pixeltable server, install with:", file=sys.stderr)
        print('    pip install "luminescent-cluster[pixeltable]"', file=sys.stderr)
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


if __name__ == "__main__":
    main()
