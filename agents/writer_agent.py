"""
Writer Agent — Takes a research brief and brand voice config, produces
a complete newsletter draft in structured sections.

Input:  Research brief (from Research Agent) + brand voice config
Output: Structured newsletter content as a dict of sections
"""

import json
from anthropic import Anthropic

SYSTEM_PROMPT = """You are a wellness newsletter writer. You receive a research brief and
brand voice guidelines, and you write a complete newsletter draft.

Your writing must:
- Match the brand voice EXACTLY (tone, personality, do/don't rules)
- Stay within the word count target
- Be scannable — short paragraphs, clear headers, no walls of text
- Sound like a real person wrote it, not AI
- Educate first, promote second (and promote subtly)
- Use "you" and "your" — speak directly to the reader

Your output must be a JSON object with this exact structure:
{
    "subject_line": "Email subject line (compelling, not clickbait)",
    "preview_text": "The preview/preheader text (50-90 chars)",
    "hero_topic": {
        "headline": "Section headline",
        "body": "Full article text (~300 words). Use short paragraphs."
    },
    "quick_tips": {
        "headline": "3 Things You Can Do This Week",
        "tips": [
            {"title": "Short tip title", "body": "1-2 sentence explanation"},
            {"title": "Short tip title", "body": "1-2 sentence explanation"},
            {"title": "Short tip title", "body": "1-2 sentence explanation"}
        ]
    },
    "myth_buster": {
        "headline": "Myth vs. Reality",
        "myth": "The myth statement",
        "reality": "The truth, written conversationally"
    },
    "practice_spotlight": {
        "headline": "From the Practice",
        "body": "Brief practice update (2-3 sentences)"
    },
    "cta": {
        "headline": "Your Next Step",
        "body": "1-2 sentences leading to the action",
        "button_text": "CTA button text (3-5 words)"
    }
}

Output ONLY the JSON object, no other text."""


class WriterAgent:
    """Drafts newsletter content from a research brief and brand voice."""

    def __init__(self, client: Anthropic, model: str = "claude-sonnet-4-20250514"):
        self.client = client
        self.model = model
        self.name = "Writer Agent"

    def run(self, research_brief: dict, brand_config: dict, logger=None) -> dict:
        """
        Write the newsletter draft from research and brand config.

        Args:
            research_brief: Output from ResearchAgent
            brand_config: The full brand voice configuration dict

        Returns:
            Structured newsletter draft as a dict
        """
        voice = brand_config.get("voice", {})
        newsletter = brand_config.get("newsletter", {})
        practice = brand_config.get("practice", {})

        user_message = f"""Write a complete newsletter draft based on this research brief and brand voice.

RESEARCH BRIEF:
{json.dumps(research_brief, indent=2)}

BRAND VOICE:
- Practice: {practice.get('name', 'N/A')}
- Tone: {', '.join(voice.get('tone', []))}
- Personality: {voice.get('personality', 'N/A')}
- DO: {', '.join(voice.get('do', []))}
- DON'T: {', '.join(voice.get('dont', []))}

NEWSLETTER SPECS:
- Name: {newsletter.get('name', 'Newsletter')}
- Max words: {newsletter.get('style', {}).get('max_words', 800)}
- Reading time target: {newsletter.get('style', {}).get('reading_time_target', '3-4 minutes')}

Write the newsletter. Make it sound human. Return ONLY the JSON."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        if logger:
            usage = getattr(response, "usage", None)
            logger({
                "stage": "llm_call",
                "agent": self.name,
                "model": getattr(response, "model", self.model),
                "input_tokens": getattr(usage, "input_tokens", None) if usage else None,
                "output_tokens": getattr(usage, "output_tokens", None) if usage else None,
                "stop_reason": getattr(response, "stop_reason", None),
            })

        raw_text = response.content[0].text.strip()

        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1]
            raw_text = raw_text.rsplit("```", 1)[0]

        return json.loads(raw_text)
