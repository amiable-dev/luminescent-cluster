"""Luminescent Cluster - Context-aware AI development system.

Provides persistent memory and multi-platform chatbot capabilities
for AI agents via the MCP protocol.

Usage:
    # Start the MCP server (session memory + optional pixeltable)
    luminescent-cluster

    # Start specific server
    luminescent-cluster session
    luminescent-cluster pixeltable

For installation:
    pip install luminescent-cluster                    # Core (session memory)
    pip install "luminescent-cluster[pixeltable]"      # + long-term memory
    pip install "luminescent-cluster[all]"             # Everything
"""

try:
    from luminescent_cluster._version import __version__, __version_tuple__
except ImportError:
    # Package not installed (development mode without build)
    __version__ = "0.0.0.dev0"
    __version_tuple__ = (0, 0, 0, "dev0")

__all__ = [
    "__version__",
    "__version_tuple__",
]
