"""
Newsletter Pipeline Orchestrator
=================================
Coordinates the multi-agent pipeline:

    Research Agent (Google Trends → Firecrawl → Brief)
         ↓
    Writer Agent (Research Brief → Newsletter Draft)
         ↓
    Editor Agent (Draft → Polished Newsletter + Scorecard)
         ↓
    HTML Renderer (Final Content → Email-Ready HTML)

Each agent runs independently with a clear input/output contract.
The orchestrator manages data flow, logging, and error handling.
"""

import json
import re
import yaml
import os
from datetime import datetime
from pathlib import Path
from anthropic import Anthropic
from jinja2 import Template

from agents import ResearchAgent, WriterAgent, EditorAgent
import history
from theme import console


class NewsletterOrchestrator:
    """Runs the full newsletter generation pipeline."""

    def __init__(self, config_path: str = "config/brand_voice.yaml", model: str = "claude-sonnet-4-20250514"):
        self.client = Anthropic()  # Uses ANTHROPIC_API_KEY env var
        self.model = model
        self.config = self._load_config(config_path)

        # Tiered models: Sonnet for research + drafting, Opus for review/scoring
        self.research_agent = ResearchAgent(self.client, model=self.model)
        self.writer_agent = WriterAgent(self.client, model=self.model)
        self.editor_agent = EditorAgent(self.client, model="claude-opus-4-7")

        # Pipeline state
        self.pipeline_log = []

    def _load_config(self, path: str) -> dict:
        """Load the brand voice YAML configuration."""
        with open(path, "r") as f:
            return yaml.safe_load(f)

    def _log(self, agent_name: str, status: str, detail: str = ""):
        """Log a status event (backwards-compatible)."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": agent_name,
            "status": status,
            "detail": detail,
        }
        self.pipeline_log.append(entry)
        style = "error" if status == "FAILED" else "muted"
        console.print(f"  [muted][[/muted]{agent_name}[muted]][/muted] [{style}]{status}[/{style}] [muted]{detail}[/muted]")

    def _log_event(self, event: dict):
        """Structured logging for tool calls, LLM calls, and topic discovery."""
        entry = {"timestamp": datetime.now().isoformat(), **event}
        self.pipeline_log.append(entry)

    def run(self, month: str = None, topic: str = None, output_dir: str = "examples/output") -> dict:
        """
        Run the full newsletter pipeline.

        Args:
            month: Target month (e.g., "May 2026"). Defaults to current month.
            topic: Optional user-specified topic override
            output_dir: Directory for output files

        Returns:
            Complete pipeline results including all intermediate outputs
        """
        if not month:
            month = datetime.now().strftime("%B %Y")

        console.rule(f"[stage]NEWSLETTER PIPELINE[/stage] [muted]—[/muted] [accent]{self.config['newsletter']['name']}[/accent] [muted]·[/muted] {month}")

        practice_name = self.config.get("practice", {}).get("name", "unknown")
        practice_slug = history.slugify(practice_name)
        results = {"month": month, "topic": topic, "practice_slug": practice_slug}

        # ── Phase 1: Research ──────────────────────────────────────
        console.print(f"\n[stage]🔍 Phase 1: Research[/stage] [muted]for {practice_name}[/muted]")
        self._log("Research Agent", "STARTED", f"Month: {month}, Topic: {topic or 'auto'}")
        try:
            excluded = history.recent_topics(practice_slug)
            last_seen = history.last_covered_at(practice_slug)
            if excluded:
                self._log("Research Agent", "MEMORY", f"Excluding {len(excluded)} recent topics: {excluded}")

            research_brief = self.research_agent.run(
                brand_config=self.config,
                month=month,
                custom_topic=topic,
                excluded_topics=excluded,
                last_seen=last_seen,
                logger=self._log_event,
            )
            results["research_brief"] = research_brief
            trend_disc = research_brief.get("trend_discovery", {})
            results["topic"] = trend_disc.get("winner") or topic
            self._log("Research Agent", "COMPLETED",
                      f"Theme: {research_brief.get('month_theme', 'N/A')} | "
                      f"Winner: {results['topic']} (rank {trend_disc.get('winner_rank')}, "
                      f"fallback={trend_disc.get('fallback_used', False)})")
        except Exception as e:
            self._log("Research Agent", "FAILED", str(e))
            raise

        # ── Phase 2: Write ─────────────────────────────────────────
        console.print("\n[stage]✍️  Phase 2: Write[/stage]")
        self._log("Writer Agent", "STARTED")
        try:
            newsletter_draft = self.writer_agent.run(
                research_brief=research_brief,
                brand_config=self.config,
                logger=self._log_event,
            )
            results["draft"] = newsletter_draft
            self._log("Writer Agent", "COMPLETED", f"Subject: {newsletter_draft.get('subject_line', 'N/A')}")
        except Exception as e:
            self._log("Writer Agent", "FAILED", str(e))
            raise

        # ── Phase 3: Edit ──────────────────────────────────────────
        console.print("\n[stage]📝 Phase 3: Edit[/stage]")
        self._log("Editor Agent", "STARTED")
        try:
            editor_output = self.editor_agent.run(
                newsletter_draft=newsletter_draft,
                brand_config=self.config,
                logger=self._log_event,
            )
            results["editor_output"] = editor_output
            scorecard = editor_output.get("scorecard", {})
            overall = scorecard.get("overall", {})
            self._log("Editor Agent", "COMPLETED", f"Score: {overall.get('score', 'N/A')}/10")
        except Exception as e:
            self._log("Editor Agent", "FAILED", str(e))
            raise

        # ── Phase 4: Render HTML ───────────────────────────────────
        console.print("\n[stage]📮 Phase 4: Render[/stage]")
        self._log("Renderer", "STARTED")
        try:
            html_output = self._render_html(editor_output["edited_newsletter"])
            results["html"] = html_output

            # Save outputs
            os.makedirs(output_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            html_path = os.path.join(output_dir, f"newsletter_{timestamp}.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_output)

            self._log("Renderer", "COMPLETED", f"Saved to {html_path}")

            # Record successful run for topic memory (so next run excludes this topic)
            trend_disc = results.get("research_brief", {}).get("trend_discovery", {})
            recorded_topic = trend_disc.get("winner") or results.get("topic")
            if recorded_topic:
                ranking = trend_disc.get("ranking", [])
                winner_rank = trend_disc.get("winner_rank") or 0
                mean_interest = ranking[winner_rank].get("mean_interest", 0.0) if ranking and winner_rank < len(ranking) else 0.0
                discovery_method = trend_disc.get("source", "pytrends")
                history.record_run(
                    practice_slug=practice_slug,
                    topic=recorded_topic,
                    discovery_method=discovery_method,
                    mean_interest=mean_interest,
                )
                self._log("History", "RECORDED", f"{practice_slug} / {recorded_topic} ({discovery_method})")

            results["output_files"] = {"html": html_path}
            results["pipeline_log"] = self.pipeline_log

            json_path = os.path.join(output_dir, f"pipeline_results_{timestamp}.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, default=str)
            results["output_files"]["json"] = json_path
        except Exception as e:
            self._log("Renderer", "FAILED", str(e))
            raise

        # ── Summary ────────────────────────────────────────────────
        console.rule("[success]PIPELINE COMPLETE[/success]")
        console.print(f"  [stage]Subject:[/stage] [accent]{editor_output['edited_newsletter'].get('subject_line', 'N/A')}[/accent]")
        console.print(f"  [stage]Overall Score:[/stage] [success]{overall.get('score', 'N/A')}/10[/success] [muted]{overall.get('note', '')}[/muted]")
        console.print(f"  [stage]Changes Made:[/stage] {len(editor_output.get('changes_made', []))}   [stage]Flags:[/stage] {len(editor_output.get('flags', []))}")
        console.print(f"  [stage]Output:[/stage] [muted]{html_path}[/muted]\n")

        return results

    def _render_html(self, newsletter: dict) -> str:
        """Render the final newsletter content as an HTML email."""
        practice = self.config.get("practice", {})
        newsletter_cfg = self.config.get("newsletter", {})
        practice_name = practice.get("name", "Wellness Practice")
        practice_location = practice.get("location", "")
        newsletter_name = newsletter_cfg.get("name", "Newsletter")

        template_path = newsletter_cfg.get("template")
        if template_path and os.path.exists(template_path):
            with open(template_path, "r", encoding="utf-8") as f:
                template = Template(f.read())
        else:
            template = Template(HTML_TEMPLATE)

        def split_paragraphs(text: str) -> list:
            if not text:
                return []
            return [p.strip() for p in text.replace("\r\n", "\n").split("\n\n") if p.strip()]

        hero_paragraphs = split_paragraphs(newsletter.get("hero_topic", {}).get("body", ""))
        spotlight_paragraphs = split_paragraphs(newsletter.get("practice_spotlight", {}).get("body", ""))

        now = datetime.now()
        issue_date = now.strftime("%A · %b %d, %Y")
        total_words = sum(len(p.split()) for p in hero_paragraphs + spotlight_paragraphs)
        total_words += sum(
            len((t.get("body") or "").split()) + len((t.get("title") or "").split())
            for t in newsletter.get("quick_tips", {}).get("tips", [])
        )
        read_time = max(1, round(total_words / 220))

        words = re.split(r"\s+", practice_name.strip())
        avatar_initials = "".join(w[0] for w in words[:2]).upper() or "VW"

        hero_topic_headline = newsletter.get("hero_topic", {}).get("headline", "")
        hero_eyebrow = newsletter_cfg.get("sections", [{}])[0].get("name", "This month").upper()

        return template.render(
            newsletter=newsletter,
            practice_name=practice_name,
            practice_location=practice_location,
            newsletter_name=newsletter_name,
            wordmark=newsletter_cfg.get("wordmark", newsletter_name),
            tagline=newsletter_cfg.get("tagline", ""),
            footer_tagline=newsletter_cfg.get("footer_tagline", ""),
            issue_number=newsletter_cfg.get("issue_number", now.strftime("%y.%m")),
            issue_date=issue_date,
            read_time=read_time,
            avatar_initials=avatar_initials,
            byline_subtitle=f"Reviewed by the {practice_name} clinical team",
            hero_eyebrow=f"This month · {hero_eyebrow}",
            hero_paragraphs=hero_paragraphs,
            spotlight_paragraphs=spotlight_paragraphs,
            year=now.year,
        )


# ── HTML Email Template ───────────────────────────────────────────────
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ newsletter.subject_line }}</title>
    <style>
        /* Reset */
        body, table, td, p, a, li { -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }
        body { margin: 0; padding: 0; width: 100% !important; }

        /* Base */
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background-color: #f4f4f0;
            color: #2d2d2d;
            line-height: 1.7;
        }

        .container {
            max-width: 620px;
            margin: 0 auto;
            background: #ffffff;
        }

        .header {
            background: linear-gradient(135deg, #1a5c3a 0%, #2d8a5e 100%);
            padding: 40px 32px;
            text-align: center;
        }

        .header h1 {
            color: #ffffff;
            font-size: 28px;
            font-weight: 700;
            margin: 0 0 4px 0;
            letter-spacing: -0.5px;
        }

        .header p {
            color: rgba(255,255,255,0.85);
            font-size: 14px;
            margin: 0;
        }

        .content {
            padding: 36px 32px;
        }

        .section {
            margin-bottom: 36px;
            padding-bottom: 36px;
            border-bottom: 1px solid #e8e8e4;
        }

        .section:last-child {
            border-bottom: none;
            margin-bottom: 0;
            padding-bottom: 0;
        }

        h2 {
            font-size: 22px;
            font-weight: 700;
            color: #1a5c3a;
            margin: 0 0 16px 0;
            letter-spacing: -0.3px;
        }

        h3 {
            font-size: 16px;
            font-weight: 600;
            color: #2d2d2d;
            margin: 0 0 6px 0;
        }

        p {
            font-size: 16px;
            margin: 0 0 14px 0;
            color: #3d3d3d;
        }

        .tip-card {
            background: #f8f9f6;
            border-left: 3px solid #2d8a5e;
            padding: 16px 20px;
            margin-bottom: 14px;
            border-radius: 0 6px 6px 0;
        }

        .tip-card h3 { color: #1a5c3a; margin-bottom: 4px; }
        .tip-card p { margin: 0; font-size: 15px; color: #4a4a4a; }

        .myth-box {
            background: #fef9f0;
            border: 1px solid #f0e0c0;
            border-radius: 8px;
            padding: 24px;
        }

        .myth-label {
            display: inline-block;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            padding: 3px 10px;
            border-radius: 3px;
            margin-bottom: 8px;
        }

        .myth-label.myth { background: #fde8e8; color: #c53030; }
        .myth-label.reality { background: #e6f7ee; color: #1a5c3a; }

        .cta-section {
            background: linear-gradient(135deg, #1a5c3a 0%, #2d8a5e 100%);
            border-radius: 10px;
            padding: 32px;
            text-align: center;
        }

        .cta-section h2 { color: #ffffff; }
        .cta-section p { color: rgba(255,255,255,0.9); }

        .cta-button {
            display: inline-block;
            background: #ffffff;
            color: #1a5c3a;
            font-size: 16px;
            font-weight: 600;
            padding: 14px 36px;
            border-radius: 6px;
            text-decoration: none;
            margin-top: 8px;
        }

        .footer {
            background: #f4f4f0;
            padding: 24px 32px;
            text-align: center;
            font-size: 13px;
            color: #888;
        }

        .footer a { color: #2d8a5e; text-decoration: none; }

        @media (max-width: 640px) {
            .header, .content, .footer { padding-left: 20px; padding-right: 20px; }
            h2 { font-size: 20px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>{{ newsletter_name }}</h1>
            <p>by {{ practice_name }}</p>
        </div>

        <div class="content">
            <!-- Hero Topic -->
            <div class="section">
                <h2>{{ newsletter.hero_topic.headline }}</h2>
                {% for paragraph in newsletter.hero_topic.body.split('\\n\\n') %}
                <p>{{ paragraph }}</p>
                {% endfor %}
            </div>

            <!-- Quick Tips -->
            <div class="section">
                <h2>{{ newsletter.quick_tips.headline }}</h2>
                {% for tip in newsletter.quick_tips.tips %}
                <div class="tip-card">
                    <h3>{{ tip.title }}</h3>
                    <p>{{ tip.body }}</p>
                </div>
                {% endfor %}
            </div>

            <!-- Myth Buster -->
            <div class="section">
                <h2>{{ newsletter.myth_buster.headline }}</h2>
                <div class="myth-box">
                    <div><span class="myth-label myth">Myth</span></div>
                    <p><em>"{{ newsletter.myth_buster.myth }}"</em></p>
                    <div style="margin-top: 16px;"><span class="myth-label reality">Reality</span></div>
                    <p>{{ newsletter.myth_buster.reality }}</p>
                </div>
            </div>

            <!-- Practice Spotlight -->
            <div class="section">
                <h2>{{ newsletter.practice_spotlight.headline }}</h2>
                <p>{{ newsletter.practice_spotlight.body }}</p>
            </div>

            <!-- CTA -->
            <div class="section">
                <div class="cta-section">
                    <h2>{{ newsletter.cta.headline }}</h2>
                    <p>{{ newsletter.cta.body }}</p>
                    <a href="#" class="cta-button">{{ newsletter.cta.button_text }}</a>
                </div>
            </div>
        </div>

        <!-- Footer -->
        <div class="footer">
            <p>&copy; {{ year }} {{ practice_name }} &middot; <a href="#">Unsubscribe</a> &middot; <a href="#">View in Browser</a></p>
        </div>
    </div>
</body>
</html>"""
