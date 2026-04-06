"""
Agent 2: Touchpoint Mapper
Model: gpt-4o-mini (OpenAI Responses API with web search)
Also: httpx to scrape brand homepage for social links, CTAs, and brand meta
Populates: FunnelMap.touchpoints, FunnelMap.brand.theme_color, FunnelMap.brand.logo_url
"""
import json
import os
import httpx
from bs4 import BeautifulSoup
from openai import OpenAI
from state.teardown_state import TeardownState
from utils.cost_tracker import CostTracker
from models.funnel_map import Touchpoint

def _get_client() -> OpenAI:
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

http_client = httpx.Client(timeout=15, follow_redirects=True,
                           headers={"User-Agent": "Mozilla/5.0 (compatible; FunnelTeardown/1.0)"})

SYSTEM_PROMPT = """You are a brand channel researcher. Given a brand name, website, and homepage HTML,
identify ALL public channels where this brand has a presence.

Return a JSON array of touchpoint objects:
[
  {
    "platform": "youtube|linkedin|instagram|tiktok|newsletter|blog|podcast|seo|paid_ads|twitter|other",
    "handle_or_name": "channel name or handle",
    "url": "direct URL",
    "awareness_level": "unaware|problem_aware|solution_aware|product_aware|most_aware|customer|advocate",
    "is_observed": true,
    "confidence": "high|medium|low",
    "evidence": ["url where you found this"]
  }
]

Schwartz level guidance for channels:
- YouTube/TikTok/podcast/blog content → usually "unaware" or "problem_aware" (top of funnel)
- Newsletter/lead magnet → usually "solution_aware" (they opted in)
- Pricing/sales pages → "product_aware" to "most_aware"
- Onboarding/member portal → "customer"
- Referral/affiliate program → "advocate"

Also search for: "{brand} YouTube channel", "{brand} LinkedIn", "{brand} newsletter signup",
"{brand} podcast", "{brand} Instagram"

Rules:
- Only include touchpoints you found evidence for (is_observed: true) OR that are strongly implied
  by the business type (is_observed: false, confidence: medium or low)
- Return ONLY the JSON array, no markdown fences."""


def _scrape_homepage(url: str) -> tuple[str, dict]:
    """
    Fetch homepage. Returns (links_text_for_prompt, brand_meta_dict).
    brand_meta_dict may contain: theme_color, logo_url
    """
    try:
        resp = http_client.get(url)
        if resp.status_code != 200:
            return "", {}

        soup = BeautifulSoup(resp.text, "html.parser")

        # Links for the AI prompt
        links = [a.get("href", "") for a in soup.find_all("a", href=True)]
        links_text = "\n".join(filter(None, links))[:3000]

        # Brand visual meta
        meta: dict = {}

        theme_tag = soup.find("meta", attrs={"name": "theme-color"})
        if theme_tag and theme_tag.get("content"):
            color = theme_tag["content"].strip()
            if color.startswith("#") or color.startswith("rgb"):
                meta["theme_color"] = color

        og_image = (
            soup.find("meta", attrs={"property": "og:image"}) or
            soup.find("meta", attrs={"name": "og:image"})
        )
        if og_image and og_image.get("content"):
            meta["logo_url"] = og_image["content"].strip()

        return links_text, meta

    except Exception:
        return "", {}


def map_touchpoints(state: TeardownState, tracker: CostTracker) -> None:
    """Discover brand touchpoints via web search + homepage scraping."""
    brand = state.funnel_map.brand
    homepage_links, brand_meta = _scrape_homepage(brand.website)

    # Apply brand visual meta back to state immediately
    if brand_meta.get("theme_color") and not brand.theme_color:
        state.funnel_map.brand.theme_color = brand_meta["theme_color"]
    if brand_meta.get("logo_url") and not brand.logo_url:
        state.funnel_map.brand.logo_url = brand_meta["logo_url"]

    prompt = (
        f"Brand: {brand.name}\n"
        f"Website: {brand.website}\n"
        f"Description: {brand.description}\n"
        f"\nHomepage links found:\n{homepage_links}"
    )

    response = _get_client().responses.create(
        model="gpt-4o-mini",
        instructions=SYSTEM_PROMPT,
        input=prompt,
        tools=[{"type": "web_search_preview"}],
    )

    tracker.record(
        "touchpoint_mapper",
        "gpt-4o-mini",
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )

    # Extract text from Responses API output (may contain web_search + message items)
    output_text = ""
    for item in response.output:
        if hasattr(item, "content"):
            for block in item.content:
                if hasattr(block, "text"):
                    output_text += block.text
        elif hasattr(item, "text"):
            output_text += item.text

    # Strip markdown fences if GPT wrapped the JSON
    output_text = output_text.strip()
    if output_text.startswith("```"):
        lines = output_text.split("\n")
        output_text = "\n".join(lines[1:-1])

    # If model returned prose instead of JSON (common when web_search fires),
    # make a second formatting call to extract the structured data
    try:
        raw = json.loads(output_text)
    except json.JSONDecodeError:
        format_response = _get_client().chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": (
                    "Convert the brand channel information below into a JSON object "
                    "with a single key 'touchpoints' containing an array. Each item must have: "
                    "platform (youtube|linkedin|instagram|tiktok|newsletter|blog|podcast|seo|paid_ads|twitter|other), "
                    "handle_or_name, url, "
                    "awareness_level (unaware|problem_aware|solution_aware|product_aware|most_aware|customer|advocate), "
                    "is_observed (bool), confidence (high|medium|low), evidence (list of urls). "
                    "Return ONLY the JSON object."
                )},
                {"role": "user", "content": output_text},
            ],
        )
        wrapped = json.loads(format_response.choices[0].message.content)
        raw = wrapped.get("touchpoints", wrapped) if isinstance(wrapped, dict) else wrapped

    state.funnel_map.touchpoints = [Touchpoint(**t) for t in raw]
