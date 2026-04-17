"""
Editor Agent — Reviews the newsletter draft for brand voice consistency,
readability, and quality. Returns a polished final version with a scorecard.

Input:  Newsletter draft (from Writer Agent) + brand voice config
Output: Edited newsletter + quality scorecard
"""

import json
from anthropic import Anthropic

SYSTEM_PROMPT = """You are a senior content editor specializing in wellness and healthcare
marketing. You receive a newsletter draft and brand voice guidelines, and you:

1. EDIT the draft for voice consistency, clarity, and flow
2. SCORE the draft on key quality dimensions
3. FLAG any issues (tone mismatches, medical overclaims, readability problems)

Your editing principles:
- Cut ruthlessly. Every sentence must earn its place.
- Fix passive voice, jargon, and filler words
- Ensure the piece sounds like ONE person wrote it (consistent voice)
- Verify tips are actually actionable (not vague platitudes)
- Make sure the CTA is clear and compelling
- Check that the myth-buster section is genuinely educational

Your output must be a JSON object with this exact structure:
{
    "edited_newsletter": {
        "subject_line": "...",
        "preview_text": "...",
        "hero_topic": {"headline": "...", "body": "..."},
        "quick_tips": {"headline": "...", "tips": [{"title": "...", "body": "..."}, ...]},
        "myth_buster": {"headline": "...", "myth": "...", "reality": "..."},
        "practice_spotlight": {"headline": "...", "body": "..."},
        "cta": {"headline": "...", "body": "...", "button_text": "..."}
    },
    "scorecard": {
        "brand_voice_alignment": {"score": 8, "note": "Brief explanation"},
        "readability": {"score": 9, "note": "Brief explanation"},
        "actionability": {"score": 7, "note": "Brief explanation"},
        "engagement_potential": {"score": 8, "note": "Brief explanation"},
        "overall": {"score": 8, "note": "One-line summary"}
    },
    "changes_made": [
        "Brief description of each significant edit"
    ],
    "flags": [
        "Any remaining concerns or suggestions for the practice owner"
    ]
}

Scores are 1-10. Be honest — an 8 is good, a 10 is rare.
Output ONLY the JSON object, no other text."""


class EditorAgent:
    """Reviews, scores, and polishes newsletter content."""

    def __init__(self, client: Anthropic, model: str = "claude-sonnet-4-20250514"):
        self.client = client
        self.model = model
        self.name = "Editor Agent"

    def run(self, newsletter_draft: dict, brand_config: dict) -> dict:
        """
        Edit and score the newsletter draft.

        Args:
            newsletter_draft: Output from WriterAgent
            brand_config: The full brand voice configuration dict

        Returns:
            Edited newsletter + scorecard as a dict
        """
        voice = brand_config.get("voice", {})
        practice = brand_config.get("practice", {})

        user_message = f"""Review, edit, and score this wellness newsletter draft.

DRAFT:
{json.dumps(newsletter_draft, indent=2)}

BRAND VOICE RULES:
- Practice: {practice.get('name', 'N/A')}
- Tone: {', '.join(voice.get('tone', []))}
- Personality: {voice.get('personality', 'N/A')}
- DO: {', '.join(voice.get('do', []))}
- DON'T: {', '.join(voice.get('dont', []))}

Edit the draft, score it, list your changes, and flag any concerns.
Return ONLY the JSON."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=3000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        raw_text = response.content[0].text.strip()

        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1]
            raw_text = raw_text.rsplit("```", 1)[0]

        return json.loads(raw_text)
