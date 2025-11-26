"""
Entity Registry module for the Vault Architect.
Manages the 'Knowledge Graph' of the world, tracking created entities,
their relationships (links), and their completion status.
"""

import os
import json
import re
from json.decoder import JSONDecodeError
from typing import List, Dict, Any
from datetime import datetime

REGISTRY_PATH = "checkpoints/entity_registry.json"


class EntityRegistry:
    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.registry_path = os.path.join(root_dir, REGISTRY_PATH)
        self.data = self._load_registry()

    def _load_registry(self) -> Dict[str, Any]:
        """Load registry from JSON or create new if not exists."""
        if os.path.exists(self.registry_path):
            try:
                with open(self.registry_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (IOError, OSError, JSONDecodeError) as e:
                print(f"   ⚠️  Error loading registry: {e}. Creating new.")

        return {
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "total_entities": 0,
            },
            "entities": {},
            "queue_plan": [],
        }

    def save(self):
        """Save registry to JSON."""
        self.data["metadata"]["last_updated"] = datetime.now().isoformat()
        self.data["metadata"]["total_entities"] = len(self.data["entities"])

        os.makedirs(os.path.dirname(self.registry_path), exist_ok=True)
        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def register_entity(
        self,
        name: str,
        category: str,
        tier: int,
        status: str = "planned",
        path: str = "",
    ):
        """Register an entity or update its status."""
        if name not in self.data["entities"]:
            self.data["entities"][name] = {
                "name": name,
                "category": category,
                "tier": tier,
                "status": status,
                "path": path,
                "word_count": 0,
                "outbound_links": [],
                "inbound_links": [],
                "created_at": datetime.now().isoformat()
                if status == "complete"
                else None,
            }
        else:
            # Update existing
            self.data["entities"][name]["status"] = status
            if path:
                self.data["entities"][name]["path"] = path
            if tier:
                self.data["entities"][name]["tier"] = tier
            if category:
                self.data["entities"][name]["category"] = category
            if status == "complete" and not self.data["entities"][name].get(
                "created_at"
            ):
                self.data["entities"][name]["created_at"] = datetime.now().isoformat()

        self.save()

    def update_content_stats(self, name: str, content: str):
        """Update word count and extract wikilinks."""
        if name not in self.data["entities"]:
            return

        # Word count
        word_count = len(content.split())
        self.data["entities"][name]["word_count"] = word_count

        # Extract wikilinks: [[Link Name]] or [[Link Name|Display Text]]
        # Regex handles both cases, capturing "Link Name"
        links = re.findall(r"\[\[(.*?)(?:\|.*?)?\]\]", content)
        unique_links = list(set(links))

        # Update outbound links
        self.data["entities"][name]["outbound_links"] = unique_links

        # Update inbound links for targets
        for target in unique_links:
            # If target exists, add inbound link
            if target in self.data["entities"]:
                if name not in self.data["entities"][target]["inbound_links"]:
                    self.data["entities"][target]["inbound_links"].append(name)
            else:
                # Optional: Register "stub" or "missing" entity?
                # For now, we just track it if it eventually gets created
                pass

        self.save()

    def get_planned_queue(self) -> List[str]:
        """Get list of entities planned but not complete."""
        return [
            name
            for name, data in self.data["entities"].items()
            if data["status"] == "planned"
        ]

    def is_complete(self, name: str) -> bool:
        """Check if entity is marked complete."""
        return self.data["entities"].get(name, {}).get("status") == "complete"
