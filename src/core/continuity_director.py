import json
import os
from typing import Dict, Optional
from datetime import datetime


class ContinuityDirector:
    """
    The Strategic Project Manager for the Simulation Engine.
    Manages the priority_queue.json to decide WHAT to build next based on:
    1. Tier Priority (Foundation > Micro)
    2. Relevance (Mentioned by major nodes)
    3. Frequency (Mentioned often)
    """

    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.queue_path = os.path.join(root_dir, "priority_queue.json")
        self.queue_data = self._load_queue()

    def _load_queue(self) -> Dict:
        if os.path.exists(self.queue_path):
            try:
                with open(self.queue_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return self._init_empty_queue()
        return self._init_empty_queue()

    def _init_empty_queue(self) -> Dict:
        return {
            "queue": {},  # "Entity Name": {score: 100, tier: 1, mentions: [], status: "pending"}
            "completed": [],
            "history": [],
        }

    def save_queue(self):
        with open(self.queue_path, "w", encoding="utf-8") as f:
            json.dump(self.queue_data, f, indent=2)

    def add_entity(self, entity: str, source: str, tier: int = 5):
        """
        Adds or updates an entity in the priority queue.
        """
        entity = entity.strip()
        if not entity:
            return

        # Skip if already completed
        if entity in self.queue_data["completed"]:
            return

        # Initialize if new
        if entity not in self.queue_data["queue"]:
            self.queue_data["queue"][entity] = {
                "score": 0,
                "tier": tier,
                "mentions": [],
                "status": "pending",
                "added_at": datetime.now().isoformat(),
            }

        # Update Metadata
        node = self.queue_data["queue"][entity]
        if source not in node["mentions"]:
            node["mentions"].append(source)

        # Update Tier if new tier is higher (lower number)
        if tier < node["tier"]:
            node["tier"] = tier

        # Recalculate Score
        node["score"] = self._calculate_score(node)

        self.save_queue()

    def _calculate_score(self, node: Dict) -> int:
        """
        Scoring Logic:
        - Base Score: Tier 1=100, Tier 2=80, Tier 3=60, Tier 4=40, Tier 5=20
        - Mention Bonus: +5 per unique source
        - Tier 1 Mention Bonus: +20 if mentioned by a Tier 1 entity (requires lookup, simplified here)
        """
        # Base Score
        tier_scores = {1: 100, 2: 80, 3: 60, 4: 40, 5: 20, 6: 10}
        score = tier_scores.get(node["tier"], 10)

        # Mention Bonus (Cap at 50)
        mention_bonus = min(len(node["mentions"]) * 5, 50)
        score += mention_bonus

        return score

    def get_next_entity(self) -> Optional[str]:
        """
        Returns the highest scoring pending entity.
        """
        pending = [
            (name, data)
            for name, data in self.queue_data["queue"].items()
            if data["status"] == "pending"
        ]

        if not pending:
            return None

        # Sort by Score (Desc), then Tier (Asc)
        # We use negative tier for sorting because lower tier number = higher priority
        pending.sort(key=lambda x: (x[1]["score"], -x[1]["tier"]), reverse=True)

        return pending[0][0]

    def mark_complete(self, entity: str):
        if entity in self.queue_data["queue"]:
            self.queue_data["queue"][entity]["status"] = "complete"
            self.queue_data["completed"].append(entity)

            # Remove from active queue map to keep file clean?
            # No, keep it for reference but maybe move to a "graveyard" key if it gets too big.
            # For now, just status update.

            self.save_queue()

    def get_queue_status(self) -> str:
        pending_count = len(
            [k for k, v in self.queue_data["queue"].items() if v["status"] == "pending"]
        )
        completed_count = len(self.queue_data["completed"])
        top_node = self.get_next_entity()
        return f"Queue: {pending_count} pending, {completed_count} complete. Next: {top_node}"
