import pytest
import os
from unittest.mock import MagicMock, AsyncMock, patch
from src.utils.security import validate_path, SecurityError
from src.core.cognitive_engine import CognitiveEngine, BudgetExceededError, TokenBucket

def test_validate_path_valid():
    """Test valid path within root."""
    root = "/tmp/safe_root"
    path = "subdir/file.txt"
    # Mock os.path.abspath to avoid filesystem dependency issues in test env if paths don't exist
    # But validate_path uses os.path.abspath which doesn't require existence.
    # However, commonpath might behave differently on different OS.
    # Let's use real paths if possible or just rely on string manipulation logic of os.path
    
    # We can use the current directory as root for testing
    cwd = os.getcwd()
    valid = validate_path("test_file.txt", cwd)
    assert valid == os.path.join(cwd, "test_file.txt")

def test_validate_path_traversal():
    """Test path traversal attempt."""
    cwd = os.getcwd()
    with pytest.raises(SecurityError):
        validate_path("../outside.txt", cwd)

def test_validate_path_absolute_traversal():
    """Test absolute path outside root."""
    cwd = os.getcwd()
    outside = "/etc/passwd"
    with pytest.raises(SecurityError):
        validate_path(outside, cwd)

@pytest.mark.asyncio
async def test_token_bucket_enforcement():
    """Test that CognitiveEngine enforces token budget."""
    # Set low limit and mock API key using patch.dict to avoid side effects
    with patch.dict(os.environ, {"MAX_DAILY_TOKENS": "100", "GOOGLE_API_KEY": "dummy_key"}):
        engine = CognitiveEngine()
        
        # Mock client
        engine.client = MagicMock()
        engine.client.aio.models.generate_content = AsyncMock()
        engine.client.aio.models.generate_content.return_value.text = "Response"
        engine.client.aio.models.generate_content.return_value.usage_metadata.total_token_count = 10

        # 1. Request within budget
        await engine.generate_async("Short prompt")
        assert engine.token_bucket.current_usage > 0
        
        # 2. Request exceeding budget
        # Manually fill bucket
        engine.token_bucket.current_usage = 100
        
        with pytest.raises(BudgetExceededError):
            await engine.generate_async("This should fail")
