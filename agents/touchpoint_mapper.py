"""
Agent 2: Touchpoint Mapper
Model: gpt-4o-mini (OpenAI Responses API with web search)
Strategy: 5 targeted searches covering the full funnel stack, then one formatting call.
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


def _scrape_homepage(url: str) -> tuple[str, dict]:
    """Fetch homepage. Returns (links_text_for_prompt, brand_meta_dict)."""
    try:
        resp = http_client.get(url)
        if resp.status_code != 200:
            return "", {}

        soup = BeautifulSoup(resp.text, "html.parser")

        links = [a.get("href", "") for a in soup.find_all("a", href=True)]
        links_text = "\n".join(filter(None, links))[:3000]

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


def _web_search(client: OpenAI, query: str) -> tuple[str, int, int]:
    """
    Run a single web search via Responses API.
    Returns (text_result, input_tokens, output_tokens).
    """
    response = client.responses.create(
        model="gpt-4o-mini",
        instructions=(
            "You are a research assistant. Search the web and report everything you find "
            "about the query. Be thorough and specific — include channel names, URLs, "
            "descriptions, pricing if visible, and any other relevant details. "
            "Report factually what you found. Do not format as JSON."
        ),
        input=query,
        tools=[{"type": "web_search_preview"}],
    )
    output_text = ""
    for item in response.output:
        if hasattr(item, "content") and isinstance(item.content, list):
            for block in item.content:
                if hasattr(block, "text"):
                    output_text += block.text
        elif hasattr(item, "text"):
            output_text += item.text

    return output_text, response.usage.input_tokens, response.usage.output_tokens


def map_touchpoints(state: TeardownState, tracker: CostTracker) -> None:
    """
    Discover brand touchpoints via 5 targeted web searches covering the full funnel:
    1. Social + content channels (awareness)
    2. Founder personal brand (awareness amplifier)
    3. Lead magnets + newsletter (consideration)
    4. Offers + pricing (decision)
    5. Referral + affiliate + community (post-purchase)
    """
    brand = state.funnel_map.brand
    homepage_links, brand_meta = _scrape_homepage(brand.website)

    if brand_meta.get("theme_color") and not brand.theme_color:
        state.funnel_map.brand.theme_color = brand_meta["theme_color"]
    if brand_meta.get("logo_url") and not brand.logo_url:
        state.funnel_map.brand.logo_url = brand_meta["logo_url"]

    client = _get_client()
    founder = brand.founder or ""
    name = brand.name
    site = brand.website

    # 5 targeted searches — one per funnel layer
    searches = [
        # 1. Social + content channels
        (f"{name} YouTube channel Instagram TikTok Twitter X podcast site:youtube.com OR site:instagram.com OR site:twitter.com OR site:tiktok.com OR site:spotify.com"),
        # 2. Founder personal brand (their audience feeds into brand)
        (f"{founder or name} founder personal brand LinkedIn Twitter podcast book newsletter" if founder else f"{name} founder CEO LinkedIn Twitter Instagram"),
        # 3. Lead magnets + email list + newsletter + blog
        (f"{name} newsletter signup lead magnet free guide email list blog {site}"),
        # 4. Products, offers, pricing, courses, membership
        (f"{name} products pricing plans courses membership program buy {site}"),
        # 5. Referral, affiliate, community, reviews
        (f"{name} affiliate program referral ambassador community forum reviews"),
    ]

    all_research = ""
    total_in_tokens = 0
    total_out_tokens = 0

    for query in searches:
        try:
            text, in_tok, out_tok = _web_search(client, query)
            all_research += f"\n\n---\nSEARCH: {query}\nRESULTS:\n{text}"
            total_in_tokens += in_tok
            total_out_tokens += out_tok
        except Exception:
            pass  # skip failed searches, use what we got

    tracker.record(
        "touchpoint_mapper",
        "gpt-4o-mini",
        input_tokens=total_in_tokens,
        output_tokens=total_out_tokens,
    )

    # Include homepage links in context too
    if homepage_links:
        all_research += f"\n\n---\nHOMEPAGE LINKS:\n{homepage_links}"

    # One formatting call to convert all research into structured touchpoints
    format_response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": f"""You are a funnel analyst. Convert the research below into a structured list of all brand touchpoints.

Brand: {name}
Founder: {founder or 'unknown'}
Website: {site}

Map the COMPLETE funnel stack — do not miss any layer:
1. AWARENESS: Social channels (YouTube, Instagram, TikTok, Twitter/X, LinkedIn, podcast)
2. FOUNDER BRAND: Founder's personal social accounts, books, podcast — these feed brand awareness
3. CONSIDERATION: Blog/SEO content, newsletter, lead magnet, free resources
4. DECISION: Core offers, pricing pages, sales pages, checkout
5. RETENTION: Onboarding, member portal, community, customer emails
6. REFERRAL: Affiliate program, referral program, ambassador program, UGC

Return a JSON object with key "touchpoints" containing an array. Each item:
{{
  "platform": "youtube|linkedin|instagram|tiktok|newsletter|blog|podcast|seo|paid_ads|twitter|other",
  "handle_or_name": "specific channel/product name",
  "url": "direct URL if found, else brand website",
  "awareness_level": "unaware|problem_aware|solution_aware|product_aware|most_aware|customer|advocate",
  "is_observed": true or false,
  "confidence": "high|medium|low",
  "evidence": ["URL where found"]
}}

Schwartz level mapping:
- YouTube/TikTok/Instagram/Podcast/Twitter content → unaware or problem_aware
- Founder personal social → unaware
- Blog/SEO content → problem_aware
- Newsletter/lead magnet → solution_aware
- Core product/pricing page → product_aware to most_aware
- Checkout/sales page → most_aware
- Onboarding/community/membership → customer
- Referral/affiliate → advocate

Include ALL channels found. Minimum 8 touchpoints for any real brand. Be specific with names and URLs."""},
            {"role": "user", "content": all_research[:12000]},  # cap context length
        ],
    )

    wrapped = json.loads(format_response.choices[0].message.content)
    raw = wrapped.get("touchpoints", wrapped) if isinstance(wrapped, dict) else wrapped

    VALID_PLATFORMS = {"youtube", "linkedin", "instagram", "tiktok", "newsletter",
                       "blog", "podcast", "seo", "paid_ads", "twitter", "other"}
    PLATFORM_MAP = {
        "x": "twitter", "x.com": "twitter", "twitter/x": "twitter",
        "youtube channel": "youtube", "youtube shorts": "youtube",
        "instagram reels": "instagram", "ig": "instagram",
        "courses": "other", "course": "other", "book": "other", "books": "other",
        "email": "newsletter", "email list": "newsletter", "substack": "newsletter",
        "website": "other", "landing page": "other", "affiliate": "other",
        "referral": "other", "community": "other", "facebook": "other",
        "threads": "other", "reddit": "other",
    }

    clean = []
    for t in raw:
        p = str(t.get("platform", "other")).lower().strip()
        t["platform"] = PLATFORM_MAP.get(p, p) if p not in VALID_PLATFORMS else p
        if t["platform"] not in VALID_PLATFORMS:
            t["platform"] = "other"
        clean.append(t)

    state.funnel_map.touchpoints = [Touchpoint(**t) for t in clean]
