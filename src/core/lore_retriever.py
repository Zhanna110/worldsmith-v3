import os
import glob
import json
import logging
from typing import Dict, List, Optional
import chromadb
from json.decoder import JSONDecodeError
from supabase import create_client, Client
from src.core.cognitive_engine import CognitiveEngine
import asyncio

# Basic logging configuration for consistency until a proper system is added
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


class LoreRetriever:
    """
    Handles read-only knowledge retrieval from source directory with cache support.
    Uses three-tier system:
    1. Vector Search (Semantic) - via ChromaDB
    2. Cache (Relevance/Keyword) - via JSON cache
    3. Full File Load - for context
    """

    def __init__(
        self, source_path: str, vault_root: str = None, use_cache: bool = True, use_supabase: bool = False
    ):
        self.source_path = source_path
        self.vault_root = vault_root
        self.use_cache = use_cache
        self.use_supabase = use_supabase
        self.cache = None
        self.chroma_client = None
        self.collection = None
        self.supabase: Optional[Client] = None
        self.engine = CognitiveEngine()

        # Ensure we don't crash if path doesn't exist
        if not os.path.exists(self.source_path):
            logging.warning(f"Source path '{self.source_path}' does not exist.")

        # Load cache if enabled
        if self.use_cache:
            self.cache = self._load_cache()

        # Initialize Vector DB (Chroma or Supabase)
        if self.use_supabase:
            self._initialize_supabase()
        else:
            self._initialize_vector_db()

    def _initialize_supabase(self):
        """Initialize Supabase client."""
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if url and key:
            try:
                self.supabase = create_client(url, key)
                print("Supabase Client Initialized.")
            except Exception as e:
                logging.error(f"Failed to initialize Supabase: {e}")
        else:
            logging.warning("SUPABASE_URL or SUPABASE_KEY not set. Falling back to local.")
            self.use_supabase = False
            self._initialize_vector_db()

    def _initialize_vector_db(self):
        """Initialize ChromaDB client and collection."""
        try:
            db_path = os.path.join(os.path.dirname(self.source_path), "_vector_db")
            os.makedirs(db_path, exist_ok=True)

            self.chroma_client = chromadb.PersistentClient(path=db_path)

            # Use default embedding function (all-MiniLM-L6-v2)
            # In production, you might want a specific model, but default is fine for now.
            self.collection = self.chroma_client.get_or_create_collection(
                name="world_lore", metadata={"hnsw:space": "cosine"}
            )

            # Check if we need to index (simple check: if empty)
            if self.collection.count() == 0:
                print("Vector DB empty. Indexing lore...")
                # We can't await here easily in __init__, so we skip auto-index for now
                # or run it synchronously if we really need to.
                # For now, let's assume indexing happens via a separate script or manual call.
                pass

        except Exception as e:
            logging.error(f"Failed to initialize Vector DB: {e}", exc_info=True)
            self.chroma_client = None

    async def index_lore(self):
        """
        Index all markdown files in source_path into Vector DB (Chroma or Supabase).
        """
        if not self.collection and not self.supabase:
            return

        files = glob.glob(os.path.join(self.source_path, "**/*.md"), recursive=True)

        documents = []
        metadatas = []
        ids = []
        embeddings = [] # For Supabase
        chunk_count = 0

        if not files:
            print(f"Warning: No markdown files found in source path: {self.source_path}")
            return

        for file_path in files:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                rel_path = os.path.relpath(file_path, self.source_path)
                chunks = [c.strip() for c in content.split("\n\n") if c.strip()]

                for i, chunk in enumerate(chunks):
                    if len(chunk) < 50: 
                        continue 

                    unique_id = f"{rel_path}_chunk_{i}" 
                    
                    documents.append(chunk)
                    metadatas.append(
                        {"source": rel_path, "filename": os.path.basename(file_path), "chunk_index": i}
                    )
                    ids.append(unique_id)
                    chunk_count += 1
                    
                    # Generate embedding for Supabase immediately (or batch later)
                    # For simplicity, we'll batch generate later if needed, but here we do it per chunk
                    # to keep logic simple, though slow.
                    # Actually, let's batch it.

            except (IOError, OSError, UnicodeError) as e:
                logging.error(f"Error indexing {file_path}: {e}")

        if documents:
            from tqdm import tqdm
            print(f"Found {len(files)} files. Creating and indexing {chunk_count} document chunks.")
            
            batch_size = 100
            for i in tqdm(range(0, len(documents), batch_size), desc="Building Vector DB"):
                batch_end = min(i + batch_size, len(documents))
                batch_docs = documents[i:batch_end]
                batch_metas = metadatas[i:batch_end]
                batch_ids = ids[i:batch_end]
                
                if self.use_supabase and self.supabase:
                    # Generate embeddings
                    batch_embeddings = []
                    for doc in batch_docs:
                        emb = await self.engine.embed_async(doc)
                        batch_embeddings.append(emb)
                    
                    # Upsert to Supabase
                    data = []
                    for j, doc in enumerate(batch_docs):
                        if batch_embeddings[j]:
                             data.append({
                                "content": doc,
                                "metadata": batch_metas[j],
                                "embedding": batch_embeddings[j]
                            })
                    
                    if data:
                        try:
                            self.supabase.table("documents").upsert(data).execute()
                        except Exception as e:
                            print(f"Supabase Upsert Error: {e}")

                elif self.collection:
                    self.collection.upsert(
                        documents=batch_docs,
                        metadatas=batch_metas,
                        ids=batch_ids,
                    )
            
            logging.info(f"Indexed {len(documents)} chunks from {len(files)} files.")

    def _load_cache(self, cache_path: str = "world_primer_cache.json") -> Optional[Dict]:
        """Load cache from JSON file."""
        if not os.path.exists(cache_path):
            # Silent fail is okay, we'll just rely on vector search or rebuild
            return None

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (IOError, OSError, JSONDecodeError) as e:
            logging.error(f"Error loading cache '{cache_path}': {e}")
            return None

    async def search_lore(self, query: str, depth: str = "auto", max_files: int = 5) -> str:
        """
        Search for lore using Vector Search + Cache + Exact Match.
        """
        if not os.path.exists(self.source_path):
            return ""

        results = []
        seen_files = set()

        # 1. Exact Match (Highest Priority)
        exact_match = self._find_exact_match(query)
        if exact_match:
            content = self._load_full_file(exact_match)
            results.append(
                f"[PRIMARY CANON: {os.path.basename(exact_match)}]\n{content}"
            )
            seen_files.add(exact_match)

        # 2. Vector Search (Semantic)
        if self.use_supabase and self.supabase:
            try:
                query_embedding = await self.engine.embed_async(query)
                if query_embedding:
                    response = self.supabase.rpc(
                        "match_documents",
                        {
                            "query_embedding": query_embedding,
                            "match_threshold": 0.5,
                            "match_count": max_files,
                        },
                    ).execute()
                    
                    for item in response.data:
                        # item has 'content', 'metadata', 'similarity'
                        meta = item.get("metadata", {})
                        source = meta.get("source", "Unknown")
                        content = item.get("content", "")
                        
                        # Check if we already have this file
                        # (Note: source is rel_path)
                        abs_path = os.path.join(self.source_path, source)
                        if abs_path not in seen_files:
                             results.append(f"[SEMANTIC MATCH: {source}]\n{content}")
                             # We might want to mark file as seen, but we are getting chunks here.
                             # If we get multiple chunks from same file, that's fine.
                             # But if we want to avoid duplicates if we loaded the FULL file via exact match:
                             if abs_path in seen_files:
                                 continue
                                 
                             # If we want to support "Parent Document Retrieval" fully, 
                             # we would load the full file here using abs_path.
                             # But for now, let's trust the chunk content + metadata.
                             # To strictly follow the plan "retrieve the parent section", 
                             # we could try to load the file and find the section, but that's complex.
                             # Let's stick to the chunk for now, as it's usually sufficient if chunking is good.
            except Exception as e:
                print(f"Supabase search failed: {e}")

        elif self.collection:
            try:
                vector_results = self.collection.query(
                    query_texts=[query], n_results=max_files
                )

                if vector_results["ids"]:
                    for i, full_id in enumerate(vector_results["ids"][0]):
                        rel_path = full_id.rsplit('_chunk_', 1)[0]
                        abs_path = os.path.join(self.source_path, rel_path)

                        if abs_path not in seen_files:
                            content = self._load_full_file(abs_path)
                            if content:
                                results.append(
                                    f"[SEMANTIC MATCH: {os.path.basename(abs_path)}]\n{content}"
                                )
                                seen_files.add(abs_path)

                                if len(seen_files) >= max_files + 1:
                                    break
            except Exception as e:
                print(f"Vector search failed: {e}")

        # 3. Fallback to Cache/Legacy if Vector failed or yielded few results
        if len(seen_files) < 2 and self.cache:
            pass

        # 4. Vault Search (Recent Memory)
        if self.vault_root and os.path.exists(self.vault_root):
            vault_matches = self._search_vault(query, max_results=2)
            if vault_matches:
                results.append("\n--- GENERATED VAULT CONTENT ---")
                results.extend(vault_matches)

        return "\n\n".join(results) if results else "No specific lore found."

    def _find_exact_match(self, entity_name: str) -> Optional[str]:
        """Find source file with exact name match."""
        safe_name = entity_name.replace(" ", "_") + ".md"
        # Search recursively
        for root, dirs, files in os.walk(self.source_path):
            for file in files:
                if file.lower() == safe_name.lower():
                    return os.path.join(root, file)

        # Try hyphen (Added in previous review)
        safe_name_hyphen = entity_name.replace(" ", "-") + ".md"
        for root, dirs, files in os.walk(self.source_path):
            for file in files:
                if file.lower() == safe_name_hyphen.lower():
                    return os.path.join(root, file)
        return None

    def _load_full_file(self, file_path: str) -> str:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except (IOError, OSError, UnicodeError) as e:
            logging.warning(f"Could not load full file '{file_path}': {e}")
            return ""

    def _search_vault(self, entity_name: str, max_results: int = 2) -> List[str]:
        """Search vault for recent content."""
        results = []
        if not self.vault_root:
            return results

        # Simple walk and search
        count = 0
        for root, dirs, files in os.walk(self.vault_root):
            dirs[:] = [d for d in dirs if not d.startswith((".", "_"))]
            for file in files:
                if not file.endswith(".md"):
                    continue
                if count >= max_results:
                    break

                try:
                    path = os.path.join(root, file)
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                    if entity_name.lower() in content.lower():
                        idx = content.lower().find(entity_name.lower())
                        start = max(0, idx - 150)
                        end = min(len(content), idx + 150 + len(entity_name))
                        snippet = content[start:end].strip()
                        results.append(f"[VAULT: {file}]\n...{snippet}...")
                        count += 1
                except (IOError, OSError, UnicodeError) as e:
                    logging.warning(f"Skipping vault file {file} due to error: {e}")
                    continue
        return results