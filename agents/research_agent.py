"""
Research Agent — Two-phase research pipeline using tool use:

    Phase 1: Google Trends → Discover what wellness topics are trending RIGHT NOW
    Phase 2: Firecrawl    → Scrape top articles on trending topics for real content angles

The agent autonomously decides what to search and what to scrape,
then synthesizes everything into a structured research brief.

Input:  Brand voice config (practice details, audience, services)
Output: Structured research brief grounded in real-time data
"""

import json
import os
import requests
from anthropic import Anthropic

# ── Tool Definitions (Claude tool_use format) ─────────────────────────

TOOLS = [
    {
        "name": "google_trends",
        "description": (
            "Search Google Trends for current interest in wellness and health topics. "
            "Returns trending searches and relative interest data. Use this FIRST to "
            "discover what people are actually searching for right now."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of 3-5 wellness keywords to check trends for",
                },
                "timeframe": {
                    "type": "string",
                    "description": "Timeframe for trends (e.g., 'today 3-m' for last 3 months)",
                    "default": "today 3-m",
                },
                "geo": {
                    "type": "string",
                    "description": "Geographic region (e.g., 'US')",
                    "default": "US",
                },
            },
            "required": ["keywords"],
        },
    },
    {
        "name": "firecrawl_search",
        "description": (
            "Search the web and scrape content from top results using Firecrawl. "
            "Use this AFTER Google Trends to get detailed content from the top articles "
            "on trending topics. Returns extracted text from web pages."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query to find relevant wellness articles",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to scrape (1-5)",
                    "default": 3,
                },
            },
            "required": ["query"],
        },
    },
]

SYSTEM_PROMPT = """You are a wellness content research specialist with access to real-time
research tools. Your job is to generate a data-driven research brief for a monthly newsletter.

You have two tools available:
1. google_trends — Check what wellness topics are trending right now
2. firecrawl_search — Scrape top articles on trending topics for content angles

YOUR RESEARCH PROCESS (follow this order):
1. FIRST, use google_trends to check interest in topics related to the practice's services
2. ANALYZE the trends data to identify the most promising topic
3. THEN, use firecrawl_search to scrape 2-3 top articles on that topic
4. SYNTHESIZE everything into a research brief

After completing your research, output a JSON object with this exact structure:
{
    "month_theme": "The overarching theme for this month's newsletter",
    "trends_data": {
        "top_trending": "The highest-trending topic found",
        "search_volume_signal": "high/medium/low",
        "related_searches": ["related terms people are searching"]
    },
    "sources_consulted": [
        {"url": "article URL", "key_insight": "What we learned from this source"}
    ],
    "hero_topic": {
        "title": "The main article topic",
        "angle": "The specific angle or hook — grounded in trends data and competitor content",
        "key_points": ["3-5 key points to cover"],
        "seo_keywords": ["5-8 keywords pulled from actual trending searches"]
    },
    "quick_tips": [
        {"tip": "Actionable tip text", "why": "Brief reason this matters"},
        {"tip": "Actionable tip text", "why": "Brief reason this matters"},
        {"tip": "Actionable tip text", "why": "Brief reason this matters"}
    ],
    "myth_buster": {
        "myth": "The common misconception",
        "reality": "The evidence-based truth",
        "source_hint": "What type of evidence supports this"
    },
    "practice_spotlight_suggestion": "A suggested practice update angle that ties to the theme",
    "cta_suggestion": "A suggested call to action that ties to the hero topic"
}

Guidelines:
- ALWAYS use your tools before generating the brief — don't rely on training data alone
- SEO keywords should come from actual Google Trends data
- The angle should differentiate from what competitors are already publishing
- Tips must be actionable TODAY — not vague advice
- Output ONLY the JSON object after you've completed your tool calls"""


# ── Tool Execution Functions ──────────────────────────────────────────

def execute_google_trends(keywords: list, timeframe: str = "today 3-m", geo: str = "US") -> dict:
    """
    Query Google Trends via SerpAPI (or similar).
    Falls back to a structured placeholder if no API key is configured.
    """
    api_key = os.environ.get("SERPAPI_API_KEY")

    if api_key:
        try:
            response = requests.get(
                "https://serpapi.com/search.json",
                params={
                    "engine": "google_trends",
                    "q": ",".join(keywords),
                    "date": timeframe,
                    "geo": geo,
                    "api_key": api_key,
                },
                timeout=15,
            )
            if response.ok:
                return response.json()
        except Exception as e:
            return {"error": str(e), "fallback": True}

    # Fallback: return structure so the agent can still reason
    return {
        "note": "Google Trends API not configured — using keyword analysis mode",
        "keywords_analyzed": keywords,
        "suggestion": "Proceed with Firecrawl to research these topics directly",
        "fallback": True,
    }


