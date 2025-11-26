import os
from typing import Optional
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential
import time

class BudgetExceededError(Exception):
    """Raised when the daily token budget is exceeded."""
    pass

class TokenBucket:
    """
    Simple token bucket for rate limiting and budget tracking.
    """
    def __init__(self, max_tokens: int):
        self.max_tokens = max_tokens
        self.current_usage = 0
        self.last_reset = time.time()
        
    def check_budget(self, estimated_cost: int = 0):
        """Check if we have enough budget."""
        if self.current_usage + estimated_cost > self.max_tokens:
            raise BudgetExceededError(f"Daily limit of {self.max_tokens} tokens exceeded. Current: {self.current_usage}")
            
    def add_usage(self, tokens: int):
        """Add usage to the bucket."""
        self.current_usage += tokens
        # In a real app, we'd persist this or reset daily.
        # For now, it's in-memory per session.


class CognitiveEngine:
    """
    High-velocity async inference wrapper for Gemini 2.5 Flash-Lite.
    Supports Context Caching for large system instructions.
    """

    def __init__(self):
        """
        Initialize the unified genai.Client for Gemini API.
        """
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")

        # Standard Gemini API mode
        self.client = genai.Client(api_key=api_key)

        self.model_name = "gemini-2.5-flash-lite"
        self.cached_content_name = None
        
        # Initialize Token Bucket (Default 1M tokens)
        max_tokens = int(os.environ.get("MAX_DAILY_TOKENS", 1000000))
        self.token_bucket = TokenBucket(max_tokens)

    def create_cache(self, system_instruction: str, ttl_minutes: int = 60):
        """
        Create a cached content object for the system instruction.
        This reduces token usage for repeated calls with the same system prompt.
        """
        try:
            # Create cache config
            # Note: The exact syntax depends on the SDK version.
            # Assuming google-genai v0.3+ / v1.0 structure.

            # We'll use a fixed name or let the API generate one.
            # For simplicity, we'll create a new one each time this is called,
            # but in a real app you'd check if one exists.

            cache_config = types.CreateCachedContentConfig(
                system_instruction=system_instruction,
                ttl=f"{ttl_minutes * 60}s",
            )

            cached_content = self.client.caches.create(
                model=self.model_name, config=cache_config
            )
            self.cached_content_name = cached_content.name
            print(f"Created Gemini Cache: {self.cached_content_name}")

        except Exception as e:
            print(
                f"Warning: Failed to create cache: {e}. Falling back to standard prompt."
            )
            self.cached_content_name = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def generate_async(
        self,
        prompt: str,
        image: Optional[bytes] = None,
        system_instruction: Optional[str] = None,
        response_mime_type: Optional[str] = None,
    ) -> str:
        """
        Non-blocking generation using client.aio.models.generate_content.
        Optimized for high throughput (4,000 RPM).
        Supports Image input for Vision capabilities.
        Enforces Token Budget.
        """
        # Check budget before request (estimate input tokens roughly)
        # 1 char ~= 0.25 tokens. Let's be conservative.
        estimated_input = len(prompt) // 3
        self.token_bucket.check_budget(estimated_input)
        
        contents = [prompt]
        if image:
            contents.append(types.Part.from_bytes(data=image, mime_type="image/png"))

        # If we have a valid cache and no specific system instruction override is passed,
        # use the cache.
        if self.cached_content_name and system_instruction is None:
            # When using cache, we pass the cache name in the config or model argument
            # The SDK usually allows passing 'cached_content' in config
            config = types.GenerateContentConfig(
                response_mime_type=response_mime_type,
                cached_content=self.cached_content_name,
            )

            # Note: When using cached content, 'model' arg might need to be omitted or specific.
            # But usually passing the model name is fine.
            response = await self.client.aio.models.generate_content(
                model=self.model_name, contents=contents, config=config
            )
        else:
            # Standard path
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type=response_mime_type,
            )

            response = await self.client.aio.models.generate_content(
                model=self.model_name, contents=contents, config=config
            )

        # Track usage
        try:
            # Attempt to get usage metadata
            usage = response.usage_metadata
            if usage:
                total_tokens = usage.total_token_count
                self.token_bucket.add_usage(total_tokens)
            else:
                # Fallback estimation
                output_len = len(response.text) // 3
                self.token_bucket.add_usage(estimated_input + output_len)
        except Exception:
            # If accessing usage fails, just estimate
            output_len = len(response.text) // 3
            self.token_bucket.add_usage(estimated_input + output_len)

        return response.text

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=5),
        reraise=True,
    )
    async def embed_async(self, text: str) -> list[float]:
        """
        Generate embeddings using text-embedding-004 (768 dimensions).
        """
        try:
            response = await self.client.aio.models.embed_content(
                model="text-embedding-004",
                contents=text,
            )
            return response.embeddings[0].values
        except Exception as e:
            print(f"Embedding failed: {e}")
            return []
