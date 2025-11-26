import os
import json
import re
import glob
from typing import TypedDict, List, Set
from langgraph.graph import StateGraph, END
from src.core.cognitive_engine import CognitiveEngine
from src.utils.security import safe_write_file
from src.core.metadata_handler import MetadataHandler
from src.core.lore_retriever import LoreRetriever
from src.core.prompts import (
    WRITER_PERSONA,
    SCANNER_INSTRUCTION,
    OUTLINER_INSTRUCTION,
    PERSONA_LIBRARY,
    GM_OMNISCIENT,
    select_persona,
)
from src.utils.entity_registry import EntityRegistry
from src.core.continuity_director import ContinuityDirector
from src.core.editorial_director import EditorialDirector
from src.core.consistency_controller import ConsistencyController
from src.utils.hierarchy_parser import HierarchyParser

TIER_MAP = {
    "Secrets": 1,
    "Cosmology": 1,
    "Magic": 1,
    "History": 2,
    "Events": 2,
    "Factions": 3,
    "Cults": 3,
    "Locations": 3,
    "Cities": 4,
    "Dungeons": 4,
    "Lineages": 5,
    "Characters": 5,
    "Bestiary": 5,
    "Items": 5,
    "Technology": 5,
}

FOLDER_MAP = {
    "Secrets": "01_The_Meta_Truths",
    "Cosmology": "02_Cosmology_and_Magic/The_Six_Axioms",
    "Magic": "02_Cosmology_and_Magic/Mechanics_of_Magic",
    "Factions": "03_Factions_and_Politics",
    "Cults": "03_Factions_and_Politics/Antagonists",
    "Locations": "04_The_Atlas/Regions",
    "Cities": "04_The_Atlas/Cities",
    "Dungeons": "04_The_Atlas/Dungeons_and_Ruins",
    "Lineages": "05_People_and_Biology/Lineages",
    "Characters": "05_People_and_Biology/NPCs",
    "Bestiary": "05_People_and_Biology/Bestiary",
    "History": "06_Timeline_and_History",
    "Events": "06_Timeline_and_History/Events",
    "Items": "07_Items_and_Tech/MacGuffins",
    "Technology": "07_Items_and_Tech/Breaker_and_Alerion_Tech",
}


def get_density_settings(category: str, tier: int = None):
    """
    Returns (Entity_Type, Target_Word_Count, Description) based on hierarchy tier.
    """
    if tier is not None:
        if tier == 1:
            return "TIER 1 FOUNDATION", 3500, "Full Earth-Level Simulation"
        elif tier in [2, 3]:
            return "TIER 2-3 MAJOR", 2500, "Deep Systemic Simulation"
        elif tier in [4, 5]:
            return "TIER 4-5 STANDARD", 1500, "Focused Simulation"
        else:
            return "TIER 6+ MICRO", 1200, "Concise Functional Simulation"

    if category in ["01_The_Meta_Truths", "02_Cosmology_and_Magic/The_Six_Axioms"]:
        return "MACRO (Foundation)", 3500, "Full Earth-Level Simulation"
    elif category in ["04_The_Atlas/Cities", "03_Factions_and_Politics"]:
        return "MACRO (Major)", 2500, "Deep Systemic Simulation"
    elif category in ["05_People_and_Biology/NPCs", "04_The_Atlas/Dungeons_and_Ruins"]:
        return "STANDARD", 1500, "Focused Simulation"
    else:
        return "MICRO", 1200, "Concise Functional Simulation"


class AgentState(TypedDict):
    current_file_path: str
    sprawl_queue: List[str]
    visited_entities: Set[str]
    recursion_depth: int
    root_dir: str
    generated_files: List[str]
    latest_rag_count: int
    vault_glossary: List[str]
    world_primer: str
    entity_outline: str
    current_entity_category: str
    current_density_settings: tuple[str, int, str]
    simulation_mode: str
    critique_notes: str
    critique_count: int
    current_entity: str


