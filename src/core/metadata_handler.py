import os
from ruamel.yaml import YAML


class MetadataHandler:
    """
    Handles non-destructive YAML frontmatter editing using ruamel.yaml.
    """

    def __init__(self):
        self.yaml = YAML(typ="rt")
        self.yaml.preserve_quotes = True
        self.yaml.indent(mapping=2, sequence=4, offset=2)

    def update_tags_safely(self, file_path: str, new_tags_list: list[str]) -> None:
        """
        Updates the 'tags' field in the YAML frontmatter of a Markdown file.
        Preserves comments and formatting.

        Args:
            file_path: Absolute path to the markdown file.
            new_tags_list: List of tags to append.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Read the file
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract frontmatter
        if not content.startswith("---\n"):
            # No frontmatter, create it
            frontmatter = {}
            body = content
        else:
            parts = content.split("---\n", 2)
            if len(parts) < 3:
                # Malformed or empty frontmatter
                frontmatter = {}
                body = content
            else:
                frontmatter_str = parts[1]
                body = parts[2]
                frontmatter = self.yaml.load(frontmatter_str) or {}

        # Update tags
        current_tags = frontmatter.get("tags", [])
        if isinstance(current_tags, str):
            current_tags = [current_tags]

        # Use set for uniqueness but preserve order if possible, or just append new ones
        # Requirement says "append tags if they don't exist"
        updated = False
        for tag in new_tags_list:
            if tag not in current_tags:
                current_tags.append(tag)
                updated = True

        if updated:
            frontmatter["tags"] = current_tags

            # Write back
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("---\n")
                self.yaml.dump(frontmatter, f)
                f.write("---\n")
                f.write(body)
