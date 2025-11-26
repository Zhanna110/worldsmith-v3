"""
End-to-End Test - Full Agent Lifecycle
This is the ultimate test: Run the agent from start to finish.
"""

import pytest
from src.graph.sprawl_graph import SprawlGraph


@pytest.mark.asyncio
async def test_full_agent_simulation(mock_vault, mock_llm):
    """
    The Holodeck: Full simulation test.

    This test runs the agent through its complete lifecycle:
    1. Architect reads hierarchy
    2. Dispatcher queues entities
    3. Outliner creates blueprint
    4. Creator writes file
    5. Scanner finds new entities
    6. System stops gracefully
    """
    print("\nRUNNING FULL AGENT SIMULATION (The Holodeck)")
    print("=" * 60)

    # Initialize the graph
    graph = SprawlGraph(
        root_dir=str(mock_vault), source_dir=str(mock_vault / "Source Files")
    )

    initial_state = {
        "current_file_path": "Start",
        "sprawl_queue": [],
        "visited_entities": set(),
        "recursion_depth": 0,
        "root_dir": str(mock_vault),
        "generated_files": [],
        "latest_rag_count": 0,
        "vault_glossary": [],
        "world_primer": "",
        "entity_outline": "{}",
        "current_entity_category": "Unsorted",
        "current_density_settings": ("STANDARD", 1500, "Test"),
        "simulation_mode": "FULL",
        "critique_notes": "",
        "critique_count": 0,
        "current_entity": "",
    }

    print("\nSIMULATION STAGES:\n")

    files_generated = []
    nodes_executed = []

    # Run the agent
    async for event in graph.app.astream(initial_state, config={"recursion_limit": 100}):
        for node, state in event.items():
            nodes_executed.append(node)

            if node == "architect":
                print("   - ARCHITECT: Planning phase complete")
                print(f"     Queue size: {len(state.get('sprawl_queue', []))}")

            elif node == "outliner":
                entity = (
                    state.get("sprawl_queue", ["Unknown"])[0]
                    if state.get("sprawl_queue")
                    else "Unknown"
                )
                print(f"   - OUTLINER: Created blueprint for '{entity}'")

            elif node == "creator":
                generated = state.get("generated_files", [])
                if generated:
                    latest = generated[-1]
                    files_generated.append(latest)
                    print(f"   - CREATOR: Wrote file -> {latest}")

            elif node == "scanner":
                found = len(state.get("sprawl_queue", [])) - len(
                    initial_state["sprawl_queue"]
                )
                if found > 0:
                    print(f"   - SCANNER: Found {found} new entities")

            elif node == "dispatcher":
                depth = state.get("recursion_depth", 0)
                if depth > 0:
                    print(f"   - DISPATCHER: Depth {depth}")

            elif node == "editor":
                print(f"   - EDITOR: Reviewed content. Status: {state.get('critique_notes', 'Unknown')}")

    print("\n" + "=" * 60)
    print("SIMULATION COMPLETE\n")

    # === ASSERTIONS === #

    # 1. Check that key nodes executed
    assert "architect" in nodes_executed, "Architect node did not execute"
    print("PASS: Architect node executed")

    assert "dispatcher" in nodes_executed, "Dispatcher node did not execute"
    print("PASS: Dispatcher node executed")

    assert "editor" in nodes_executed, "Editor node did not execute"
    print("PASS: Editor node executed")

    # 2. Check that at least one file was generated
    assert len(files_generated) > 0, "No files were generated"
    print(f"PASS: Generated {len(files_generated)} file(s)")

    # 3. Verify files exist on disk
    for file_path in files_generated:
        full_path = mock_vault / file_path
        assert full_path.exists(), f"File not found: {full_path}"
        print(f"PASS: File exists: {file_path}")

    # 4. Check content of first file
    if files_generated:
        first_file = mock_vault / files_generated[0]
        content = first_file.read_text()

        # Should have content
        assert len(content) > 100, "Generated file is too short"
        print("PASS: Generated content has sufficient length")

        # Should have markdown header
        assert content.startswith("#"), "Generated file missing markdown header"
        print("PASS: Content has proper markdown formatting")

    print("\nHOLODECK TEST PASSED")
    print("   All systems operational. Agent is ready for production.\n")
