"""
Utility functions for content validation and cleanup.
"""

import re


def strip_code_fences(content: str) -> str:
    """
    Remove code fences from AI-generated content.
    Handles ```markdown, ```yaml, and ``` fences.
    """
    # Remove opening fence (```markdown, ```yaml, or just ```)
    content = re.sub(
        r"^```(?:markdown|yaml|json)?\s*\n", "", content, flags=re.MULTILINE
    )

    # Remove closing fence (```)
    content = re.sub(r"\n```\s*$", "", content, flags=re.MULTILINE)

    return content.strip()


def validate_markdown_format(content: str, entity_name: str) -> list:
    """
    Validate that generated content meets formatting requirements.
    Returns a list of warning messages.
    """
    warnings = []

    # Check if starts with YAML frontmatter
    if not content.startswith("---"):
        warnings.append(
            f"⚠️  {entity_name}: Output doesn't start with YAML frontmatter (---)"
        )

    # Check for GM's Truth section
    if "> [!secret]" not in content.lower():
        warnings.append(f"⚠️  {entity_name}: Missing GM's Truth section (> [!secret])")

    # Check for tags in frontmatter
    if "tags:" not in content[:500]:  # Check first 500 chars
        warnings.append(f"⚠️  {entity_name}: Missing 'tags:' in YAML frontmatter")

    # Check minimum word count (rough estimate)
    word_count = len(content.split())
    if word_count < 300:
        warnings.append(f"⚠️  {entity_name}: Only {word_count} words (expected 500+)")

    return warnings


def validate_json_outline(json_str: str) -> tuple[bool, str]:
    """
    Validate that the JSON outline is properly formatted.
    Returns (is_valid, error_message).
    """
    import json

    try:
        outline = json.loads(json_str)

        # Check required keys
        required_keys = [
            "Title",
            "Type",
            "Metadata_Keys",
            "The_GMs_Truth",
            "Adventure_Hooks",
        ]
        missing_keys = [key for key in required_keys if key not in outline]

        if missing_keys:
            return False, f"Missing required keys: {', '.join(missing_keys)}"

        return True, ""

    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {str(e)}"
