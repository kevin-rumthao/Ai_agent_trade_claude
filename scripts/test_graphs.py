#!/usr/bin/env python3
"""Test that the graph compiles without node name conflicts."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_full_mvp_graph():
    """Test the full MVP graph compiles."""
    from app.langgraph_graphs.full_mvp_graph import create_full_mvp_graph

    print("Testing full MVP graph compilation...")
    graph = create_full_mvp_graph()
    print("✅ Full MVP graph compiled successfully!")

    # Check nodes
    print(f"   Nodes: {list(graph.nodes.keys())}")
    return True

def test_momentum_graph():
    """Test the momentum graph compiles."""
    from app.langgraph_graphs.momentum_graph import create_momentum_graph

    print("\nTesting momentum graph compilation...")
    graph = create_momentum_graph()
    print("✅ Momentum graph compiled successfully!")

    # Check nodes
    print(f"   Nodes: {list(graph.nodes.keys())}")
    return True

def test_ingest_graph():
    """Test the ingest graph compiles."""
    from app.langgraph_graphs.ingest_graph import create_ingest_graph

    print("\nTesting ingest graph compilation...")
    graph = create_ingest_graph()
    print("✅ Ingest graph compiled successfully!")

    # Check nodes
    print(f"   Nodes: {list(graph.nodes.keys())}")
    return True

if __name__ == "__main__":
    print("=" * 70)
    print("Testing LangGraph Compilation (Node Name Conflict Fix)")
    print("=" * 70)
    print()

    all_passed = True

    try:
        all_passed &= test_full_mvp_graph()
    except Exception as e:
        print(f"❌ Full MVP graph failed: {e}")
        all_passed = False

    try:
        all_passed &= test_momentum_graph()
    except Exception as e:
        print(f"❌ Momentum graph failed: {e}")
        all_passed = False

    try:
        all_passed &= test_ingest_graph()
    except Exception as e:
        print(f"❌ Ingest graph failed: {e}")
        all_passed = False

    print()
    print("=" * 70)
    if all_passed:
        print("✅ ALL TESTS PASSED - Graphs compile successfully!")
        print("=" * 70)
        print()
        print("You can now run:")
        print("  poetry run python -m app.main")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 70)
        sys.exit(1)

