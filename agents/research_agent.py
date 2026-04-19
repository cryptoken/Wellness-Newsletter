"""
Research Agent — Deterministic trend discovery + agentic scrape/synthesize:

    Phase 1 (code):  pytrends ranks practice services by real interest scores,
                     picks the winning topic and pulls its related queries.
    Phase 2 (agent): LLM scrapes the winning topic via Firecrawl and synthesizes
                     a structured research brief grounded in both signals.

Input:  Brand voice config (practice details, audience, services)
Output: Structured research brief grounded in real-time data
"""

import json
import os
import re
import requests
from anthropic import Anthropic
from pytrends_modern import TrendReq

# ── Tool Definitions (Claude tool_use format) ─────────────────────────

TOOLS = [
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

SYSTEM_PROMPT = """You are a wellness content research specialist. Google Trends has already
been queried for you; the winning topic and its related queries are in the user message.
Your job: scrape real articles on that topic with firecrawl_search and synthesize a brief.

YOUR RESEARCH PROCESS:
1. Use firecrawl_search 2-3 times on the WINNING TOPIC provided — do not pivot to a different topic.
2. Vary queries to surface distinct angles (mechanism, latest research, patient-facing explainers).
3. Synthesize everything into a research brief grounded in the scraped sources and trend signals.

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
- ALWAYS call firecrawl_search before generating the brief — do not rely on training data alone
- Stay on the WINNING TOPIC from the trends step; do not switch topics
- SEO keywords MUST be drawn from the related_queries the trends step produced
- The angle should differentiate from what competitors are already publishing
- Tips must be actionable TODAY — not vague advice
- Output ONLY the JSON object after you've completed your tool calls"""


# ── Tool Execution Functions ──────────────────────────────────────────

def execute_google_trends(keywords: list, timeframe: str = "today 3-m", geo: str = "US") -> dict:
    """
    Query Google Trends via pytrends-modern (free, no API key).
    Google caps build_payload at 5 keywords per call.
    """
    try:
        pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
        pytrends.build_payload(keywords[:5], timeframe=timeframe, geo=geo)

        interest = pytrends.interest_over_time()
        related = pytrends.related_queries()

        related_summary = {}
        for kw in keywords[:5]:
            kw_data = related.get(kw, {}) or {}
            top = kw_data.get("top")
            rising = kw_data.get("rising")
            related_summary[kw] = {
                "top": top.head(10).to_dict(orient="records") if top is not None else [],
                "rising": rising.head(10).to_dict(orient="records") if rising is not None else [],
            }

        return {
            "keywords": keywords[:5],
            "timeframe": timeframe,
            "geo": geo,
            "interest_over_time": interest.to_dict(orient="list") if not interest.empty else {},
            "related_queries": related_summary,
        }
    except Exception as e:
        return {"error": str(e), "keywords": keywords, "fallback": True}


def compact_firecrawl_result(result: dict, max_chars: int = 4000) -> dict:
    markdown = result.get("markdown", "")
    metadata = result.get("metadata", {})

    # Strip nav/footer boilerplate Firecrawl sometimes leaves in
    lines = [l for l in markdown.split("\n") if l.strip()]

    if len(markdown) <= max_chars:
        body = markdown
    else:
        # Take first 60% and last 20% — headline/intro + conclusion matter most
        head_chars = int(max_chars * 0.6)
        tail_chars = int(max_chars * 0.2)
        body = markdown[:head_chars] + "\n\n[... middle truncated ...]\n\n" + markdown[-tail_chars:]

    return {
        "url": metadata.get("sourceURL", result.get("url", "")),
        "title": metadata.get("title", ""),
        "description": metadata.get("description", ""),
        "content": body,
        "original_length": len(markdown),
        "truncated": len(markdown) > max_chars,
    }


def execute_firecrawl_search(query: str, num_results: int = 3) -> dict:
    """
    Search and scrape web content via Firecrawl API.
    Results are compacted (markdown truncated) before returning to the LLM
    to stay within input-token budgets.
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
                payload = response.json()
                raw_items = payload.get("data", []) if isinstance(payload, dict) else []
                return {
                    "query": query,
                    "num_results": len(raw_items),
                    "results": [compact_firecrawl_result(item) for item in raw_items],
                }
            return {"error": f"firecrawl returned {response.status_code}", "query": query, "fallback": True}
        except Exception as e:
            return {"error": str(e), "query": query, "fallback": True}

    # Fallback
    return {
        "note": "Firecrawl API not configured — agent will use training knowledge",
        "query": query,
        "fallback": True,
    }


TOOL_DISPATCH = {
    "firecrawl_search": lambda input: execute_firecrawl_search(**input),
}


# ── Deterministic Trend Discovery ─────────────────────────────────────

def _normalize_service(service: str) -> str:
    """Strip parentheticals, lowercase, collapse whitespace. 'Peptide Therapy (BPC-157)' -> 'peptide therapy'."""
    cleaned = re.sub(r"\([^)]*\)", "", service)
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def discover_trending_topic(services: list, timeframe: str = "today 3-m", geo: str = "US") -> dict:
    """
    Rank service keywords by mean Google Trends interest and return the winner.

    Returns a dict with: winner, ranking, related_queries_top, related_queries_rising,
    timeframe, geo. Interest scores are within-batch relative (0-100 per pytrends).
    """
    keywords = [_normalize_service(s) for s in services if s][:5]
    if not keywords:
        return {"error": "no keywords to rank", "fallback": True}

    trends = execute_google_trends(keywords, timeframe=timeframe, geo=geo)
    if trends.get("fallback") or trends.get("error"):
        return {"error": trends.get("error", "trends unavailable"), "fallback": True, "keywords": keywords}

    interest = trends.get("interest_over_time", {})
    ranking = []
    for kw in keywords:
        series = [v for v in interest.get(kw, []) if isinstance(v, (int, float))]
        mean_score = sum(series) / len(series) if series else 0.0
        ranking.append({"keyword": kw, "mean_interest": round(mean_score, 2)})
    ranking.sort(key=lambda r: r["mean_interest"], reverse=True)

    winner = ranking[0]["keyword"]
    winner_related = trends.get("related_queries", {}).get(winner, {})

    return {
        "winner": winner,
        "ranking": ranking,
        "related_queries_top": winner_related.get("top", []),
        "related_queries_rising": winner_related.get("rising", []),
        "timeframe": timeframe,
        "geo": geo,
    }


# ── Research Agent Class ──────────────────────────────────────────────

class ResearchAgent:
    """
    Two-phase research pipeline:
    Phase 1 (code): pytrends ranks practice services, picks the winning topic.
    Phase 2 (agent): Firecrawl scrapes articles on the winner, agent synthesizes the brief.
    """

    def __init__(self, client: Anthropic, model: str = "claude-sonnet-4-20250514"):
        self.client = client
        self.model = model
        self.name = "Research Agent"

    def run(self, brand_config: dict, month: str = None, custom_topic: str = None) -> dict:
        """
        Run the two-phase research pipeline.

        Args:
            brand_config: The full brand voice configuration dict
            month: Optional month override (e.g., "January 2026")
            custom_topic: Optional user override — skips trend discovery

        Returns:
            Structured research brief as a dict
        """
        practice = brand_config.get("practice", {})
        voice = brand_config.get("voice", {})
        services = practice.get("services", [])

        # ── Phase 1: deterministic trend discovery ───────────────────
        if custom_topic:
            print(f"    * topic override: {custom_topic!r} (skipping trend discovery)")
            trend_context = {
                "winner": custom_topic,
                "ranking": [],
                "related_queries_top": [],
                "related_queries_rising": [],
                "source": "user_override",
            }
        else:
            trend_context = discover_trending_topic(services)
            if trend_context.get("fallback"):
                print(f"    ! trend discovery fallback: {trend_context.get('error')}")
            else:
                print(f"    * winning topic: {trend_context['winner']!r} "
                      f"(mean interest {trend_context['ranking'][0]['mean_interest']})")

        winner = trend_context["winner"]
        related_top = trend_context.get("related_queries_top", [])[:10]
        related_rising = trend_context.get("related_queries_rising", [])[:10]

        user_message = f"""Generate a research brief for this wellness practice's monthly newsletter.
Scrape real articles with firecrawl_search before writing the brief.

PRACTICE DETAILS:
- Name: {practice.get('name', 'N/A')}
- Type: {practice.get('type', 'N/A')}
- Services: {', '.join(services)}
- Target Audience: {practice.get('audience', 'N/A')}
- Location: {practice.get('location', 'N/A')}

VOICE GUIDELINES:
- Tone: {', '.join(voice.get('tone', []))}
- Personality: {voice.get('personality', 'N/A')}

MONTH: {month or 'Current month'}

WINNING TOPIC (from Google Trends — do not change): {winner}

RANKING (practice services by mean Google Trends interest):
{json.dumps(trend_context.get('ranking', []), indent=2)}

RELATED QUERIES — TOP (use these for SEO keywords):
{json.dumps(related_top, indent=2)}

RELATED QUERIES — RISING (fresh angles worth scraping):
{json.dumps(related_rising, indent=2)}

Start by calling firecrawl_search on the WINNING TOPIC."""

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
                        brief = self._parse_json(block.text)
                        brief["trend_discovery"] = trend_context
                        return brief

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
