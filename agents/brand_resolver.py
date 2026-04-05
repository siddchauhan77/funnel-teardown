"""
Agent 1: Brand Resolver
Model: gpt-4o-mini-search-preview (OpenAI Responses API with web search)
Populates: FunnelMap.brand
"""
import json
import os
from openai import OpenAI
from state.teardown_state import TeardownState
from utils.cost_tracker import CostTracker
from models.funnel_map import Brand

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", "sk-placeholder"))

SYSTEM_PROMPT = """You are a brand research assistant. Given a brand name (and optional hints),
search the web to identify the correct brand and return a JSON object with this exact structure:

{
  "name": "official brand name",
  "website": "primary website URL",
  "founder": "founder name or null",
  "description": "1-2 sentence description of what they sell/do",
  "primary_icp": "1 sentence describing their core customer",
  "confidence": "high|medium|low",
  "evidence": ["url1", "url2"],
  "ambiguous": false,
  "ambiguity_note": null
}

Rules:
- If the brand name could match 2+ completely different companies/people, set ambiguous: true
  and explain in ambiguity_note. Do NOT guess.
- Never invent URLs, metrics, or facts not found in search results.
- confidence = "high" if you found the official site; "medium" if inferred; "low" if uncertain.
- Return ONLY the JSON object, no markdown fences."""


def resolve_brand(state: TeardownState, tracker: CostTracker) -> None:
    """Search web for brand info, populate state.funnel_map.brand."""
    hints = state.hints
    hint_parts = []
    if hints.get("founder"):
        hint_parts.append(f"Founder: {hints['founder']}")
    if hints.get("url"):
        hint_parts.append(f"Website hint: {hints['url']}")

    hint_str = ("\n\nAdditional hints:\n" + "\n".join(hint_parts)) if hint_parts else ""
    prompt = f"Research the brand: {state.brand_input}{hint_str}"

    response = openai_client.responses.create(
        model="gpt-4o-mini-search-preview",
        instructions=SYSTEM_PROMPT,
        input=prompt,
    )

    tracker.record(
        "brand_resolver",
        "gpt-4o-mini-search-preview",
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )

    data = json.loads(response.output_text)

    if data.get("ambiguous"):
        note = data.get("ambiguity_note", "multiple matches found")
        raise ValueError(
            f"Brand '{state.brand_input}' is ambiguous: {note}\n"
            "Tip: re-run with --founder or --url to disambiguate."
        )

    state.funnel_map.brand = Brand(
        name=data["name"],
        website=data["website"],
        founder=data.get("founder"),
        description=data["description"],
        primary_icp=data["primary_icp"],
        confidence=data["confidence"],
        evidence=data.get("evidence", []),
    )
