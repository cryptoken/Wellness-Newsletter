# Wellness Newsletter — Tasks

## Status

**V1 shipped 2026-04-17:**
- Code-side trend discovery from `brand_voice.yaml` services (pytrends-modern)
- Research Agent scrapes winning topic via Firecrawl (real URLs confirmed)
- Writer + Editor LLM stages produce newsletter + audit JSON + HTML
- Tier 2 Anthropic API unlocked
- Firecrawl results truncated (~4KB head+tail) to fix rate limits
- Tested on Vitality Wellness config only

**Deadline: Loom recorded by Sat 2026-04-19 EOD.**

---

## Active Blocks

### Block 1 — Portability proof (30 min) — HIGHEST PRIORITY

- [ ] Create second `brand_voice.yaml` (suggest: chiropractic practice or med spa — different services list)
- [ ] Run `python main.py --config config/[second_practice].yaml`
- [ ] Verify different trend winner picked
- [ ] Verify content is sensibly different (not just find/replace)
- [ ] Save both HTML outputs to `examples/output/` for the Loom

> If this doesn't work, everything else is premature.

### Block 2 — Audit trail hardening (30 min)

- [ ] Add tool-level logging to Research Agent loop — each Firecrawl call appends to `pipeline_log` with `{agent, tool, input_summary, output_bytes, timestamp}`
- [ ] Add model + token logging per agent — `{model: response.model, input_tokens, output_tokens, stop_reason}`
- [ ] Add topic discovery entry to `pipeline_log` — `{stage: "topic_discovery", candidates, winner, winner_rank, excluded_as_recent}`
- [ ] Re-run pipeline and confirm `pipeline_log` now has ~15+ entries instead of 8

### Block 3 — Topic memory feature (45 min)

- [ ] Create `history.py` with SQLite setup
- [ ] Implement `recent_topics(practice_slug, limit_runs=12, limit_days=90)` with hybrid exclusion window
- [ ] Implement `record_run(practice_slug, topic, discovery_method, mean_interest)` — call at end of successful pipeline run
- [ ] Modify `discover_trending_topic()` to filter excluded topics, fall back to oldest-first recycling if all services recently covered
- [ ] Add `excluded_as_recent`, `winner_rank`, `fallback_used` fields to `trend_discovery` output
- [ ] Test: run same practice twice — confirm second run picks different topic
- [ ] Test: run 6 times — confirm eventually recycles oldest topic without crashing

> Deferred to V2: sub-angle selection from related queries when all services exhausted.

### Block 4 — Documentation (15 min)

- [ ] Update README "How It Works" to reflect code-side discovery → agent-side research architecture
- [ ] Update README "Why Multi-Agent" to be defensible — soften "3 agents" to "research agent + 2 specialized LLM stages" OR commit to Writer-as-agent in v2 roadmap
- [ ] Add new section: "Topic Memory" — describes per-practice 12-run/90-day exclusion
- [ ] Remove or update aspirational claims (e.g., "researches what's actually trending" → "discovers trending topics from practice services, then researches the winner")

### Block 5 — Hygiene (10 min)

- [ ] Remove `google_trends` from `research_agent.py` TOOLS if still there
- [ ] Remove `requests` import if unused (SerpAPI fallback gone)
- [ ] Confirm `.env` is in `.gitignore`
- [ ] Create `.env.example` with key names but no values
- [ ] Add `data/` to `.gitignore` (for `run_history.db`)

### Block 6 — Demo prep (after Blocks 1–5 complete)

- [ ] Write Loom script/talking points (3–5 min: problem → live run → audit trail walkthrough → portability demo → close)
- [ ] Test OBS recording setup, audio levels
- [ ] Dry-run the demo once before recording
- [ ] Record Loom
- [ ] Upload to YouTube (unlisted) or Loom
- [ ] Draft one Upwork proposal using the Loom as the anchor

---

## Deferred to V2 (roadmap, do not build now)

- Writer-as-agent with `check_brand_voice_compliance`, `measure_readability`, `count_words` tools
- Editor-as-agent with `pubmed_search` and verification tools for medical claims
- Sub-angle topic discovery from `related_queries_rising` when services exhausted
- Multi-language / compliance / distribution agents (already in README — keep as roadmap)
- Tie-breaking on rising delta instead of mean interest
- pytrends failure fallback (cache last-known-good)

---

## Decisions log

- **2026-04-17** — Picked SQLite over JSON for run history (concurrent write safety, queryability, production-ready story)
- **2026-04-17** — Topic memory hybrid window: `max(12 runs, 90 days)` per practice
- **2026-04-17** — Reached Tier 2 Anthropic API (lifetime $40+ credits) for raised TPM/RPM
- **2026-04-17** — Firecrawl results truncated to ~4KB using head (60%) + tail (20%) pattern, preserves intro angle and conclusion
- **2026-04-17** — Trend discovery moved code-side (deterministic ranking against brand_voice.yaml services); agent only retains Firecrawl tool
- **2026-04-17** — Confirmed all three agents on Sonnet 4.6; Editor stays Sonnet (Opus premium not justified without verification tools)

---

## Resumption context (paste into next Claude Code session)

```
Wellness newsletter pipeline V1 shipped last session:
- Code-side trend discovery from brand_voice.yaml services (pytrends-modern)
- Research Agent scrapes winning topic via Firecrawl (real URLs confirmed)
- Writer + Editor LLM stages produce newsletter + audit JSON + HTML
- Tier 2 API unlocked, Firecrawl results truncated to fix rate limits
- Tested on Vitality Wellness config only

Read tasks.md. Start with Block 1.

Open: portability test, tool-level logging, topic memory with SQLite,
README update, Loom recording. Deadline: Loom by Sat 2026-04-19 EOD.
```

---

## Red flags to watch for next session

- Scope creep into Writer-as-agent tools ("while I'm here I'll add...")
- Opening new Claude Code session on a new feature before finishing Block 1
- Rebuilding working code because you want to "clean it up"
- Adding any feature not on this list without writing it down first

> Pattern from this week: ideation churn all week, broke out by shipping today. Don't restart the churn tomorrow by chasing the next shiny feature. Close V1 → record → proposal → Monday.
