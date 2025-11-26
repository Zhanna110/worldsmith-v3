import re
from typing import Tuple, List


class EditorialDirector:
    """
    The Quality Assurance Lead.
    Responsible for:
    1. Formatting Enforcement (Obsidian standards)
    2. Word Count Verification (Dynamic Density)
    3. Auto-Fixing common LLM errors (Code fences, bad YAML)
    """

    def __init__(self):
        pass

    def review_content(
        self, content: str, density_settings: Tuple[str, int, str]
    ) -> Tuple[str, str, List[str]]:
        """
        Reviews and polishes content.
        Returns: (polished_content, status, feedback_list)
        Status: "approved", "rejected", "warning"
        """
        entity_type, target_count, _ = density_settings
        feedback = []

        # 1. Auto-Fix Formatting
        content = self._fix_formatting(content)

        # 2. Validate Structure
        if not content.startswith("---"):
            feedback.append("Missing YAML frontmatter")
            # Attempt to fix? Maybe later.

        if "> [!infobox" not in content and "> [!infobox" not in content:
            feedback.append("Missing Sidebar/Infobox")

        if "[[Source:" in content:
            feedback.append("Leftover Source placeholders found")

        # 3. Validate Word Count
        word_count = len(content.split())
        min_acceptable = int(target_count * 0.8)

        if word_count < min_acceptable:
            feedback.append(f"Low density: {word_count} words (Target: {target_count})")
            status = "rejected" if word_count < (target_count * 0.5) else "warning"
        else:
            status = "approved"

        # 4. Voice Check (Simple heuristics)
        if "In conclusion" in content or "In summary" in content:
            feedback.append("Detected essay-style conclusion (Voice Violation)")

        # Final Status Determination
        if any("Missing" in f for f in feedback):
            status = "rejected"

        return content, status, feedback

    def _fix_formatting(self, content: str) -> str:
        """
        Strips code fences and standardizes Obsidian format.
        """
        # Strip code fences
        content = re.sub(
            r"^```(?:markdown|yaml|json)?\s*\n", "", content, flags=re.MULTILINE
        )
        content = re.sub(r"\n```\s*$", "", content, flags=re.MULTILINE)

        # Ensure single H1
        # (Complex regex, maybe skip for now)

        return content.strip()
