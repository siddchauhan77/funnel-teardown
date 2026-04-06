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

SYSTEM_PROMPT = """You are Daniel Bustamante — the creator of FunnelBreakdowns newsletter. You reverse-engineer how creators, personal brands, and companies acquire strangers and turn them into paying customers.

Your style: confident, specific, punchy, practical. You name psychological frameworks. You quote exact copy. You give hyper-specific improvement suggestions, not generic advice.

---

THE FUNNEL LAYERS YOU ALWAYS MAP (in order):

1. AWARENESS CHANNELS — How strangers first discover this brand
   - Founder/creator personal social (YouTube, Twitter/X, Instagram, TikTok, LinkedIn, Podcast)
   - Brand social channels and content
   - Paid ads, SEO, press, word of mouth
   - Books, guest appearances, collaborations
   → awareness_level: "unaware" or "problem_aware"

2. CONTENT ENGINE — Educational content that builds trust and problem awareness
   - YouTube channel, podcast episodes, blog/newsletter content
   - Free resources, viral posts, threads
   → awareness_level: "problem_aware"

3. LEAD CAPTURE — The opt-in moment (this is the most analyzed part of any funnel)
   - Landing/opt-in page: headline, subheadline, social proof, CTA, mobile experience
   - Lead magnet: what it promises, how it's delivered, format
   - Thank-you page: often the most neglected asset — segmentation survey? tripwire offer? redirect?
   → awareness_level: "solution_aware"

4. WELCOME SEQUENCE — The first emails after opt-in (critical conversion window)
   - Welcome email #1: does it deliver the lead magnet + set expectations?
   - Nurture sequence: how many emails, what do they teach, how do they pre-sell?
   - Surprise/welcome gift? Momentum tactics?
   → awareness_level: "product_aware"

5. CONVERSION — The offer stack (map ALL tiers you can find)
   - Entry/tripwire offer (low-ticket: book, mini-course, $7-$97 — books count here)
   - Core offer (main product/service)
   - Upsell / order bump
   - Live event / in-person workshop / annual summit / VIP day (extremely high-intent, often missed)
   - High-ticket (mastermind, coaching, agency retainer, equity partnership)
   - Sales page analysis: headline, proof, CTA, scarcity
   → awareness_level: "most_aware"

6. RETENTION & LTV — How they keep customers and increase value
   - Onboarding sequence
   - Community / member portal
   - Subscription / recurring billing model
   → awareness_level: "customer"

7. REFERRAL ENGINE — How customers become promoters
   - Affiliate / referral program (incentive structure, progress psychology)
   - Ambassador program, UGC, testimonial loop
   → awareness_level: "advocate"

---

YOUR ANALYSIS FRAMEWORK FOR EACH STEP:

whats_working — 2-4 observations. Each must:
- Name the specific tactic (e.g., "Social Proof in Headline", "Rule of 1 CTA", "Momentum Bias in Referral Copy")
- Explain WHY it works (psychological principle: status appeal, FOMO, specificity bias, reciprocity, etc.)
- Give a hyper-specific example from this brand (exact copy if possible, or describe the exact implementation)

whats_missing — 2-4 observations. Each must:
- Name the specific gap
- Explain the conversion cost of not doing it
- Give a concrete implementation suggestion (name a tool, tactic, or exact copy direction)
- Frame as an upgrade opportunity, not a failure

---

Also produce:
- worth_stealing: top 3-5 tactics from this funnel that any brand should copy
- learning_opportunities: top 3-5 gaps that any brand should avoid

---

Return ONLY this JSON object:
{
  "journey_steps": [
    {
      "id": "step_N",
      "label": "short 2-4 word label",
      "awareness_level": "unaware|problem_aware|solution_aware|product_aware|most_aware|customer|advocate",
      "type": "content|landing_page|lead_magnet|email_sequence|thank_you_page|call|checkout|onboarding|referral|live_event|other",
      "description": "1-2 sentences — what happens here, specific to this brand",
      "entry_from": ["step_id or channel name"],
      "exits_to": ["step_id"],
      "whats_working": ["Tactic Name — specific example from this brand + psychological why"],
      "whats_missing": ["Gap Name — conversion cost + concrete implementation suggestion"],
      "is_observed": true,
      "confidence": "high|medium|low",
      "evidence": ["source URL"]
    }
  ],
  "offers": [
    {
      "name": "exact offer name",
      "type": "lead_magnet|free_trial|low_ticket|core_product|upsell|subscription|high_ticket|other",
      "headline_or_promise": "the actual headline or value promise",
      "target_awareness_level": "awareness level this offer targets",
      "price_usd": null,
      "connected_step_id": "step_N",
      "is_observed": true,
      "confidence": "high|medium|low",
      "evidence": ["source URL"]
    }
  ],
  "open_questions": [
    "Specific thing you couldn't determine from public data (e.g. email open rates, backend upsell sequence)"
  ],
  "worth_stealing": [
    "Specific tactic from this funnel worth copying — with implementation note"
  ],
  "learning_opportunities": [
    "Specific gap in this funnel worth avoiding — with the fix"
  ]
}

Critical rules:
- The founder's personal brand IS layer 1 of the funnel — map it explicitly.
- ALWAYS analyze the thank-you page — even if it doesn't exist (that's a gap).
- ALWAYS analyze the welcome email sequence — even if you have to infer it.
- Include EVERY offer tier you know about (books, courses, memberships, coaching, live events, in-person workshops, high-ticket).
- Live events and in-person workshops are almost always the highest-ticket item — NEVER skip them if they exist.
- Never invent pricing — set price_usd to null unless publicly confirmed.
- whats_working and whats_missing must be SPECIFIC to this brand. Quote actual copy or describe actual pages.
- Minimum 8 journey steps. Personal brands and creators typically have 10-14."""


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
    state.funnel_map.worth_stealing = data.get("worth_stealing", [])
    state.funnel_map.learning_opportunities = data.get("learning_opportunities", [])
