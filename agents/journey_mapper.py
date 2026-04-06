"""
Agent 3: Journey & Offers Mapper
Model: claude-sonnet-4-6 (Anthropic)
Populates: FunnelMap.journey_steps, FunnelMap.offers, FunnelMap.open_questions
"""
import json
import os
import anthropic
import openai
from state.teardown_state import TeardownState
from utils.cost_tracker import CostTracker
from models.funnel_map import JourneyStep, Offer


def _get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _get_openai_client() -> openai.OpenAI:
    return openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _strip_json_fences(text: str) -> str:
    """Strip markdown code fences if the model wrapped the JSON in them."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    return text


def _map_with_gpt(user_message: str, tracker: CostTracker) -> dict:
    """Fallback: call GPT-4o when Anthropic is unavailable."""
    response = _get_openai_client().chat.completions.create(
        model="gpt-4o",
        max_tokens=4096,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )
    tracker.record(
        "journey_mapper",
        "gpt-4o",
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens,
    )
    return json.loads(response.choices[0].message.content)

SYSTEM_PROMPT = """You are a funnel strategist who reverse-engineers brand acquisition funnels.
You think through the lens of Eugene Schwartz's 5 levels of awareness, extended to include
Customer (retention) and Advocate (referral).

Given a brand profile and its discovered touchpoints, map:
1. The full journey_steps[] from stranger to advocate
2. The offers[] they use to move people forward
3. The open_questions[] — what you couldn't determine from public data

For EACH journey step, provide honest "whats_working" and "whats_missing" analysis
in the style of Daniel Bustamante's FunnelBreakdowns newsletter — tactical, specific, actionable.

Return ONLY a JSON object with this exact structure:
{
  "journey_steps": [
    {
      "id": "step_N",
      "label": "short label",
      "awareness_level": "unaware|problem_aware|solution_aware|product_aware|most_aware|customer|advocate",
      "type": "content|landing_page|lead_magnet|email_sequence|thank_you_page|call|checkout|onboarding|referral|other",
      "description": "what happens at this step",
      "entry_from": ["step_id or touchpoint platform"],
      "exits_to": ["step_id"],
      "whats_working": ["specific tactic that works well"],
      "whats_missing": ["specific gap or improvement opportunity"],
      "is_observed": true,
      "confidence": "high|medium|low",
      "evidence": ["source URL"]
    }
  ],
  "offers": [
    {
      "name": "offer name",
      "type": "lead_magnet|free_trial|low_ticket|core_product|upsell|subscription|high_ticket|other",
      "headline_or_promise": "main value prop or headline",
      "target_awareness_level": "awareness level this offer targets",
      "price_usd": null,
      "connected_step_id": "step_N",
      "is_observed": true,
      "confidence": "high|medium|low",
      "evidence": ["source URL"]
    }
  ],
  "open_questions": [
    "Question about something you couldn't determine from public data"
  ]
}

Critical rules:
- Never invent pricing, metrics, or private data. Set price_usd to null if not publicly visible.
- Set is_observed: false for inferred steps with no direct evidence.
- whats_working and whats_missing must be SPECIFIC to this brand — not generic advice.
- open_questions must be genuinely unanswerable from public data only."""


def map_journey(state: TeardownState, tracker: CostTracker) -> None:
    """Use Claude to reason over brand + touchpoints and map the full funnel journey."""
    brand = state.funnel_map.brand
    touchpoints_summary = "\n".join(
        f"- {t.platform}: {t.handle_or_name} ({t.url}) → targets {t.awareness_level} [confidence: {t.confidence}]"
        for t in state.funnel_map.touchpoints
    )

    user_message = (
        f"Brand: {brand.name}\n"
        f"Website: {brand.website}\n"
        f"Founder: {brand.founder or 'unknown'}\n"
        f"Description: {brand.description}\n"
        f"ICP: {brand.primary_icp}\n"
        f"\nDiscovered touchpoints:\n{touchpoints_summary}\n"
        f"\nMap the full funnel journey for this brand."
    )

    try:
        response = _get_client().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        tracker.record(
            "journey_mapper",
            "claude-sonnet-4-6",
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        data = json.loads(_strip_json_fences(response.content[0].text))
    except Exception:
        # Claude unavailable (low credits, bad key, rate limit) — fall back to GPT-4o
        data = _map_with_gpt(user_message, tracker)

    state.funnel_map.journey_steps = [JourneyStep(**s) for s in data["journey_steps"]]
    state.funnel_map.offers = [Offer(**o) for o in data["offers"]]
    state.funnel_map.open_questions = data["open_questions"]
