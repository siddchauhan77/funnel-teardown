# FunnelTeardown AI — Progress Log

> **For future sessions:** Read this file first. It tells you exactly where the project is, what's been built, what's open, and what's coming next.

---

## Current Checkpoint

**Status:** v1 complete. All code written, tests passing, pushed to GitHub.
**Blocked on:** Railway deployment (requires browser login — see Open Tasks).
**Last worked on:** 2026-04-05

---

## What's Been Built (v1)

### Foundation
- [x] Project scaffold — Python 3.11+, Pydantic v2, all directories, `.env.example`, `.gitignore`
- [x] Pydantic data models — `FunnelMap`, `Brand`, `Touchpoint`, `JourneyStep`, `Offer`, `RunMetadata`, `AwarenessLevel` enum (7 Schwartz levels)
- [x] `CostTracker` — per-agent token tracking, USD cost per model, total cost summary
- [x] `TeardownState` — wraps `FunnelMap` + hints, read/write JSON cache to `.tmp/` so any single agent can be re-run in isolation

### Agents
- [x] **Agent 1 — Brand Resolver** (`agents/brand_resolver.py`) — OpenAI `gpt-4o-mini-search-preview` with built-in web search. Takes brand name + optional hints → resolves official name, website, founder, ICP. Raises `ValueError` if brand is ambiguous (e.g. "Apple" = multiple companies).
- [x] **Agent 2 — Touchpoint Mapper** (`agents/touchpoint_mapper.py`) — OpenAI web search + `httpx` homepage scraping. Discovers all public channels (YouTube, LinkedIn, newsletter, podcast, etc.) + scrapes `<meta name="theme-color">` and `og:image` for brand color theming.
- [x] **Agent 3 — Journey Mapper** (`agents/journey_mapper.py`) — `claude-sonnet-4-6`. Full Schwartz 7-level funnel mapping: journey steps, offers, What's Working / What's Missing (Bustamante-style), open questions.

### Report & CLI
- [x] **HTML Renderer** (`report/html_renderer.py`) — Pure Python, no LLM. `FunnelMap` → standalone HTML with Mermaid.js flowchart, awareness coverage grid, step analysis cards, offers table, dark/light mode toggle, brand accent color pulled from homepage.
- [x] **CLI entry point** (`teardown.py`) — `python3 teardown.py "Brand Name" [--url site.com] [--founder Name] [--from-cache] [--agent N]`. Rich terminal output. Saves `output/<slug>_<timestamp>/funnel_map.json` + `teardown_report.html`.

### Web App
- [x] **FastAPI backend** (`web/app.py`) — `/analyze` endpoint streams real-time agent progress via Server-Sent Events (SSE). `/report/{id}` serves the generated HTML report. In-memory UUID-keyed report store.
- [x] **SPA frontend** (`web/index.html`) — 4 view states (home → running → report → error). Live progress cards per agent with shimmer animations. Light/dark mode toggle with `localStorage` persistence.
- [x] **Railway config** — `Procfile` + `railway.toml` (nixpacks, health check, restart on failure). Railway chosen over Vercel because the 30–60s pipeline exceeds Vercel's 10s serverless timeout.

### Tests & Docs
- [x] Full test suite — ~30 tests across models, cost tracker, state, all 3 agents (mocked), HTML renderer, CLI integration
- [x] `README.md` — full tutorial: install, setup, CLI usage, all flags, report walkthrough, cost reference
- [x] Demo report — `demo/ag1-teardown.html` (AG1 mock data, rendered with real renderer)

---

## Open Tasks — Things Sidd Needs To Do

These require interactive steps (browser, account access) that can't be scripted:

- [ ] **Deploy to Railway**
  1. `~/bin/railway login` (opens browser)
  2. `cd ~/funnel-teardown && ~/bin/railway init` (creates Railway project, link to GitHub repo)
  3. `~/bin/railway variables set OPENAI_API_KEY=sk-...`
  4. `~/bin/railway variables set ANTHROPIC_API_KEY=sk-ant-...`
  5. `~/bin/railway up` — deploys, gives you a live URL
  6. Test with: enter `AG1` + `ag1.com` in the form