class SprawlGraph:
    def __init__(self, root_dir: str, source_dir: str = None, checkpointer=None):
        self.engine = CognitiveEngine()
        self.metadata_handler = MetadataHandler()
        self.root_dir = root_dir
        self.source_dir = (
            source_dir if source_dir else os.path.join(root_dir, "Source FIles")
        )
        self.registry = EntityRegistry(root_dir)
        self.director = ContinuityDirector(root_dir)
        self.editor = EditorialDirector()
        self.consistency = ConsistencyController()
        self.lore_retriever = LoreRetriever(self.source_dir, vault_root=self.root_dir)
        self.cache_active = False
        self.default_system_instruction = None

        self.workflow = StateGraph(AgentState)
        self.workflow.add_node("architect", self.architect_node)
        self.workflow.add_node("scanner", self.scanner_node)
        self.workflow.add_node("dispatcher", self.dispatcher_node)
        self.workflow.add_node("outliner", self.outliner_node)
        self.workflow.add_node("creator", self.creator_node)
        self.workflow.add_node("editor", self.editor_node)

        self.workflow.set_entry_point("architect")
        self.workflow.add_edge("architect", "dispatcher")
        self.workflow.add_edge("scanner", "dispatcher")
        self.workflow.add_conditional_edges(
            "dispatcher", self.dispatch_logic, {"create": "outliner", "end": END}
        )
        self.workflow.add_edge("outliner", "creator")
        self.workflow.add_conditional_edges(
            "editor", self.check_critique, {"approve": "scanner", "revise": "creator"}
        )
        self.workflow.add_edge("creator", "editor")

        self.app = self.workflow.compile(checkpointer=checkpointer)

    def initialize_cache(self, content: str):
        """Initialize Gemini Context Caching with the World Primer."""
        print(f"Initializing Cache with {len(content)} chars of World Primer...")
        self.engine.create_cache(system_instruction=content)
        if self.engine.cached_content_name:
            self.cache_active = True
            self.default_system_instruction = content
            print("Cache Active!")
        else:
            print("Cache Creation Failed. Using standard prompts.")

    def _load_world_primer(self, cache_path: str) -> str:
        """Load world primer cache and convert to comprehensive text for context caching."""
        if not os.path.exists(cache_path):
            return "Meridian world (cache not found)"
        
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
            
            # Build comprehensive primer from all cached summaries
            primer_parts = ["# Meridian World Primer\n"]
            
            for file_path, summary in cache.get("source", {}).items():
                key_points = summary.get("key_points", [])
                category = summary.get("category", "Unknown")
                
                if key_points:
                    # Use basename for cleaner context
                    name = os.path.basename(file_path).replace(".md", "").replace("_", " ")
                    primer_parts.append(f"\n## {name} ({category})")
                    for point in key_points:
                        primer_parts.append(f"- {point}")
            
            return "\n".join(primer_parts)
        except Exception as e:
            print(f"Warning: Failed to load world primer cache: {e}")
            return "Meridian world (cache load failed)"

    def find_file(self, filename: str, search_path: str) -> str | None:
        target_lower = filename.lower()
        for root, dirs, files in os.walk(search_path):
            # Exclude hidden dirs and Source Files
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith((".", "_"))
                and "Source FIles" not in d
                and "Source Files" not in d
            ]
            for file in files:
                if file.lower() == target_lower:
                    return os.path.join(root, file)
        return None

    def scan_for_stubs(self) -> List[str]:
        stubs = []
        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith((".", "_")) and "Source FIles" not in d
            ]
            for file in files:
                if file.endswith(".md"):
                    path = os.path.join(root, file)
                    try:
                        if os.path.getsize(path) < 800:
                            stubs.append(file.replace(".md", "").replace("_", " "))
                    except OSError:
                        pass
        return stubs

    def build_vault_glossary(self) -> List[str]:
        glossary = []
        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if not d.startswith((".", "_"))]
            for file in files:
                if file.endswith(".md"):
                    glossary.append(file.replace(".md", "").replace("_", " "))
        return glossary

    async def classify_entity(self, entity: str) -> str:
        keys = list(FOLDER_MAP.keys())
        prompt = f"Classify '{entity}' into one of: {keys}. Return ONLY the key name."
        try:
            key = await self.engine.generate_async(prompt)
            key = key.strip().replace("`", "").replace('"', "")
            return FOLDER_MAP.get(key, "Unsorted")
        except:
            return "Unsorted"

    async def architect_node(self, state: AgentState) -> AgentState:
        print("[ARCHITECT] Initializing...")

        search_pattern = os.path.join(self.source_dir, "**/*Tiered Hierarchy*.md")
        files = glob.glob(search_pattern, recursive=True)

        if not files:
            return state

        parser = HierarchyParser(files[0])
        ordered_entities = parser.parse()

        if not ordered_entities:
            return state

        queue_items = []
        for item in ordered_entities:
            name = item["name"]
            
            # Check if file exists on disk (Primary Truth)
            file_exists = self.find_file(name + ".md", self.root_dir)
            
            # Only skip if file actually exists
            if file_exists:
                continue
                
            # If file is missing, we queue it, even if registry says "complete"
            # (This handles the case where user deleted files to force regen)
            queue_items.append(item)

        for item in queue_items:
            state["sprawl_queue"].append(item["name"])
            self.registry.register_entity(
                name=item["name"],
                category=item["category"],
                tier=item["tier"],
                status="planned",
            )

        # Load world primer from cache in the PROJECT directory (not vault)
        # The cache file is always in the same directory as this script
        # src/graph/sprawl_graph.py -> src/graph -> src -> root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cache_path = os.path.join(project_root, "world_primer_cache.json")
        world_primer_text = self._load_world_primer(cache_path)
        state["world_primer"] = world_primer_text
        print(f"Loaded world primer: {len(world_primer_text)} chars")
        return state

    async def scanner_node(self, state: AgentState) -> AgentState:
        if "vault_glossary" not in state:
            state["vault_glossary"] = self.build_vault_glossary()

        file_path = state["current_file_path"]
        if not os.path.exists(file_path):
            return state

        all_entities = []
        if not os.path.isdir(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            prompt = (
                f"{SCANNER_INSTRUCTION}\nReturn JSON list.\nText: {content[:15000]}"
            )
            try:
                response = await self.engine.generate_async(
                    prompt, response_mime_type="application/json"
                )
                new_entities = json.loads(response)
                for entity in new_entities:
                    if isinstance(entity, str) and entity.strip():
                        all_entities.append(entity.strip())
            except:
                pass

        unique_entities = list(set(all_entities))
        for entity in unique_entities:
            if (
                entity
                and entity not in state["visited_entities"]
                and not self.registry.is_complete(entity)
            ):
                tier = 10  # Default LOW priority for scanned entities
                lower_name = entity.lower()
                if "continent" in lower_name:
                    tier = 1
                elif "region" in lower_name:
                    tier = 2
                elif "city" in lower_name:
                    tier = 3
                elif "town" in lower_name:
                    tier = 4

                self.director.add_entity(entity, source="Scanner", tier=tier)

        return state

    def dispatcher_node(self, state: AgentState) -> AgentState:
        state["recursion_depth"] = state.get("recursion_depth", 0) + 1
        if not state["sprawl_queue"]:
            next_entity = self.director.get_next_entity()
            if next_entity:
                state["sprawl_queue"].append(next_entity)
        return state

    def dispatch_logic(self, state: AgentState) -> str:
        max_depth = int(os.environ.get("MAX_RECURSION", 50))
        if state["recursion_depth"] >= max_depth or not state["sprawl_queue"]:
            return "end"
        return "create"

    async def outliner_node(self, state: AgentState) -> AgentState:
        if not state["sprawl_queue"]:
            return state

        entity = state["sprawl_queue"][0]
        category = await self.classify_entity(entity)
        state["current_entity_category"] = category

        entity_tier = None
        if entity in self.registry.data["entities"]:
            entity_tier = self.registry.data["entities"][entity]["tier"]

        entity_type, target_count, desc = get_density_settings(category, entity_tier)
        state["current_density_settings"] = (entity_type, target_count, desc)

        lore_context = await self.lore_retriever.search_lore(entity)
        prompt = f"{OUTLINER_INSTRUCTION}\nEntity: {entity}\nTarget: {target_count} words\nContext: {lore_context[:500]}"

        try:
            # If cache is active, we prepend the instruction to the prompt and pass None as system_instruction
            # This allows the cached "World Primer" to be the system instruction
            if self.cache_active:
                full_prompt = f"SYSTEM INSTRUCTION: {OUTLINER_INSTRUCTION}\n\nUSER PROMPT:\n{prompt}"
                response = await self.engine.generate_async(
                    full_prompt,
                    response_mime_type="application/json",
                    system_instruction=None,
                )
            else:
                response = await self.engine.generate_async(
                    prompt, response_mime_type="application/json"
                )
            state["entity_outline"] = response
            state["simulation_mode"] = json.loads(response).get(
                "Simulation_Mode", "FULL"
            )
        except:
            state["entity_outline"] = "{}"
            state["simulation_mode"] = "FULL"

        return state

    def check_critique(self, state: AgentState) -> str:
        """Determines if the draft needs revision."""
        critique_result = state.get("critique_notes", "")
        critique_count = state.get("critique_count", 0)

        # If approved or too many retries, move on
        if "APPROVED" in critique_result or critique_count > 3:
            return "approve"
        
        return "revise"

    async def editor_node(self, state: AgentState) -> AgentState:
        """Reviews the generated content."""
        print("🧐 [EDITOR] Reviewing content...")
        
        if not state["generated_files"]:
            return state
            
        latest_file = state["generated_files"][-1]
        
        try:
            with open(latest_file, "r", encoding="utf-8") as f:
                content = f.read()
                
            density = state.get("current_density_settings", ("STANDARD", 1500, "Focused Simulation"))
            polished, status, feedback = self.editor.review_content(content, density)
            
            # Update state with critique
            state["critique_count"] = state.get("critique_count", 0) + 1
            
            if status == "approved":
                state["critique_notes"] = "APPROVED"
                # Finalize registration here
                entity = state.get("current_entity")
                if entity:
                    category = state.get("current_entity_category", "Unsorted")
                    self.registry.register_entity(
                        name=entity, category=category, tier=5, status="complete", path=latest_file
                    )
                    self.director.mark_complete(entity)
                    state["visited_entities"].add(entity)
                    # Clear current entity for next loop
                    state["current_entity"] = ""
                    state["critique_count"] = 0
            else:
                state["critique_notes"] = "; ".join(feedback)
                print(f"    ⚠️ REVISION REQUESTED: {state['critique_notes']}")
                
        except Exception as e:
            print(f"Editor Error: {e}")
            state["critique_notes"] = "APPROVED" # Fail open to avoid infinite loops on error
            
        return state

    async def creator_node(self, state: AgentState) -> AgentState:
        entity = state.get("current_entity")
        if not entity:
            if not state["sprawl_queue"]:
                return state
            entity = state["sprawl_queue"].pop(0)
            state["current_entity"] = entity
            
        print(f"✍️  [CREATOR] Writing content for '{entity}' (Attempt {state.get('critique_count', 0) + 1})...")

        safe_filename = entity.replace(" ", "_") + ".md"
        lore_context = await self.lore_retriever.search_lore(entity)
        existing_path = self.find_file(safe_filename, self.root_dir)

        category = state.get("current_entity_category", "Unsorted")
        entity_outline = state.get("entity_outline", "{}")
        gm_mode_enabled = os.environ.get("GM_MODE", "True").lower() == "true"

        persona_key = select_persona(category, entity)
        public_voice = PERSONA_LIBRARY.get(persona_key, PERSONA_LIBRARY["CHRONICLER"])

        style_instruction = "Use Obsidian Callouts. Wikilink proper nouns."

        dual_truth_instruction = f"""
### PART 1: THE PUBLIC MYTH
{public_voice}
Write from the in-world perspective.

### PART 2: THE GM'S TRUTH
{GM_OMNISCIENT}
Reveal the mechanical reality and secrets.
        """
        
        # Inject Critique if present
        critique_notes = state.get("critique_notes", "")
        critique_instruction = ""
        if critique_notes and "APPROVED" not in critique_notes:
            critique_instruction = f"""
            PREVIOUS DRAFT REJECTED. 
            CRITIQUE: {critique_notes}
            Fix these specific issues in your rewrite.
            """

        if existing_path:
            try:
                with open(existing_path, "r", encoding="utf-8") as f:
                    old_content = f.read()

                prompt = f"""REWRITE "{entity}".
                OLD CONTENT: {old_content}
                OUTLINE: {entity_outline}
                CONTEXT: {lore_context}
                {dual_truth_instruction}
                {critique_instruction}"""
                target_path = existing_path
            except Exception as e:
                print(f"Error reading existing file {existing_path}: {e}")
                return state
        else:
            prompt = f"""Write NEW entry "{entity}".
            OUTLINE: {entity_outline}
            CONTEXT: {lore_context}
            {dual_truth_instruction}
            {critique_instruction}
            
            CRITICAL INSTRUCTION:
            - Write ONLY the article content.
            - DO NOT output a list of files.
            - DO NOT output the World Primer or context.
            - DO NOT append a 'GENERATED VAULT CONTENT' section.
            """
            target_path = os.path.join(category, safe_filename)

        if self.cache_active:
            full_prompt = (
                f"SYSTEM INSTRUCTION: {WRITER_PERSONA}\n\nUSER PROMPT:\n{prompt}"
            )
            content = await self.engine.generate_async(
                full_prompt, system_instruction=None
            )
        else:
            content = await self.engine.generate_async(
                prompt, system_instruction=WRITER_PERSONA
            )

        # CRITICAL SAFETY: Strip code fences if LLM disobeys "no code fence" instruction

        content = re.sub(
            r"^```(?:markdown|yaml|json)?\s*\n", "", content, flags=re.MULTILINE
        )
        content = re.sub(r"\n```\s*$", "", content, flags=re.MULTILINE)
        content = content.strip()

        # VALIDATION: Ensure YAML frontmatter compliance
        if not content.startswith("---"):
            print(
                f"   ⚠️  WARNING: Output for '{entity}' doesn't start with YAML frontmatter!"
            )

        safe_write_file(target_path, content, self.root_dir)

        # Only append if not already in list (to avoid duplicates on retries)
        if target_path not in state["generated_files"]:
            state["generated_files"].append(target_path)
            
        # NOTE: Registration moved to Editor Node on approval

        return state
