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


def main():
    parser = argparse.ArgumentParser(
        description="Generate a wellness newsletter using a multi-agent pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py
  python main.py --month "May 2026" --topic "sleep optimization"
  python main.py --config config/brand_voice.yaml --output ./output
        """,
    )
    parser.add_argument("--month", type=str, default=None, help="Target month (e.g., 'May 2026')")
    parser.add_argument("--topic", type=str, default=None, help="Override topic (e.g., 'peptide therapy')")
    parser.add_argument("--config", type=str, default="config/brand_voice.yaml", help="Path to brand voice YAML config")
    parser.add_argument("--output", type=str, default="examples/output", help="Output directory for generated files")
    parser.add_argument("--model", type=str, default="claude-sonnet-4-20250514", help="Claude model to use")

    args = parser.parse_args()

    # Validate API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n  x ANTHROPIC_API_KEY environment variable not set.")
        print("    export ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    # Validate config exists
    if not os.path.exists(args.config):
        print(f"\n  x Config file not found: {args.config}")
        sys.exit(1)

    # Run pipeline
    orchestrator = NewsletterOrchestrator(
        config_path=args.config,
        model=args.model,
    )

    try:
        results = orchestrator.run(
            month=args.month,
            topic=args.topic,
            output_dir=args.output,
        )
        print(f"  ✓ Newsletter generated: {results['output_files']['html']}")
    except Exception as e:
        print(f"\n  x Pipeline failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