- [ ] **Run a live smoke test** — try it on Justin Welsh (`justinwelsh.me`), Athletic Greens (`ag1.com`), or Alex Hormozi. Verify report quality, cost < $0.50, Mermaid renders.

- [ ] **Share with friends** — share the Railway URL. Repo is currently private so only you can see the code.

- [ ] **When ready to open-source** — change GitHub repo visibility to Public. `LICENSE` (MIT) is already in the repo.

---

## Future Roadmap (v2+)

These are planned but not started. Prioritized roughly:

### v2 — Auth & Monetization
- [ ] **Supabase auth** — sign in with Google/email, user accounts. `runs` table stores `FunnelMap` JSON, user_id, cost_usd, timestamp. Each user sees their run history.
- [ ] **Credit-based billing (Stripe)** — buy credit packs (e.g. 10 credits = $9). Each teardown = 1 credit. Free tier = 3 lifetime runs. Stripe Checkout + webhook to top up balance.
- [ ] **Feature gate** — analyze endpoint checks `credits > 0` before running pipeline. Unauthenticated users see a sign-in wall after their free runs.

### v2.5 — Subscription Tiers
- [ ] **Tier system** (after validating credit model):
  - Free: 3 runs lifetime
  - Starter: $19 / 20 credits (~$0.95/run, ~4× margin)
  - Pro: $49 / 75 credits + PDF export + saved report library
  - Agency: $149/mo unlimited + team seats + white-label export

### v3 — Quality & Features
- [ ] **PDF export** — `weasyprint` or `puppeteer` server-side render of the HTML report
- [ ] **Saved report library** — browse past teardowns, re-run with updated data
- [ ] **Compare mode** — two brands side by side (gap analysis)
- [ ] **Email digest** — weekly re-run of saved brands, "what changed" diff
- [ ] **Webhook / Zapier integration** — trigger teardown from n8n/Make/Zapier, receive JSON

### Open Source (when ready)
- [ ] Make GitHub repo public
- [ ] MIT license already added (`LICENSE`)
- [ ] Write a proper `CONTRIBUTING.md`
- [ ] Post on Twitter/LinkedIn to drive stars + community

---

## Cost Reference

| Agent | Model | Typical cost |
|-------|-------|-------------|
| Brand Resolver | `gpt-4o-mini-search-preview` | ~$0.01–0.03 |
| Touchpoint Mapper | `gpt-4o-mini-search-preview` | ~$0.02–0.05 |
| Journey Mapper | `claude-sonnet-4-6` | ~$0.10–0.20 |
| **Total per run** | — | **~$0.15–0.35** |

---

## Architecture Snapshot

```
teardown.py (CLI)          web/app.py (FastAPI + SSE)
      │                           │
      ▼                           ▼
TeardownState (.tmp/ cache) ◄─────┘
      │
      ├── agents/brand_resolver.py    → OpenAI gpt-4o-mini-search-preview
      ├── agents/touchpoint_mapper.py → OpenAI web search + httpx scraping
      └── agents/journey_mapper.py    → Anthropic claude-sonnet-4-6
                                              │
                                              ▼
                                    report/html_renderer.py
                                    output/<slug>/teardown_report.html
```

---

## Key Files

| File | What it does |
|------|-------------|
| `teardown.py` | CLI entry point |
| `web/app.py` | FastAPI web server + SSE |
| `web/index.html` | SPA frontend |
| `agents/brand_resolver.py` | Agent 1 |
| `agents/touchpoint_mapper.py` | Agent 2 |
| `agents/journey_mapper.py` | Agent 3 |
| `report/html_renderer.py` | Pure-Python report generator |
| `models/funnel_map.py` | All Pydantic models |
| `state/teardown_state.py` | State + cache |
| `utils/cost_tracker.py` | Token cost accounting |
| `demo/ag1-teardown.html` | Static demo report |
| `README.md` | User-facing tutorial |
