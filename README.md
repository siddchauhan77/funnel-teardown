# FunnelTeardown AI

> Reverse-engineer any brand's funnel in minutes. Drop a brand name, get a full stranger-to-advocate map with Bustamante-style What's Working / What's Missing analysis.

**Live app:** [funnelteardownai.up.railway.app](https://funnelteardownai.up.railway.app)

---

## What it does

FunnelTeardown AI runs three sequential AI agents against any brand name, then generates a standalone HTML report showing:

- **Awareness Coverage Map** — which of Schwartz's 7 stages the brand actively reaches (gaps = opportunities)
- **Funnel Journey Diagram** — Mermaid.js flowchart from stranger → advocate
- **Step-by-step analysis** — What's Working / What's Missing for every funnel step
- **Offer stack** — every offer identified with price, type, and stage
- **Open questions** — honest flags on what couldn't be determined from public data

Total cost: under $0.50 per run.

---

## How it works

```
Brand name
    ↓
Agent 1: Brand Resolver     (gpt-4o-mini + web search)
    → brand name, website, founder, ICP, confidence
    ↓
Agent 2: Touchpoint Mapper  (gpt-4o-mini + web search + homepage scrape)
    → all public channels tagged by awareness level
    ↓
Agent 3: Journey Mapper     (claude-sonnet-4-6)
    → full funnel steps, offers, what's working/missing, open questions
    ↓
HTML Renderer               (pure Python, no LLM)
    → dark-mode report with Mermaid.js diagrams
```

Each agent writes to a shared `TeardownState` (Pydantic model) cached to `.tmp/`. Any agent can be re-run in isolation without repeating the others.

---

## Prerequisites

- Python 3.9+
- OpenAI API key (for Agents 1 & 2)
- Anthropic API key (for Agent 3)

---

## Installation

```bash
git clone https://github.com/siddchauhan77/funnel-teardown
cd funnel-teardown
pip3 install -r requirements.txt
```

---

## Setup

Copy the env template and add your keys:

```bash
cp .env.example .env
```

Edit `.env`:

```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Usage

### Basic teardown

```bash
python3 teardown.py "Athletic Greens"
```

### With disambiguation hints

If the brand name is ambiguous (e.g. "Apple"), pass hints:

```bash
python3 teardown.py "Justin Welsh" --url "justinwelsh.me"
python3 teardown.py "Alex Hormozi" --founder "Alex Hormozi"
```

### Re-run a single agent

Each agent's output is cached. Use `--from-cache` + `--agent N` to re-run just one step without paying for the others:

```bash
# Re-run only Agent 3 (journey mapping) using cached brand + touchpoints
python3 teardown.py "Justin Welsh" --from-cache --agent 3

# Re-run from Agent 2 onward
python3 teardown.py "Justin Welsh" --from-cache --agent 2
```

### All flags

```
python3 teardown.py "Brand Name"
  --founder "Founder Name"   Disambiguation hint (adds to Agent 1 prompt)
  --url "website.com"        Website hint (adds to Agent 1 prompt)
  --from-cache               Load .tmp/ cache instead of re-running Agent 1+2
  --agent N                  Start from agent N (1, 2, or 3). Use with --from-cache.
```

---

## Output

Each run creates a timestamped folder in `output/`:

```
output/
  athletic_greens_20260405_143022/
    funnel_map.json       ← full structured data (Pydantic FunnelMap)
    teardown_report.html  ← standalone dark-mode HTML report
```

Open `teardown_report.html` in any browser — no server needed, fully self-contained.

---

## Report sections

| Section | What you see |
|---|---|
| **Stats bar** | Touchpoint count, steps, offers, questions, total cost |
| **Brand Overview** | Name, website, founder, description, ICP, confidence |
| **Awareness Coverage Map** | Color-coded grid — which Schwartz stages are covered |
| **Funnel Journey Diagram** | Mermaid.js flowchart with awareness-level coloring |
| **Step Analysis** | Per-step What's Working / What's Missing cards |
| **Offers** | All offers with price, type, stage, confidence |
| **Open Questions** | What couldn't be determined from public data |
| **Run Details** | Agent → model → cost breakdown |

---

## Awareness levels

FunnelTeardown uses Schwartz's 5 Levels of Awareness extended to 7:

| Level | Color | What it means |
|---|---|---|
| Unaware | Gray | Doesn't know the problem exists |
| Problem Aware | Amber | Knows the problem, not the solution |
| Solution Aware | Blue | Knows solutions exist, not this brand |
| Product Aware | Purple | Knows this brand, hasn't bought |
| Most Aware | Green | Ready to buy, needs a reason |
| Customer | Dark green | Has purchased, retention phase |
| Advocate | Pink | Active referrer/promoter |

---

## Project structure

```
funnel-teardown/
├── teardown.py              CLI entry point
├── agents/
│   ├── brand_resolver.py    Agent 1 — GPT-4o-mini web search
│   ├── touchpoint_mapper.py Agent 2 — GPT-4o-mini + httpx scraping
│   └── journey_mapper.py    Agent 3 — Claude Sonnet
├── models/
│   └── funnel_map.py        All Pydantic models
├── report/
│   └── html_renderer.py     Pure Python HTML generator
├── state/
│   └── teardown_state.py    Shared state + .tmp/ cache
├── utils/
│   └── cost_tracker.py      Per-agent token cost tracking
├── tests/                   42 tests, all passing
├── demo/
│   └── ag1-teardown.html    Sample report (AG1 Athletic Greens)
└── .env.example             API key template
```

---

## Running tests

```bash
python3 -m pytest tests/ -v
```

All 42 tests pass. No API calls made — agents are fully mocked.

---

## Cost reference

| Agent | Model | Typical cost |
|---|---|---|
| Brand Resolver | gpt-4o-mini | ~$0.002 |
| Touchpoint Mapper | gpt-4o-mini | ~$0.010 |
| Journey Mapper | claude-sonnet-4-6 | ~$0.15–0.30 |
| **Total** | | **~$0.15–0.35** |

---

## Tips

**Ambiguous brand names** — if the tool raises `ValueError: Brand '...' is ambiguous`, re-run with `--url` or `--founder` to help Agent 1 pick the right brand.

**Creators vs. enterprises** — works for both. Creator funnels (newsletters, cohorts, digital products) tend to produce 4–6 steps. Enterprise brands (AG1, Hubspot) produce 6–10 steps.

**Iterating on Agent 3** — journey mapping is the most expensive and most creative step. If you want to tweak the output, use `--from-cache --agent 3` to re-run only Agent 3 without paying for the web search agents again.

**Reading the report** — open `teardown_report.html` directly in Chrome/Safari/Firefox. The Mermaid.js diagram renders client-side via CDN — you need an internet connection for the diagram to appear.

---

## Built with

- [OpenAI Python SDK](https://github.com/openai/openai-python) — Agents 1 & 2 (Responses API with web search)
- [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) — Agent 3
- [Pydantic v2](https://docs.pydantic.dev/) — data models and state
- [httpx](https://www.python-httpx.org/) + [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) — homepage scraping
- [Mermaid.js](https://mermaid.js.org/) — funnel flowchart diagrams
- [Rich](https://github.com/Textualize/rich) — CLI output

---

## License

MIT