def execute_firecrawl_search(query: str, num_results: int = 3) -> dict:
    """
    Search and scrape web content via Firecrawl API.
    Falls back to a structured placeholder if no API key is configured.
    """
    api_key = os.environ.get("FIRECRAWL_API_KEY")

    if api_key:
        try:
            response = requests.post(
                "https://api.firecrawl.dev/v1/search",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "query": query,
                    "limit": num_results,
                    "scrapeOptions": {
                        "formats": ["markdown"],
                        "onlyMainContent": True,
                    },
                },
                timeout=30,
            )
            if response.ok:
                return response.json()
        except Exception as e:
            return {"error": str(e), "fallback": True}

    # Fallback
    return {
        "note": "Firecrawl API not configured — agent will use training knowledge",
        "query": query,
        "fallback": True,
    }


TOOL_DISPATCH = {
    "google_trends": lambda input: execute_google_trends(**input),
    "firecrawl_search": lambda input: execute_firecrawl_search(**input),
}


# ── Research Agent Class ──────────────────────────────────────────────

class ResearchAgent:
    """
    Two-phase research agent with tool use:
    Phase 1: Google Trends (discover what's trending)
    Phase 2: Firecrawl (deep-dive on trending topics)
    Then: Synthesize into structured research brief
    """

    def __init__(self, client: Anthropic, model: str = "claude-sonnet-4-20250514"):
        self.client = client
        self.model = model
        self.name = "Research Agent"

    def run(self, brand_config: dict, month: str = None, custom_topic: str = None) -> dict:
        """
        Run the two-phase research pipeline with tool use.

        Args:
            brand_config: The full brand voice configuration dict
            month: Optional month override (e.g., "January 2026")
            custom_topic: Optional user-specified topic to build around

        Returns:
            Structured research brief as a dict
        """
        practice = brand_config.get("practice", {})
        voice = brand_config.get("voice", {})

        user_message = f"""Generate a research brief for this wellness practice's monthly newsletter.
Use your tools to research before writing the brief.

PRACTICE DETAILS:
- Name: {practice.get('name', 'N/A')}
- Type: {practice.get('type', 'N/A')}
- Services: {', '.join(practice.get('services', []))}
- Target Audience: {practice.get('audience', 'N/A')}
- Location: {practice.get('location', 'N/A')}

VOICE GUIDELINES:
- Tone: {', '.join(voice.get('tone', []))}
- Personality: {voice.get('personality', 'N/A')}

MONTH: {month or 'Current month'}
{"REQUESTED TOPIC: " + custom_topic if custom_topic else "Use Google Trends to find the most timely topic, then research it with Firecrawl."}

Start by searching Google Trends for topics related to the practice's services."""

        messages = [{"role": "user", "content": user_message}]

        # Agentic tool-use loop
        max_iterations = 10
        for _ in range(max_iterations):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=3000,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )

            # Check if we're done (no more tool calls)
            if response.stop_reason == "end_turn":
                # Extract the final text response
                for block in response.content:
                    if hasattr(block, "text"):
                        return self._parse_json(block.text)

            # Process tool calls
            tool_results = []
            assistant_content = response.content

            for block in assistant_content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    tool_id = block.id

                    print(f"    → {tool_name}({json.dumps(tool_input, indent=None)[:80]}...)")

                    # Execute the tool
                    if tool_name in TOOL_DISPATCH:
                        result = TOOL_DISPATCH[tool_name](tool_input)
                    else:
                        result = {"error": f"Unknown tool: {tool_name}"}

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": json.dumps(result, default=str),
                    })

            # Add assistant message and tool results to conversation
            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})

        raise RuntimeError("Research Agent exceeded maximum tool-use iterations")

    def _parse_json(self, text: str) -> dict:
        """Extract and parse JSON from the agent's final response."""
        raw = text.strip()

        # Handle markdown code fences
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]

        # Try to find JSON object in the text
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            raw = raw[start:end]

        return json.loads(raw)
