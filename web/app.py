"""
FunnelTeardown AI — Web App
FastAPI + Server-Sent Events for real-time agent progress.

GET  /           → main app UI
POST /analyze    → SSE stream: agent progress events → report_ready
GET  /report/:id → serves the generated HTML report
GET  /health     → health check
"""
import asyncio
import json
import os
import queue
import threading
import time
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

# Import agents after load_dotenv so API keys are available
from agents.brand_resolver import resolve_brand
from agents.touchpoint_mapper import map_touchpoints
from agents.journey_mapper import map_journey
from report.html_renderer import render_html
from state.teardown_state import TeardownState
from utils.cost_tracker import CostTracker

app = FastAPI(title="FunnelTeardown AI")

# In-memory report store — {id: {"html": str, "brand": str}}
_reports: dict[str, dict] = {}

# ─── Rate limiter ─────────────────────────────────────────────────────────────
RATE_LIMIT = 3
RATE_WINDOW = 86_400  # 24 hours

_rate_store: dict[str, list[float]] = defaultdict(list)


def _client_ip(request: Request) -> str:
    """Return the real client IP, honouring X-Forwarded-For from Railway proxy."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _is_rate_limited(ip: str) -> bool:
    """Returns True if this IP has exceeded the limit. Records the attempt if allowed."""
    now = time.time()
    window_start = now - RATE_WINDOW
    _rate_store[ip] = [t for t in _rate_store[ip] if t > window_start]
    if len(_rate_store[ip]) >= RATE_LIMIT:
        return True
    _rate_store[ip].append(now)
    return False


def _attempts_remaining(ip: str) -> int:
    now = time.time()
    window_start = now - RATE_WINDOW
    used = len([t for t in _rate_store[ip] if t > window_start])
    return max(0, RATE_LIMIT - used)

INDEX_HTML = Path(__file__).parent / "index.html"


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(INDEX_HTML.read_text(encoding="utf-8"))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/report/{report_id}", response_class=HTMLResponse)
def get_report(report_id: str):
    entry = _reports.get(report_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Report not found")
    return HTMLResponse(entry["html"])


@app.get("/download/{report_id}")
def download_report(report_id: str):
    entry = _reports.get(report_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Report not found")
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "" for c in entry["brand"]).strip().replace(" ", "-")
    filename = f"FunnelTeardown-{safe_name}.html"
    return HTMLResponse(
        content=entry["html"],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class AnalyzeRequest(BaseModel):
    brand: str
    founder: str = ""
    url: str = ""


@app.post("/analyze")
async def analyze(req: AnalyzeRequest, request: Request):
    ip = _client_ip(request)

    if _is_rate_limited(ip):
        # Stream a single rate_limited event then close
        async def _rate_stream():
            yield f"data: {json.dumps({'type': 'rate_limited', 'limit': RATE_LIMIT})}\n\n"
        return StreamingResponse(
            _rate_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    hints: dict = {}
    if req.founder.strip():
        hints["founder"] = req.founder.strip()
    if req.url.strip():
        hints["url"] = req.url.strip()

    remaining = _attempts_remaining(ip)  # after this run is counted
    q: "queue.Queue[dict | None]" = queue.Queue()

    def worker():
        _run_pipeline(req.brand.strip(), hints, q, remaining)
        q.put(None)  # sentinel — stream ends

    threading.Thread(target=worker, daemon=True).start()

    return StreamingResponse(
        _event_stream(q),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ─── Pipeline ────────────────────────────────────────────────────────────────

def _run_pipeline(brand: str, hints: dict, q: queue.Queue, remaining: int = 0) -> None:
    """Run the 3-agent pipeline in a background thread, push SSE dicts to q."""
    import time
    start = time.time()

    state = TeardownState.new(brand, hints=hints)
    tracker = CostTracker()

    # ── Agent 1: Brand Resolver ──────────────────────────────────────────────
    q.put({"type": "agent_start", "agent": "brand_resolver",
           "message": f'Searching the web for "{brand}"…'})
    try:
        resolve_brand(state, tracker)
        b = state.funnel_map.brand
        conf = b.confidence.value if hasattr(b.confidence, "value") else str(b.confidence)
        q.put({"type": "agent_done", "agent": "brand_resolver",
               "data": {
                   "name": b.name,
                   "website": b.website,
                   "founder": b.founder or "",
                   "confidence": conf,
                   "cost": round(tracker.agent_cost("brand_resolver"), 5),
               }})
    except ValueError as e:
        q.put({"type": "error", "message": str(e),
               "hint": "Try adding --url or --founder to disambiguate."})
        return
    except Exception as e:
        err = str(e)
        print(f"[brand_resolver error] {err}", flush=True)
        if "credit" in err.lower() or "billing" in err.lower():
            q.put({"type": "error",
                   "message": "OpenAI API credit balance is too low.",
                   "hint": "Top up at platform.openai.com → Billing, then try again."})
        else:
            q.put({"type": "error",
                   "message": "Couldn't resolve that brand — web search may have returned ambiguous results.",
                   "hint": "Try adding a website URL (e.g. ag1.com) to help narrow it down."})
        return

    # ── Agent 2: Touchpoint Mapper ───────────────────────────────────────────
    q.put({"type": "agent_start", "agent": "touchpoint_mapper",
           "message": "Scraping homepage and scanning channels…"})
    try:
        map_touchpoints(state, tracker)
        touchpoints = state.funnel_map.touchpoints
        platforms = sorted({
            (t.platform.value if hasattr(t.platform, "value") else str(t.platform))
            for t in touchpoints
        })
        q.put({"type": "agent_done", "agent": "touchpoint_mapper",
               "data": {
                   "count": len(touchpoints),
                   "platforms": platforms[:6],
                   "cost": round(tracker.agent_cost("touchpoint_mapper"), 5),
               }})
    except Exception as e:
        err = str(e)
        print(f"[touchpoint_mapper error] {err}", flush=True)
        if "credit" in err.lower() or "billing" in err.lower():
            q.put({"type": "error",
                   "message": "OpenAI API credit balance is too low.",
                   "hint": "Top up at platform.openai.com → Billing, then try again."})
        else:
            q.put({"type": "error",
                   "message": "Touchpoint discovery failed — couldn't scrape enough channel data.",
                   "hint": "Try again or add the website URL to help the scraper."})
        return

    # ── Agent 3: Journey Mapper ──────────────────────────────────────────────
    q.put({"type": "agent_start", "agent": "journey_mapper",
           "message": "Claude is mapping the stranger → advocate journey…"})
    try:
        map_journey(state, tracker)
        q.put({"type": "agent_done", "agent": "journey_mapper",
               "data": {
                   "steps": len(state.funnel_map.journey_steps),
                   "offers": len(state.funnel_map.offers),
                   "questions": len(state.funnel_map.open_questions),
                   "cost": round(tracker.agent_cost("journey_mapper"), 5),
               }})
    except Exception as e:
        err = str(e)
        if "credit balance is too low" in err or "billing" in err.lower():
            q.put({"type": "error",
                   "message": "Anthropic API credit balance is too low.",
                   "hint": "Top up at console.anthropic.com → Plans & Billing, then try again."})
        elif "401" in err or "authentication" in err.lower():
            q.put({"type": "error",
                   "message": "Invalid Anthropic API key.",
                   "hint": "Check ANTHROPIC_API_KEY in your Railway environment variables."})
        elif "rate_limit" in err.lower() or "429" in err:
            q.put({"type": "error",
                   "message": "Anthropic rate limit hit — too many requests.",
                   "hint": "Wait 30 seconds and try again."})
        else:
            q.put({"type": "error",
                   "message": "Journey mapping failed — Claude couldn't complete the analysis.",
                   "hint": "Try again. If it keeps failing, the brand may have limited public data."})
        return

    # ── Render ───────────────────────────────────────────────────────────────
    q.put({"type": "rendering", "message": "Rendering report…"})

    duration = time.time() - start
    meta = state.funnel_map.run_metadata
    meta.timestamp = datetime.now().isoformat()
    meta.total_cost_usd = tracker.total_cost()
    meta.agent_costs = tracker.agent_costs_dict()
    meta.model_used = tracker.models_used_dict()
    meta.duration_seconds = round(duration, 1)

    try:
        report_html = render_html(state.funnel_map)
    except Exception as e:
        q.put({"type": "error", "message": f"Render failed: {e}"})
        return

    report_id = str(uuid.uuid4())
    _reports[report_id] = {"html": report_html, "brand": state.funnel_map.brand.name}

    q.put({
        "type": "report_ready",
        "report_id": report_id,
        "brand": state.funnel_map.brand.name,
        "cost": round(tracker.total_cost(), 4),
        "duration": round(duration, 1),
        "remaining": remaining,
    })


# ─── SSE helper ──────────────────────────────────────────────────────────────

async def _event_stream(q: queue.Queue) -> AsyncGenerator[str, None]:
    while True:
        try:
            event = q.get_nowait()
        except queue.Empty:
            await asyncio.sleep(0.08)
            continue

        if event is None:
            break

        yield f"data: {json.dumps(event)}\n\n"

        if event.get("type") in ("report_ready", "error"):
            break
