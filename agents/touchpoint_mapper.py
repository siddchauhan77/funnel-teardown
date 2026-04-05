"""
Agent 2: Touchpoint Mapper
Model: gpt-4o-mini-search-preview (OpenAI Responses API with web search)
Also: httpx to scrape brand homepage for social links and CTAs
Populates: FunnelMap.touchpoints
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


def _scrape_homepage(url: str) -> str:
    """Fetch homepage and return simplified text of links and CTAs."""
    try:
        resp = http_client.get(url)
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")
        links = [a.get("href", "") for a in soup.find_all("a", href=True)]
        return "\n".join(filter(None, links))[:3000]  # cap at 3000 chars
    except Exception:
        return ""


def map_touchpoints(state: TeardownState, tracker: CostTracker) -> None:
    """Discover brand touchpoints via web search + homepage scraping."""
    brand = state.funnel_map.brand
    homepage_links = _scrape_homepage(brand.website)

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

    raw = json.loads(output_text)
    state.funnel_map.touchpoints = [Touchpoint(**t) for t in raw]
