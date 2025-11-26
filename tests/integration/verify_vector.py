import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import os
from src.core.lore_retriever import LoreRetriever

@pytest.mark.asyncio
async def test_supabase_integration(mock_vault):
    """
    Verify that LoreRetriever correctly interacts with Supabase.
    """
    # Mock Supabase Client
    mock_supabase = MagicMock()
    mock_table = MagicMock()
    mock_supabase.table.return_value = mock_table
    mock_table.upsert.return_value.execute.return_value = None
    
    mock_rpc = MagicMock()
    mock_supabase.rpc.return_value = mock_rpc
    mock_rpc.execute.return_value.data = [
        {"content": "Supabase Content", "metadata": {"source": "test.md"}, "similarity": 0.9}
    ]

    # Mock create_client to return our mock
    with patch("src.core.lore_retriever.create_client", return_value=mock_supabase):
        with patch.dict(os.environ, {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test"}):
            
            # Initialize Retriever
            retriever = LoreRetriever(
                source_path=str(mock_vault / "Source Files"),
                use_supabase=True
            )
            
            # Mock Engine Embeddings
            retriever.engine.embed_async = AsyncMock(return_value=[0.1] * 768)
            
            # 1. Test Indexing
            print("\nTesting Indexing...")
            await retriever.index_lore()
            
            # Verify upsert called
            mock_supabase.table.assert_called_with("documents")
            mock_table.upsert.assert_called()
            print("PASS: Supabase upsert called")
            
            # 2. Test Search
            print("\nTesting Search...")
            results = await retriever.search_lore("Test Query")
            
            # Verify RPC called
            mock_supabase.rpc.assert_called_with(
                "match_documents",
                {
                    "query_embedding": [0.1] * 768,
                    "match_threshold": 0.5,
                    "match_count": 5,
                }
            )
            print("PASS: Supabase RPC called")
            
            assert "Supabase Content" in results
            print("PASS: Results contain Supabase content")
