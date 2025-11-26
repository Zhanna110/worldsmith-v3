import os
from typing import List, Dict


class HierarchyParser:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.entities = []  # List of {"name": str, "tier": int, "category": str}

    def parse(self) -> List[Dict]:
        """Parses the hierarchy file and returns an ordered list of entities."""
        if not os.path.exists(self.file_path):
            print(f"⚠️ Hierarchy file not found: {self.file_path}")
            return []

        with open(self.file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        current_tier = 5  # Default to lowest priority
        current_category = "Unsorted"

        parsed_data = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Detect Tier Headers
            if line.startswith("## **Tier 1"):
                current_tier = 1
            elif line.startswith("## **Tier 2"):
                current_tier = 2
            elif line.startswith("## **Tier 3"):
                current_tier = 3
            elif line.startswith("## **Tier 4"):
                current_tier = 4
            elif line.startswith("## **Tier 5"):
                current_tier = 5
            elif line.startswith("## **Meta"):
                current_tier = 99  # Special tier for meta

            # Detect Category Headers (Bold text)
            elif (
                line.startswith("**")
                and line.endswith("**")
                and not line.startswith("##")
            ):
                current_category = line.strip("*")

            # Detect List Items (Entities)
            elif line.startswith("- ") or line.startswith("* "):
                # Normalize Name
                raw_name = line.lstrip("-* ").strip()

                # Handle "Article: Name" or "Event 1.1: Name"
                # We want the core name for the entity, but maybe the full string is better for the file title?
                # The user's file has "Article: The GM's Truth". The file on disk is "Article- The GM's Truth.md".
                # For the QUEUE, we want the "Concept Name".
                # But if we queue "The GM's Truth", the agent might write "The GM's Truth.md".
                # Let's use the full raw name (normalized) as the entity name for now.

                # Remove "Article: ", "Event X.X: ", "Faction Dossier: " prefixes?
                # Actually, the user's previous files HAVE these prefixes.
                # So we should keep them to match existing files.

                # Just replace colons with hyphens to match file system
                safe_name = raw_name.replace(": ", "- ").replace(":", "-")

                parsed_data.append(
                    {
                        "name": safe_name,
                        "tier": current_tier,
                        "category": current_category,
                        "raw_line": raw_name,
                    }
                )

        self.entities = parsed_data
        return parsed_data

    def get_tier_map(self) -> Dict[str, int]:
        """Returns a dictionary mapping entity names to their tier."""
        return {item["name"]: item["tier"] for item in self.entities}
