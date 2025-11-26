"""
Summary Generator for World Primer Cache System
Extracts key points and entity mentions from source files to create a lightweight index.
"""

import os
import json
import asyncio
from pathlib import Path
from typing import Dict
from dotenv import load_dotenv
from src.core.cognitive_engine import CognitiveEngine

# Load environment variables
load_dotenv()


class SummaryGenerator:
    def __init__(self, source_dir: str = "Source FIles"):
        self.source_dir = source_dir
        self.engine = CognitiveEngine()
        self.cache = {
            "source": {},
            "vault": {},
            "metadata": {"version": "1.0", "total_files": 0, "last_updated": None},
        }

    def _extract_json_from_response(self, response: str) -> str:
        """
        Extract the first valid JSON object from a response that may contain extra text.
        This handles cases where the LLM adds content after the JSON.
        """
        # Find the first '{' and the last '}'
        start_idx = response.find('{')
        if start_idx == -1:
            raise ValueError("No JSON object found in response")
        
        # Find the matching closing brace
        brace_count = 0
        end_idx = -1
        for i in range(start_idx, len(response)):
            if response[i] == '{':
                brace_count += 1
            elif response[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break
        
        if end_idx == -1:
            raise ValueError("No matching closing brace found for JSON object")
        
        return response[start_idx:end_idx]

    async def extract_summary(self, file_path: str, content: str) -> Dict:
        """
        Extract key points and entity mentions from a single file.
        (Using simplified structure for reliability)
        """
        prompt = f"""
        Analyze this worldbuilding document and extract:
        
        1. **Key Points** (3-5 core facts that define this concept)
        2. **Entity Names** (A simple list of names of places, people, factions, events, concepts)
        3. **Category** (Axiom, Faction, Location, NPC, Event, Item, Lineage, etc.)
        
        Return the result as a single, flat JSON object. Do not include nested fields or importance levels.
        
        JSON STRUCTURE:
        {{
          "key_points": ["point 1", "point 2", ...],
          "entity_names": ["Entity 1", "Entity 2", ...],
          "category": "Axiom"
        }}
        
        DOCUMENT:
        {content[:8000]}
        """

        try:
            response = await self.engine.generate_async(
                prompt, response_mime_type="application/json"
            )
            # Extract only the JSON portion from the response
            json_str = self._extract_json_from_response(response)
            llm_summary = json.loads(json_str)

            # --- SYNTHESIZE FOR CACHE STRUCTURE ---
            # The LLM now returns 'entity_names' (list), but the cache expects 'entities' (dict).
            # We must convert it, setting default values for 'importance' and 'contexts'.
            entities_dict = {}
            for entity_name in llm_summary.get("entity_names", []):
                entities_dict[entity_name] = {
                    "importance": "MAJOR",  # Defaulting to MAJOR as we don't have LLM context
                    "contexts": [f"Mentioned in context of {llm_summary.get('category', 'Unknown')}"]
                }
            
            final_summary = {
                "key_points": llm_summary.get("key_points", []),
                "entities": entities_dict,
                "category": llm_summary.get("category", "Unknown"),
                "file_size": len(content),
                "word_count": len(content.split()),
            }

            return final_summary
        except Exception as e:
            # Fallback logic is used if LLM output fails to parse (due to malformed JSON)
            print(f"   ⚠️ Error extracting summary: {e}")
            return self._create_fallback_summary(content)

    def _create_fallback_summary(self, content: str) -> Dict:
        """Create a basic summary if LLM extraction fails."""
        return {
            "key_points": ["Content available but summary extraction failed"],
            "entities": {},
            "category": "Unknown",
            "file_size": len(content),
            "word_count": len(content.split()),
        }

    async def build_source_cache(self, progress_callback=None) -> Dict:
        """
        Build cache for all source files.
        """
        print(f"🔍 Scanning source files in: {self.source_dir}")

        source_path = Path(self.source_dir)
        if not source_path.exists():
            print(f"❌ Source directory not found: {self.source_dir}")
            return self.cache

        # Find all markdown files
        md_files = list(source_path.rglob("*.md"))
        total_files = len(md_files)

        print(f"📚 Found {total_files} source files")

        for idx, file_path in enumerate(md_files, 1):
            relative_path = file_path.relative_to(source_path)

            if progress_callback:
                progress_callback(idx, total_files, str(relative_path))
            else:
                print(f"   [{idx}/{total_files}] Processing: {relative_path}")

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                summary = await self.extract_summary(str(file_path), content)

                self.cache["source"][str(relative_path)] = summary

            except Exception as e:
                print(f"   ❌ Error processing {relative_path}: {e}")

        self.cache["metadata"]["total_files"] = len(self.cache["source"])

        import datetime

        self.cache["metadata"]["last_updated"] = datetime.datetime.now().isoformat()

        return self.cache

    def save_cache(self, output_path: str = "world_primer_cache.json"):
        """Save cache to JSON file."""
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, indent=2)
        print(f"💾 Cache saved to: {output_path}")

    @staticmethod
    def load_cache(cache_path: str = "world_primer_cache.json") -> Dict:
        """Load cache from JSON file."""
        if not os.path.exists(cache_path):
            return {
                "source": {},
                "vault": {},
                "metadata": {"version": "1.0", "total_files": 0},
            }

        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)


async def main():
    """Test the summary generator."""
    generator = SummaryGenerator()

    # Build cache
    cache = await generator.build_source_cache()

    # Save to file
    generator.save_cache()

    print("\n✅ Cache built successfully!")
    print(f"   Total source files: {cache['metadata']['total_files']}")
    print("   Cache file: world_primer_cache.json")


if __name__ == "__main__":
    asyncio.run(main())
