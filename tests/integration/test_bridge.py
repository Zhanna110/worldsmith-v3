import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import os
import time
from src.agents.obsidian_bridge import ObsidianBridge

@pytest.mark.asyncio
async def test_obsidian_bridge(mock_vault):
    """
    Verify ObsidianBridge functionality:
    1. Linting
    2. Visual Verification (Mocked)
    """
    
    # Mock Engine
    mock_engine = MagicMock()
    mock_engine.generate_async = AsyncMock(return_value="Looks clean! Zero issues.")
    
    bridge = ObsidianBridge(vault_root=str(mock_vault), engine=mock_engine)
    
    # 1. Test Linting (Valid)
    valid_content = "---\ntitle: Test\n---\n# Header\n[[Valid Link]]"
    errors = bridge.lint_content(valid_content)
    assert len(errors) == 0
    print("PASS: Valid content passed linting")
    
    # 2. Test Linting (Invalid)
    invalid_content = "# No Frontmatter\n[[ ]]"
    errors = bridge.lint_content(invalid_content)
    assert "Missing YAML frontmatter" in errors
    assert "Empty wikilink found: [[ ]]" in errors
    print("PASS: Invalid content caught by linter")
    
    # 3. Test Visual Verification
    # Create a dummy file
    test_file = mock_vault / "test_visual.md"
    test_file.write_text("---\ntitle: Visual\n---\n# Visual Test")
    
    result = await bridge.verify_visuals(str(test_file))
    assert result is True
    print("PASS: Visual verification passed")
    
    # Verify engine called
    mock_engine.generate_async.assert_called()
    
    # 4. Test Watchdog (Mocked Observer)
    # We won't actually wait for filesystem events in a unit test to avoid flakiness,
    # but we can test the handler directly.
    
    bridge.process_file(str(test_file))
    # Should log processing
    
    # Test file renaming on failure
    bridge.lint_content = MagicMock(return_value=["Error"])
    bridge.process_file(str(test_file))
    
    # Check if file was renamed
    renamed_files = list(mock_vault.glob("_NEEDS_REVIEW_LINT_FAIL_*"))
    assert len(renamed_files) > 0
    print(f"PASS: File renamed on failure: {renamed_files[0].name}")
