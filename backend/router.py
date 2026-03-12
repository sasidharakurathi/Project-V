class AgentRouter:
    """
    Analyzes the transcribed user query and determines which
    Skill/Agent module should handle the execution.
    """

    def __init__(self):
        # We will load and mapping skills here
        pass

    def route_query(self, query: str) -> str:
        """
        Returns the ID of the skill meant to handle the query.
        For now, uses simple keyword matching.
        """
        query = query.lower()

        # Hardcoded semantic routing until we use an LLM router
        if any(
            kw in query
            for kw in ["open", "close", "window", "click", "desktop", "type"]
        ):
            return "os"
        elif any(kw in query for kw in ["search", "browser", "website", "http"]):
            return "web"
        elif any(kw in query for kw in ["extract", "read", "text from"]):
            return "data"
        elif any(kw in query for kw in ["email", "send", "message"]):
            return "comm"

        # Default fallback to general intelligence
        return "gemini_intelligence"
