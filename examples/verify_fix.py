import sys
from pathlib import Path

# Add parent directory to path to import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from pixeltable_setup import setup_knowledge_base, search_knowledge
from examples.example_usage import example_9_rag_fallback


def run_verification():
    print("Verifying fix...")

    # Initialize (should be fast if already exists)
    kb = setup_knowledge_base()

    # Test Search (was failing with TypeError)
    print("\nTesting Search...")
    results = search_knowledge(kb, "context", limit=1)
    print(f"Search returned {len(results)} results")

    # Test Fallback
    print("\nTesting RAG Fallback...")
    example_9_rag_fallback(kb)

    print("\n✓ Verification Complete!")


if __name__ == "__main__":
    run_verification()
