"""
Simple deterministic funnel mapper.

This path makes FunnelTeardown useful before any model call succeeds. It uses the
homepage plus link patterns to produce a bounded, honest first-pass report.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from models.funnel_map import Brand, JourneyStep, Offer, Touchpoint
from state.teardown_state import TeardownState
from utils.cost_tracker import CostTracker


USER_AGENT = "Mozilla/5.0 (compatible; FunnelTeardown/1.0; +https://github.com/siddchauhan77/funnel-teardown)"


@dataclass
class HomepageScan:
    url: str
    title: str
    description: str
    text_sample: str
    links: list[tuple[str, str]]
    theme_color: str | None = None
    logo_url: str | None = None


PLATFORM_PATTERNS = {
    "youtube": ("youtube.com", "youtu.be"),
    "linkedin": ("linkedin.com",),
    "instagram": ("instagram.com",),
    "tiktok": ("tiktok.com",),
    "twitter": ("twitter.com", "x.com"),
    "podcast": ("spotify.com", "apple.com/podcast", "podcasts.apple.com"),
}

PAGE_PATTERNS = {
    "blog": ("blog", "articles", "resources", "learn"),
    "newsletter": ("newsletter", "subscribe", "email"),
    "lead_magnet": ("guide", "free", "download", "template", "checklist", "ebook", "lead-magnet"),
    "pricing": ("pricing", "plans", "membership", "join", "buy", "shop", "course", "product"),
    "demo": ("demo", "book", "call", "consultation", "apply"),
    "community": ("community", "members", "customer", "portal"),
    "referral": ("affiliate", "referral", "partner", "ambassador"),
}


def run_simple_analysis(state: TeardownState, tracker: CostTracker | None = None) -> None:
    """Populate the funnel map with a deterministic URL-based report."""
    scan = scan_homepage(state.brand_input, state.hints.get("url", ""))
    site = scan.url
    confidence = "high" if scan.title or scan.description else "low"
    evidence = [site] if site else []

    state.funnel_map.brand = Brand(
        name=state.brand_input.strip(),
        website=site,
        founder=state.hints.get("founder") or None,
        description=scan.description or f"Homepage-based funnel scan for {state.brand_input.strip()}.",
        primary_icp=_infer_icp(scan.text_sample),
        confidence=confidence,
        evidence=evidence,
        theme_color=scan.theme_color,
        logo_url=scan.logo_url,
    )
    state.funnel_map.touchpoints = _touchpoints_from_scan(state.brand_input, scan)
    state.funnel_map.journey_steps = _journey_steps_from_scan(state.brand_input, scan)
    state.funnel_map.offers = _offers_from_scan(scan)
    state.funnel_map.open_questions = [
        "What happens inside the email sequence after opt-in?",
        "Which paid channels and retargeting audiences drive the most revenue?",
        "What conversion rates exist between homepage, lead capture, checkout, and repeat purchase?",
    ]
    state.funnel_map.worth_stealing = _worth_stealing(scan)
    state.funnel_map.learning_opportunities = _learning_opportunities(scan)
    state.funnel_map.ascension_path = _ascension_path(scan)

    if tracker is not None:
        tracker.record("simple_mapper", "deterministic", input_tokens=0, output_tokens=0)


def scan_homepage(brand: str, raw_url: str) -> HomepageScan:
    url = _normalize_url(raw_url) if raw_url else _best_guess_url(brand)
    try:
        with httpx.Client(timeout=12, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
            resp = client.get(url)
            resp.raise_for_status()
    except Exception:
        return HomepageScan(url=url, title="", description="", text_sample="", links=[])

    soup = BeautifulSoup(resp.text, "html.parser")
    title = _text(soup.title.string if soup.title else "")
    description = _meta(soup, "description") or _meta(soup, "og:description")
    text_sample = _text(" ".join(soup.get_text(" ").split()))[:1800]
    links = _extract_links(soup, str(resp.url))
    theme_color = _meta(soup, "theme-color")
    logo_url = _meta(soup, "og:image")
    if logo_url:
        logo_url = urljoin(str(resp.url), logo_url)

    return HomepageScan(
        url=str(resp.url),
        title=title,
        description=_text(description),
        text_sample=text_sample,
        links=links,
        theme_color=theme_color if theme_color and theme_color.startswith("#") else None,
        logo_url=logo_url,
    )


def _normalize_url(raw_url: str) -> str:
    raw_url = raw_url.strip()
    if not raw_url:
        return ""
    if not raw_url.startswith(("http://", "https://")):
        raw_url = "https://" + raw_url
    return raw_url


def _best_guess_url(brand: str) -> str:
    domain = "".join(c for c in brand.lower() if c.isalnum())
    return f"https://{domain}.com"


def _meta(soup: BeautifulSoup, name: str) -> str:
    tag = (
        soup.find("meta", attrs={"name": name})
        or soup.find("meta", attrs={"property": name})
        or soup.find("meta", attrs={"property": f"og:{name}"})
    )
    return _text(tag.get("content", "")) if tag else ""


def _text(value: str) -> str:
    return " ".join(str(value or "").split())


def _extract_links(soup: BeautifulSoup, base_url: str) -> list[tuple[str, str]]:
    seen: set[str] = set()
    links: list[tuple[str, str]] = []
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a.get("href", "").strip())
        if href in seen or href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        seen.add(href)
        label = _text(a.get_text(" ")) or urlparse(href).netloc
        links.append((label[:80], href))
    return links[:80]


def _touchpoints_from_scan(brand: str, scan: HomepageScan) -> list[Touchpoint]:
    touchpoints: list[Touchpoint] = [
        Touchpoint(
            platform="other",
            handle_or_name=f"{brand} homepage",
            url=scan.url,
            awareness_level="product_aware",
            is_observed=bool(scan.text_sample),
            confidence="high" if scan.text_sample else "low",
            evidence=[scan.url] if scan.url else [],
        )
    ]

    for label, href in scan.links:
        platform = _platform_for_url(href)
        if platform:
            touchpoints.append(Touchpoint(
                platform=platform,
                handle_or_name=label or platform.title(),
                url=href,
                awareness_level="unaware",
                is_observed=True,
                confidence="medium",
                evidence=[scan.url, href],
            ))

    for kind, words in PAGE_PATTERNS.items():
        match = _first_matching_link(scan.links, words)
        if not match:
            continue
        label, href = match
        platform = "newsletter" if kind in {"newsletter", "lead_magnet"} else "blog" if kind == "blog" else "other"
        level = {
            "blog": "problem_aware",
            "newsletter": "solution_aware",
            "lead_magnet": "solution_aware",
            "pricing": "most_aware",
            "demo": "most_aware",
            "community": "customer",
            "referral": "advocate",
        }.get(kind, "product_aware")
        touchpoints.append(Touchpoint(
            platform=platform,
            handle_or_name=label,
            url=href,
            awareness_level=level,
            is_observed=True,
            confidence="medium",
            evidence=[scan.url, href],
        ))

    return _dedupe_touchpoints(touchpoints)


def _journey_steps_from_scan(brand: str, scan: HomepageScan) -> list[JourneyStep]:
    blog = _first_matching_link(scan.links, PAGE_PATTERNS["blog"])
    lead = _first_matching_link(scan.links, PAGE_PATTERNS["lead_magnet"] + PAGE_PATTERNS["newsletter"])
    pricing = _first_matching_link(scan.links, PAGE_PATTERNS["pricing"])
    demo = _first_matching_link(scan.links, PAGE_PATTERNS["demo"])
    community = _first_matching_link(scan.links, PAGE_PATTERNS["community"])
    referral = _first_matching_link(scan.links, PAGE_PATTERNS["referral"])

    return [
        _step("step_1", "Social discovery", "unaware", "content",
              f"New visitors likely discover {brand} through public content, search, social profiles, or word of mouth before they reach the homepage.",
              [], ["step_2"], ["Homepage links out to public discovery channels."],
              ["Channel performance is unknown without ad account, analytics, or platform data."],
              "free", "Public content or referral creates the first click.", "The brand earns enough trust to make a site visit feel worth it.", "Visit the site or follow a channel.", False, "low", [scan.url]),
        _step("step_2", "Homepage promise", "product_aware", "landing_page",
              scan.description or f"The homepage becomes the main product-aware pitch for {brand}.",
              ["step_1"], ["step_3", "step_5"], ["The homepage gives a central place to frame the promise and route intent."],
              ["The page should segment cold visitors from high-intent buyers with distinct CTAs."],
              "free", scan.title or f"{brand} homepage", scan.description or "The homepage must create the main belief shift.", "Choose a next step from the homepage.", bool(scan.text_sample), "medium", [scan.url]),
        _step("step_3", "Trust content", "problem_aware", "content",
              _link_sentence(blog, "Educational content appears to be part of the consideration path.", "No obvious blog or education hub was found from the homepage."),
              ["step_2"], ["step_4"], ["Education content helps convert problem-aware visitors before asking for a sale."],
              ["If no content hub exists, cold visitors have fewer ways to build trust before buying."],
              "free", "Useful content reframes the problem.", "The brand becomes the guide, not only the seller.", "Read, watch, or subscribe.", bool(blog), "medium" if blog else "low", _evidence(scan, blog)),
        _step("step_4", "Lead capture", "solution_aware", "lead_magnet",
              _link_sentence(lead, "A subscribe or free-resource path gives non-buyers a lower-friction next step.", "No clear lead magnet or newsletter path was found from the homepage."),
              ["step_3"], ["step_5"], ["Lead capture protects demand from visitors who are interested but not ready to buy."],
              ["The thank-you page and welcome email sequence need direct review because they are not visible from a homepage crawl."],
              "free", "A useful free resource lowers commitment.", "The brand builds trust through continued teaching.", "Subscribe or download.", bool(lead), "medium" if lead else "low", _evidence(scan, lead)),
        _step("step_5", "Offer page", "most_aware", "landing_page",
              _link_sentence(pricing or demo, "A pricing, product, demo, buy, or call path captures high-intent visitors.", "No obvious pricing, product, demo, buy, or call path was found from the homepage."),
              ["step_2", "step_4"], ["step_6"], ["High-intent traffic needs a direct action path close to the homepage."],
              ["The offer page should make price, proof, risk reversal, and next step easy to compare."],
              "core", "The buyer is ready to solve the problem.", "Proof and risk reversal make the decision feel safer.", "Buy, join, apply, book, or request a demo.", bool(pricing or demo), "medium" if pricing or demo else "low", _evidence(scan, pricing or demo)),
        _step("step_6", "Post-purchase path", "customer", "onboarding",
              _link_sentence(community, "A community, customer, member, or portal link suggests a post-purchase experience.", "The post-purchase onboarding path is not visible from the homepage."),
              ["step_5"], ["step_7"], ["Retention starts immediately after conversion."],
              ["Without access to onboarding emails or member areas, LTV analysis stays incomplete."],
              "continuity", "A new customer wants quick confirmation they made the right choice.", "The brand must create early wins.", "Log in, join the community, or consume the product.", bool(community), "low", _evidence(scan, community)),
        _step("step_7", "Referral loop", "advocate", "referral",
              _link_sentence(referral, "A referral, affiliate, partner, or ambassador path suggests a deliberate advocacy loop.", "No referral or affiliate path was found from the homepage."),
              ["step_6"], [], ["Advocacy paths turn customer trust into distribution."],
              ["If referral is absent, the brand relies more on paid, content, and founder-led distribution."],
              "continuity", "Satisfied customers need a reason to share.", "Sharing becomes part of the customer identity.", "Refer, apply as a partner, or share proof.", bool(referral), "low", _evidence(scan, referral)),
    ]


def _offers_from_scan(scan: HomepageScan) -> list[Offer]:
    offers = []
    for name, words, offer_type, level, step_id in [
        ("Lead capture", PAGE_PATTERNS["lead_magnet"] + PAGE_PATTERNS["newsletter"], "lead_magnet", "solution_aware", "step_4"),
        ("Core offer", PAGE_PATTERNS["pricing"], "core_product", "most_aware", "step_5"),
        ("Sales call", PAGE_PATTERNS["demo"], "high_ticket", "most_aware", "step_5"),
    ]:
        match = _first_matching_link(scan.links, words)
        if not match:
            continue
        label, href = match
        offers.append(Offer(
            name=label or name,
            type=offer_type,
            headline_or_promise=f"Observed homepage path: {label or href}",
            target_awareness_level=level,
            price_usd=None,
            connected_step_id=step_id,
            is_observed=True,
            confidence="medium",
            evidence=[scan.url, href],
        ))
    if not offers:
        offers.append(Offer(
            name="Primary conversion offer",
            type="other",
            headline_or_promise="Not observed from the homepage crawl. Review the main CTA, product page, checkout, or booked-call path.",
            target_awareness_level="most_aware",
            price_usd=None,
            connected_step_id="step_5",
            is_observed=False,
            confidence="low",
            evidence=[scan.url] if scan.url else [],
        ))
    return offers


def _step(*args) -> JourneyStep:
    return JourneyStep(
        id=args[0], label=args[1], awareness_level=args[2], type=args[3],
        description=args[4], entry_from=args[5], exits_to=args[6],
        whats_working=args[7], whats_missing=args[8], value_ladder_rung=args[9],
        hook=args[10], story=args[11], offer_cta=args[12],
        is_observed=args[13], confidence=args[14], evidence=args[15],
    )


def _first_matching_link(links: list[tuple[str, str]], words: tuple[str, ...]) -> tuple[str, str] | None:
    for label, href in links:
        haystack = f"{label} {href}".lower()
        if any(word in haystack for word in words):
            return label, href
    return None


def _platform_for_url(url: str) -> str | None:
    low = url.lower()
    for platform, patterns in PLATFORM_PATTERNS.items():
        if any(pattern in low for pattern in patterns):
            return platform
    return None


def _dedupe_touchpoints(items: list[Touchpoint]) -> list[Touchpoint]:
    seen = set()
    clean = []
    for item in items:
        key = (item.platform, item.url)
        if key in seen:
            continue
        seen.add(key)
        clean.append(item)
    return clean[:16]


def _link_sentence(match: tuple[str, str] | None, yes: str, no: str) -> str:
    if not match:
        return no
    label, href = match
    return f"{yes} Observed path: {label} ({href})."


def _evidence(scan: HomepageScan, match: tuple[str, str] | None) -> list[str]:
    evidence = [scan.url] if scan.url else []
    if match:
        evidence.append(match[1])
    return evidence


def _infer_icp(text: str) -> str:
    if not text:
        return "Unknown from homepage-only scan."
    return "People or teams seeking the outcome promised on the homepage."


def _worth_stealing(scan: HomepageScan) -> list[str]:
    items = ["Use the homepage as a routing layer: education for cold visitors, direct CTA for high-intent buyers."]
    if _first_matching_link(scan.links, PAGE_PATTERNS["lead_magnet"] + PAGE_PATTERNS["newsletter"]):
        items.append("Capture non-buyers with a subscribe or free-resource path before they leave.")
    if _first_matching_link(scan.links, PAGE_PATTERNS["pricing"]):
        items.append("Make the buying path visible from the homepage so most-aware visitors do not hunt for it.")
    return items[:5]


def _learning_opportunities(scan: HomepageScan) -> list[str]:
    items = []
    if not _first_matching_link(scan.links, PAGE_PATTERNS["lead_magnet"] + PAGE_PATTERNS["newsletter"]):
        items.append("Add a low-friction lead capture path for visitors who are interested but not ready to buy.")
    if not _first_matching_link(scan.links, PAGE_PATTERNS["referral"]):
        items.append("Add or expose a referral loop so happy customers have a clear sharing path.")
    items.append("Instrument the funnel from homepage CTA to checkout or booked call before making channel changes.")
    return items[:5]


def _ascension_path(scan: HomepageScan) -> str:
    has_lead = bool(_first_matching_link(scan.links, PAGE_PATTERNS["lead_magnet"] + PAGE_PATTERNS["newsletter"]))
    has_offer = bool(_first_matching_link(scan.links, PAGE_PATTERNS["pricing"] + PAGE_PATTERNS["demo"]))
    parts = ["Public discovery"]
    parts.append("lead capture" if has_lead else "homepage consideration")
    parts.append("core offer or sales call" if has_offer else "unclear paid conversion path")
    parts.append("post-purchase onboarding")
    parts.append("referral loop")
    return " → ".join(parts)
