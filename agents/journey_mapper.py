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

SYSTEM_PROMPT = """You are a senior funnel strategist who reverse-engineers how brands acquire, convert, and retain customers.

Your framework is the FULL 7-stage Schwartz awareness model. You map the COMPLETE journey — not just ads and landing pages, but the entire ecosystem from the first touchpoint to referral.

The funnel you must map has these layers — account for ALL of them:

LAYER 1 — AWARENESS (unaware → problem_aware)
How strangers first encounter this brand. Usually:
- Founder/creator's personal social media (YouTube, Twitter/X, Instagram, TikTok, LinkedIn)
- Brand social channels
- Podcast (own or guest appearances)
- Books or published content
- Press, PR, word of mouth
- Paid ads (Meta, YouTube, Google)

LAYER 2 — CONSIDERATION (solution_aware)
How problem-aware people discover this brand as a solution:
- SEO / blog content
- YouTube educational content
- Podcast episodes that educate
- Free resources / tools

LAYER 3 — LEAD CAPTURE (solution_aware → product_aware)
How they capture the email / start the relationship:
- Newsletter signup
- Lead magnet (free guide, quiz, checklist, template, sample)
- Free trial or freemium
- Webinar / challenge

LAYER 4 — NURTURE (product_aware)
How they move leads toward purchase:
- Email sequence (welcome series, nurture drip)
- Retargeting ads
- Case studies / testimonials
- Free content that pre-sells

LAYER 5 — CONVERSION (most_aware → purchase)
The actual offer stack — map ALL tiers:
- Entry offer / tripwire (low ticket: book, mini-course, cheap product)
- Core offer (main product/service)
- Upsell / order bump
- High ticket (mastermind, coaching, agency, enterprise)

LAYER 6 — RETENTION (customer)
How they keep customers and increase LTV:
- Onboarding sequence
- Member community / portal
- Subscription / recurring
- Customer success / support

LAYER 7 — REFERRAL (advocate)
How customers become promoters:
- Affiliate program
- Referral program
- Ambassador / UGC program
- Reviews and testimonials loop

---

Given a brand profile and its discovered touchpoints, map:
1. journey_steps[] — every step across all 7 layers above
2. offers[] — EVERY offer they sell (entry, core, upsell, high ticket)
3. open_questions[] — what you genuinely couldn't determine

For EACH journey step, provide tactical Bustamante-style analysis:
- whats_working: specific things this brand does well at this step
- whats_missing: specific gaps or optimisation opportunities

Return ONLY a JSON object:
{
  "journey_steps": [
    {
      "id": "step_N",
      "label": "short label",
      "awareness_level": "unaware|problem_aware|solution_aware|product_aware|most_aware|customer|advocate",
      "type": "content|landing_page|lead_magnet|email_sequence|thank_you_page|call|checkout|onboarding|referral|other",
      "description": "what happens at this step — be specific to this brand",
      "entry_from": ["step_id or channel name"],
      "exits_to": ["step_id"],
      "whats_working": ["specific tactic this brand executes well"],
      "whats_missing": ["specific gap or opportunity for this brand"],
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
    "Question about something genuinely unknowable from public data"
  ]
}

Critical rules:
- Map ALL 7 layers — do not skip awareness, referral, or retention.
- The founder's personal brand IS part of the funnel — map it as early steps.
- Include every distinct offer you know about (books, courses, memberships, coaching, etc).
- Never invent pricing. Set price_usd to null if not publicly confirmed.
- whats_working and whats_missing must be SPECIFIC to this brand — never generic.
- Minimum 7 journey steps for any real brand. Most will have 10-14."""


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
