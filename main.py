#!/usr/bin/env python3
"""
Wellness Newsletter Generator — Multi-Agent Pipeline
=====================================================

Usage:
    python main.py                          # Generate with auto-selected topic
    python main.py --month "May 2026"       # Specify month
    python main.py --topic "peptide therapy" # Force a specific topic
    python main.py --config path/to/config  # Use custom brand config

Requires:
    ANTHROPIC_API_KEY environment variable
    pip install anthropic pyyaml jinja2
"""

import argparse
import sys
import os
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
from dotenv import load_dotenv
from orchestrator import NewsletterOrchestrator

load_dotenv()


def run_pipeline(
    config: str = "config/vitality.yaml",
    topic: str | None = None,
    month: str | None = None,
    output_dir: str = "examples/output",
    model: str = "claude-sonnet-4-20250514",
) -> dict:
    """Callable entry point — runs the full pipeline and returns the results dict."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY environment variable not set.")
    if not os.path.exists(config):
        raise FileNotFoundError(f"Config file not found: {config}")

    orchestrator = NewsletterOrchestrator(config_path=config, model=model)
    return orchestrator.run(month=month, topic=topic, output_dir=output_dir)


def main():
    parser = argparse.ArgumentParser(
        description="Generate a wellness newsletter using a multi-agent pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py
  python main.py --month "May 2026" --topic "sleep optimization"
  python main.py --config config/vitality.yaml --output ./output
        """,
    )
    parser.add_argument("--month", type=str, default=None, help="Target month (e.g., 'May 2026')")
    parser.add_argument("--topic", type=str, default=None, help="Override topic (e.g., 'peptide therapy')")
    parser.add_argument("--config", type=str, default="config/vitality.yaml", help="Path to brand voice YAML config")
    parser.add_argument("--output", type=str, default="examples/output", help="Output directory for generated files")
    parser.add_argument("--model", type=str, default="claude-sonnet-4-20250514", help="Claude model to use")

    args = parser.parse_args()

    from theme import console
    try:
        results = run_pipeline(
            config=args.config,
            topic=args.topic,
            month=args.month,
            output_dir=args.output,
            model=args.model,
        )
        console.print(f"  [success]✓ Newsletter generated:[/success] [muted]{results['output_files']['html']}[/muted]")
    except Exception as e:
        console.print(f"\n  [error]✗ Pipeline failed:[/error] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
