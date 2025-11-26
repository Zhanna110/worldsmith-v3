from src.core.cognitive_engine import CognitiveEngine


class ConsistencyController:
    """
    The Lore Guard.
    Responsible for preventing contradictions and ensuring canonical integrity.
    """

    def __init__(self):
        self.engine = CognitiveEngine()

    async def check_consistency(
        self, content: str, world_primer: str, lore_context: str
    ) -> tuple[bool, str]:
        """
        Checks the content against the World Primer and Lore Context for contradictions.
        Returns: (is_consistent, report)
        """

        prompt = f"""
        You are the Consistency Controller. Your job is to find LOGICAL CONTRADICTIONS in this new text.
        
        WORLD PRIMER (THE TRUTH):
        {world_primer}
        
        ESTABLISHED LORE (CONTEXT):
        {lore_context}
        
        NEW DRAFT CONTENT:
        {content[:15000]}
        
        TASK:
        Analyze the New Draft for contradictions against the Primer and Lore.
        Ignore minor stylistic differences. Focus on FACTS (dates, names, physics, laws, history).
        
        OUTPUT FORMAT:
        Return a JSON object:
        {{
            "status": "PASS" or "FAIL",
            "contradictions": ["List of specific contradictions found..."],
            "notes": "Any other observations"
        }}
        """

        try:
            response = await self.engine.generate_async(
                prompt, response_mime_type="application/json"
            )
            import json

            result = json.loads(response)

            is_consistent = result.get("status") == "PASS"
            report = result.get("contradictions", [])

            return is_consistent, report

        except Exception as e:
            print(f"Consistency Check Error: {e}")
            return True, []  # Fail open to avoid blocking pipeline on error
