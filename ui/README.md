# Newsletter Pipeline Dashboard

FastAPI + React monitoring dashboard for the newsletter pipeline. Same-origin — no CORS, no build step, one HTML file + one server file.

## Run

```bash
# from project root
pip install -r requirements.txt
python -m uvicorn ui.server:app --reload --port 8000
```

Open http://127.0.0.1:8000 in the browser.

## What it shows

All data is real — pulled from `examples/output/pipeline_results_*.json` and `data/run_history.db`.

- **Terminal tab** — live SSE stream of `pipeline_log` events when you click Run Now. Each event (tool calls, LLM calls, topic discovery, phase status) becomes a colored line.
- **Past Runs** — list of historical runs with subject, score, sources, expandable trend_discovery detail.
- **Sources** — every domain scraped across all runs, aggregated by count + topics.
- **Agents** — the three real agents (Research / Writer / Editor) with role, model, tools, pipeline position.
- **Settings** — practice configs + per-practice topic memory (last 50 covered topics, newest highlighted).
- **Sidebar** — config picker, Run Now button, aggregated stats, source health %.

## API

| Endpoint | Purpose |
|---|---|
| `GET  /api/runs` | list past runs (from JSON files) |
| `GET  /api/runs/{id}` | run detail (in-memory if active, disk otherwise) |
| `GET  /api/runs/stream/{id}` | SSE stream of pipeline_log events for an active run |
| `POST /api/runs` | start a new run; body `{config, topic?}` |
| `GET  /api/agents` | agent definitions (Research/Writer/Editor) |
| `GET  /api/configs` | practice YAML configs |
| `GET  /api/stats` | aggregate counts across runs |
| `GET  /api/sources` | top scraped domains |
| `GET  /api/source-health` | health % for top domains |
| `GET  /api/history/{slug}` | topic memory for a practice |

## Architecture

```
Browser                     FastAPI                  Pipeline
  │                           │                         │
  │  POST /api/runs ─────────►│                         │
  │                           │ spawn thread ─────────► │
  │                           │                         │ orchestrator.run()
  │                           │                         │  ├─ pytrends
  │                           │                         │  ├─ firecrawl × 3
  │◄── EventSource ──────────►│                         │  ├─ LLM research
  │    /api/runs/stream/{id}  │ poll orch.pipeline_log  │  ├─ LLM writer
  │                           │ stream new events       │  ├─ LLM editor
  │                           │                         │  └─ render html
  │                           │◄──── status=complete ───┤
  │◄── data: {type:"done"} ───┤                         │
```

The orchestrator is instantiated per-run and kept in `RUNS[run_id]`. SSE polls `orchestrator.pipeline_log` every 350ms and streams newly-appended events.
