# FunnelTeardown AI

**Reverse-engineer any brand's customer acquisition funnel using a multi-agent AI pipeline. Drop a brand name, get a full structured report in under 60 seconds for under $0.50.**

🔗 **[Try it live → funnelteardownai.up.railway.app](https://funnelteardownai.up.railway.app)**
&nbsp;&nbsp;|&nbsp;&nbsp;
📦 **[github.com/siddchauhan77/funnel-teardown](https://github.com/siddchauhan77/funnel-teardown)**

---

## The Problem

Marketers, founders, and growth teams spend hours manually researching competitor funnels — scrolling through social channels, clicking through landing pages, trying to piece together how a brand moves a stranger to a paying customer. The output is usually a messy Google Doc that goes stale in a week.

There's no tool that does this systematically, maps it to a framework, and flags what's working vs. what's missing — in minutes, not hours.

---

## What I Built

A three-agent AI pipeline that takes a brand name as input and returns:

- **Awareness Coverage Map** — which of Schwartz's 7 stages the brand actively reaches, and which are gaps
- **Funnel Journey Diagram** — Mermaid.js flowchart tracing the stranger → advocate pathway
- **Step-by-step analysis** — per-step What's Working / What's Missing in the style of Daniel Bustamante's FunnelBreakdowns newsletter
- **Offer stack** — every offer identified with price, type, and target awareness stage
- **Open questions** — honest epistemic flags on what couldn't be determined from public data alone

The whole thing runs as a **live web app** with real-time streaming progress (SSE), light/dark mode, and a full-screen report viewer. It also works as a CLI tool for developers.

**Cost per run: $0.15–0.35. Runtime: 30–60 seconds.**

---

## Architecture & Key Decisions

```
User Input (brand + website)
        │
        ▼
Agent 1: Brand Resolver          gpt-4o-mini-search-preview
  → official name, website,      OpenAI Responses API (built-in web search)
    founder, ICP, confidence
        │
        ▼
Agent 2: Touchpoint Mapper       gpt-4o-mini-search-preview + httpx
  → all public channels          web search + homepage scraping
    tagged by awareness level    extracts brand color + logo from meta tags
        │
        ▼
Agent 3: Journey Mapper          claude-sonnet-4-6
  → funnel steps, offers,        Anthropic SDK (reasoning-heavy task)
    what's working/missing,
    open questions
        │
        ▼
HTML Renderer                    Pure Python — no LLM, no cost
  → standalone report with       brand-colored, dark/light mode,
    Mermaid.js diagrams          self-contained HTML file
```

### Why three agents instead of one?

The tasks have different cost/quality profiles. Brand resolution and touchpoint discovery are lookup tasks — cheap GPT-4o-mini with web search handles them well at ~$0.01/call. Journey mapping is reasoning-heavy and benefits from Claude's longer context and analytical depth. Splitting them keeps the total run cost under $0.35 while maintaining quality where it matters.

Each agent writes to a shared `TeardownState` (Pydantic model) cached to `.tmp/` as JSON. Any single agent can be re-run in isolation without repeating the others — critical during development and useful when iterating on the journey mapping prompt without paying for web search again.

### Why Railway instead of Vercel?

The pipeline takes 30–60 seconds. Vercel's free tier kills serverless functions at 10 seconds. Railway runs a persistent Python process with no timeout ceiling. The `Procfile` + `railway.toml` config is already in the repo — one-command deploy.

### Why SSE instead of WebSockets?

Server-Sent Events are unidirectional (server → client), which is all that's needed for streaming agent progress. They work over standard HTTP with no protocol upgrade, no connection state to manage, and no library on the client side — just `fetch()` with a `ReadableStream` reader. Simpler, more reliable, good enough.

### Why Pydantic v2 for everything?

The `FunnelMap` model tree (`Brand`, `Touchpoint`, `JourneyStep`, `Offer`, `RunMetadata`) serves as the contract between all three agents, the renderer, and the CLI. Pydantic validates every LLM output at the boundary — if Claude returns a bad `awareness_level` string, it fails loudly at parse time rather than silently corrupting the report. It also makes JSON serialization and cache round-trips trivial.

---

## Technical Highlights

**Multi-agent orchestration** — sequential pipeline with shared typed state, per-agent cost tracking, and selective re-run capability (`--from-cache --agent N`)

**Real-time SSE streaming** — FastAPI background thread pushes agent progress events to the browser via a `queue.Queue`. The async event loop drains the queue without blocking, so the UI updates live as each agent completes

**Brand color theming** — Agent 2 scrapes `<meta name="theme-color">` and `og:image` from the brand homepage. The report renderer uses the extracted hex color as the CSS `--accent` variable, so each report feels visually native to the brand being analyzed

**Security** — all server data inserted into `innerHTML` is HTML-escaped through an `esc()` helper to prevent XSS. API keys live server-side only, never exposed to the client

**Test suite** — 42 tests across models, cost tracker, state cache, all three agents (fully mocked — no real API calls), HTML renderer, and CLI integration. Tests enforce the `response.output` iteration contract so any SDK change that breaks the parsing fails immediately

**Cost tracking** — `CostTracker` records input/output tokens per agent, computes USD cost using a model pricing table, and reports a full breakdown in the report footer and CLI output

---

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, uvicorn |
| AI — Agents 1 & 2 | OpenAI Responses API (`gpt-4o-mini-search-preview`) |
| AI — Agent 3 | Anthropic SDK (`claude-sonnet-4-6`) |
| Web scraping | httpx + BeautifulSoup4 |
| Data models | Pydantic v2 |
| Frontend | Vanilla JS SPA (no framework) |
| Diagrams | Mermaid.js |
| CLI output | Rich |
| Hosting | Railway (nixpacks) |
| Tests | pytest + pytest-mock |

---

## Running it yourself

**Prerequisites:** Python 3.9+, OpenAI API key, Anthropic API key

```bash
git clone https://github.com/siddchauhan77/funnel-teardown
cd funnel-teardown
pip3 install -r requirements.txt
```

Create a `.env` file:

```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

**Run a teardown:**

```bash
python3 teardown.py "Athletic Greens" --url ag1.com
python3 teardown.py "Justin Welsh" --url justinwelsh.me
python3 teardown.py "Alex Hormozi" --founder "Alex Hormozi"
```

**Run the web app locally:**

```bash
uvicorn web.app:app --host 0.0.0.0 --port 8000
# open http://localhost:8000
```

**Re-run a single agent (without paying for the others):**

```bash
python3 teardown.py "Justin Welsh" --from-cache --agent 3
```

**Run the tests:**

```bash
python3 -m pytest tests/ -v
# 42 passed, no API calls made
```

---

## Output

Each CLI run creates a timestamped folder in `output/`:

```
output/
  athletic_greens_20260405_143022/
    funnel_map.json       ← full structured data (FunnelMap Pydantic model)
    teardown_report.html  ← standalone HTML report, no server needed
```

---

## Awareness level framework

FunnelTeardown maps every touchpoint, journey step, and offer to Schwartz's 5 Levels of Awareness — extended to 7 to include post-purchase:

| Level | What it means |
|---|---|
| Unaware | Doesn't know the problem exists |
| Problem Aware | Knows the problem, not the solution |
| Solution Aware | Knows solutions exist, not this brand |
| Product Aware | Knows this brand, hasn't bought |
| Most Aware | Ready to buy, needs a nudge |
| Customer | Has purchased — retention phase |
| Advocate | Active referrer or community member |

The coverage map in the report shows which stages the brand actively reaches and which are gaps — a direct input for channel strategy decisions.

---

## Roadmap

See [`PROGRESS.md`](./PROGRESS.md) for the full checkpoint log and what's coming.

**v2 planned:** Supabase auth (user accounts + run history) + Stripe credit-based billing to offset API costs and capture margin. Free tier → credit packs → subscription tiers.

---

## License

MIT — use it, fork it, build on it.

---

*Built by [Sidd Chauhan](https://github.com/siddchauhan77)*
