WorldSmith V3: Antigravity Implementation Plan

Objective: Upgrade the WorldSmith Sidecar MVP to a fully Agentic V3 Architecture using the "Three-Surface" methodology (Editor, Terminal, Browser).
Context: This plan operationalizes the transition from a linear RAG script to a cyclic, self-correcting LangGraph system with Supabase memory and Obsidian verification.

Phase 1: The Logic Upgrade (Cyclic Graph)

Target Surface: Editor
Agent Persona: Graph_Engineer
Workspace: WorldSmithSidecar/src/graph

Mission 1.1: Activate the Editorial Node

Context: The EditorialDirector class exists in imports but is unused. The current graph is linear (Architect -> Scanner -> Dispatcher -> Outliner -> Creator).

Task: Refactor sprawl_graph.py.

Initialize self.editor = EditorialDirector() in __init__.

Add self.workflow.add_node("editor", self.editor_node).

Critical: Reroute the edge. Change creator -> scanner to creator -> editor.

Mission 1.2: Implement the Critique Loop

Context: We need a conditional edge that allows rejection of drafts.

Task: Implement check_critique logic in sprawl_graph.py.

Update AgentState TypedDict to include:

critique_notes: str

critique_count: int

Define the condition:

IF critique_result == "APPROVE" OR critique_count > 3: Route to scanner.

IF critique_result == "REVISE": Route to creator.

Prompt Engineering: Update the creator_node prompt. If state["critique_notes"] exists, inject: "PREVIOUS DRAFT REJECTED. CRITIQUE: {critique_notes}. Fix these specific issues."

Mission 1.3: Supervisor Refinement

Context: Review langgraph_supervisor.py (uploaded in worldsmith-v3).

Task: If this file contains superior routing logic than sprawl_graph.py, merge the logic. Otherwise, deprecate it to maintain a "Single Source of Truth."

Phase 1 Validation Artifact:

Unit Test: Run tests/e2e/test_full_simulation.py.

Success Criteria: The logs must show a "REVISE" event occurring, followed by a re-generation of the text, before the file is finally saved.

Phase 2: The Memory Upgrade (Supabase Migration)

Target Surface: Terminal & Editor
Agent Persona: DB_Architect
Workspace: WorldSmithSidecar/src/core

Mission 2.1: Infrastructure Setup

Context: User provided supabase/migrations/20251125123000_init_vector_search.sql.

Task:

Install supabase and vecs python clients (pip install supabase vecs).

Execute the migration SQL against the local Supabase instance (or cloud).

Update .env to include SUPABASE_URL and SUPABASE_KEY.

Mission 2.2: Refactor Lore Retriever

Context: lore_retriever.py currently uses local ChromaDB.

Task: Create a toggle in lore_retriever.py:

If USE_SUPABASE=True, initialize SupabaseVectorStore.

Implement match_documents RPC call (Hybrid Search: Vector + JSONB Metadata).

Crucial Fix: Implement "Parent Document Retrieval."

Current: Chunks by \n\n (Context fragmentation).

New: Store the chunk embedding, but retrieve the parent section (H2 to H2) to give the Writer Agent full context.

 Phase 2 Validation Artifact:

Test Script: tests/test_vector_search.sql (mapped to Python).

Success Criteria: A query for "Alerion" returns a result from Supabase with metadata containing the correct source_file.
Phase 3: The Frontend Bridge (Obsidian Verification)

Target Surface: Browser (Headless)
Agent Persona: Obsidian_Bridge
Workspace: WorldSmithSidecar/src/agents

Mission 3.1: The Watchdog Agent

Context: file_watcher.py exists but is passive.

Task: Create src/agents/obsidian_bridge.py.

Use watchdog library to detect NEW .md files in Output/.

Linting Logic:

Check for broken Frontmatter (invalid YAML).

Check for "Orphan Links" (Wikilinks [[Like This]] that don't exist in the vault).

Mission 3.2: Visual Verification (Antigravity Exclusive)

Task: Integrate a visual check.

Agent opens the generated Markdown file in a simple HTML renderer (or Obsidian URI).

Agent takes a screenshot.

Agent passes screenshot to Gemini Vision: "Does this render look clean? Are there unformatted code blocks?"

If Failed: Flag file as _NEEDS_REVIEW_ in filename.

Phase 3 Validation Artifact:

Screen Recording: A video showing the agent detecting a file, scanning it, and moving it to the final Vault folder only after verification passes.

Phase 4: Operations & Safety

Target Surface: Terminal

Mission 4.1: Guardrails

Task: Update src/utils/security.py.

Path Traversal Check: Ensure no agent can write to ../ outside the VAULT_ROOT.

Token Budget: Add a circuit breaker. If daily_token_usage > 1,000,000, hard stop execution.

Execution Prompts (Copy/Paste to Antigravity)

To Start Phase 1:

"Act as Graph_Engineer. Read WORLDSMITH_V3_PLAN.md. Execute Phase 1.1 and 1.2 modifying src/graph/sprawl_graph.py. Focus on adding the EditorialDirector node and the conditional logic for revisions."

To Start Phase 2:

"Act as DB_Architect. Read WORLDSMITH_V3_PLAN.md. Execute Phase 2. I have provided supabase/migrations in the file tree. Install the python supabase client and refactor src/core/lore_retriever.py to support it."