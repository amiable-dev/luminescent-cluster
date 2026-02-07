#!/usr/bin/env python3
"""
Quick test script to verify the system is working correctly
"""

import sys
from pathlib import Path


def test_imports():
    """Test that all required packages are installed"""
    print("Testing imports...")

    try:
        import git

        print("  ✓ gitpython")
    except ImportError:
        print("  ✗ gitpython - run: pip install gitpython")
        return False

    try:
        import mcp

        print("  ✓ mcp")
    except ImportError:
        print("  ✗ mcp - run: pip install mcp")
        return False

    try:
        import pixeltable as pxt

        print("  ✓ pixeltable")
    except ImportError:
        print("  ✗ pixeltable - run: pip install pixeltable")
        return False

    try:
        import sentence_transformers

        print("  ✓ sentence-transformers")
    except ImportError:
        print("  ✗ sentence-transformers - run: pip install sentence-transformers")
        return False

    return True


def test_git_repo():
    """Test that we're in a git repository"""
    print("\nTesting git repository...")

    try:
        import git

        repo = git.Repo(".", search_parent_directories=True)
        print(f"  ✓ Git repository found: {repo.working_dir}")
        print(f"  ✓ Current branch: {repo.active_branch.name}")
        return True
    except git.InvalidGitRepositoryError:
        print("  ⚠ Not in a git repository (session memory will have limited functionality)")
        return True  # Not fatal
    except Exception as e:
        print(f"  ✗ Error checking git: {e}")
        return False


def test_mcp_servers():
    """Test that MCP server files exist"""
    print("\nTesting MCP server files...")

    session_server = Path(__file__).parent / "session_memory_server.py"
    pixeltable_server = Path(__file__).parent / "pixeltable_mcp_server.py"

    if session_server.exists():
        print(f"  ✓ Session memory server: {session_server}")
    else:
        print(f"  ✗ Session memory server not found: {session_server}")
        return False

    if pixeltable_server.exists():
        print(f"  ✓ Pixeltable memory server: {pixeltable_server}")
    else:
        print(f"  ✗ Pixeltable memory server not found: {pixeltable_server}")
        return False

    return True


def test_pixeltable_setup():
    """Test Pixeltable setup script"""
    print("\nTesting Pixeltable setup...")

    setup_file = Path(__file__).parent / "pixeltable_setup.py"

    if not setup_file.exists():
        print(f"  ✗ Setup file not found: {setup_file}")
        return False

    print(f"  ✓ Pixeltable setup script: {setup_file}")
    print("  ℹ Run 'python pixeltable_setup.py' to initialize knowledge base")

    return True


def test_config():
    """Test Claude configuration"""
    print("\nTesting Claude configuration...")

    config_file = Path(__file__).parent / "claude_config.json"

    if not config_file.exists():
        print(f"  ✗ Config file not found: {config_file}")
        return False

    try:
        import json

        with open(config_file) as f:
            config = json.load(f)

        print(f"  ✓ Claude config: {config_file}")

        if "mcpServers" in config:
            print(f"  ✓ MCP servers configured: {len(config['mcpServers'])}")
            for name, server_config in config["mcpServers"].items():
                print(f"    • {name}: {server_config.get('description', 'No description')}")

        return True
    except Exception as e:
        print(f"  ✗ Error reading config: {e}")
        return False


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("CONTEXT-AWARE AI SYSTEM - VERIFICATION")
    print("=" * 60)
    print()

    tests = [
        ("Package imports", test_imports),
        ("Git repository", test_git_repo),
        ("MCP servers", test_mcp_servers),
        ("Pixeltable setup", test_pixeltable_setup),
        ("Claude config", test_config),
    ]

    results = []
    for name, test_func in tests:
        result = test_func()
        results.append((name, result))

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\n{passed}/{total} tests passed")

    if passed == total:
        print("\n✓ All tests passed! System is ready to use.")
        print("\nNext steps:")
        print("1. Run: python pixeltable_setup.py")
        print("2. Start MCP servers:")
        print("   - python session_memory_server.py")
        print("   - python pixeltable_mcp_server.py")
        print("3. Configure Claude Code with claude_config.json")
    else:
        print("\n⚠ Some tests failed. Please fix the issues above.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(run_all_tests())
