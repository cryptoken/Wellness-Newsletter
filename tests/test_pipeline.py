import os
import sys

# Make project root importable when pytest runs from anywhere
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import run_pipeline


def test_full_pipeline_produces_real_urls():
    """Acceptance test for Block 1 (portability) and ongoing regression check."""
    result = run_pipeline(config="config/vitality.yaml")
    sources = result["research_brief"]["sources_consulted"]
    assert len(sources) >= 3
    assert all(s["url"].startswith("http") for s in sources)


def test_topic_memory_excludes_recent():
    """Acceptance test for Block 3 (topic memory). Expected to FAIL until Block 3 is complete."""
    r1 = run_pipeline(config="config/vitality.yaml")
    r2 = run_pipeline(config="config/vitality.yaml")
    assert r1["topic"] != r2["topic"]
