"""
HTML Report Renderer — pure Python, no LLM.
Converts FunnelMap -> standalone dark-mode HTML report with Mermaid.js diagrams.
Design: dark professional SaaS (Linear/Notion aesthetic) — FunnelTeardown brand.
"""
from html import escape
import base64
from urllib.parse import urlparse
from models.funnel_map import FunnelMap

# Awareness level color system — kept consistent throughout
AL_COLOR = {
    "unaware":        "#64748B",
    "problem_aware":  "#F59E0B",
    "solution_aware": "#3B82F6",
    "product_aware":  "#8B5CF6",
    "most_aware":     "#10B981",
    "customer":       "#059669",
    "advocate":       "#EC4899",
}

AL_BG = {
    "unaware":        "rgba(100,116,139,0.15)",
    "problem_aware":  "rgba(245,158,11,0.15)",
    "solution_aware": "rgba(59,130,246,0.15)",
    "product_aware":  "rgba(139,92,246,0.15)",
    "most_aware":     "rgba(16,185,129,0.15)",
    "customer":       "rgba(5,150,105,0.15)",
    "advocate":       "rgba(236,72,153,0.15)",
}

AL_LABEL = {
    "unaware":        "Unaware",
    "problem_aware":  "Problem Aware",
    "solution_aware": "Solution Aware",
    "product_aware":  "Product Aware",
    "most_aware":     "Most Aware",
    "customer":       "Customer",
    "advocate":       "Advocate",
}

VL_COLOR = {
    "free":        "#64748B",
    "entry":       "#3B82F6",
    "core":        "#10B981",
    "high_ticket": "#8B5CF6",
    "continuity":  "#F59E0B",
}

VL_LABEL = {
    "free":        "Free",
    "entry":       "Entry",
    "core":        "Core",
    "high_ticket": "High-Ticket",
    "continuity":  "Continuity",
}

STEP_TYPE_ICON = {
    "content": "▶",
    "landing_page": "⬛",
    "lead_magnet": "🎁",
    "email_sequence": "✉",
    "thank_you_page": "✓",
    "call": "📞",
    "checkout": "💳",
    "onboarding": "🚀",
    "referral": "↗",
    "live_event": "🎤",
    "other": "•",
}


def _al(obj) -> str:
    """Safely extract awareness level string from enum or str."""
    return obj.value if hasattr(obj, "value") else str(obj)


def _e(value) -> str:
    """Escape dynamic text before inserting into report HTML."""
    return escape(str(value or ""), quote=True)


def _source_label(url: str) -> str:
    parsed = urlparse(_normalize_url(url))
    host = parsed.netloc.replace("www.", "") or "source"
    path = parsed.path.strip("/")
    if not path:
        return host
    short_path = path[:42] + "..." if len(path) > 45 else path
    return f"{host}/{short_path}"


def _normalize_url(url: str) -> str:
    raw = str(url or "").strip()
    markdown_match = None
    if "](" in raw and raw.endswith(")"):
        markdown_match = raw.split("](", 1)[1][:-1].strip()
    normalized = markdown_match or raw
    if normalized and not normalized.startswith(("http://", "https://")):
        parsed = urlparse(normalized)
        if parsed.netloc or "." in parsed.path.split("/")[0]:
            normalized = f"https://{normalized}"
    return normalized


def _source_links_section(fm: FunnelMap) -> str:
    seen = set()
    links: list[tuple[str, str, str]] = []

    def add(url: str, label: str, context: str) -> None:
        url = _normalize_url(url)
        if not url or url in seen:
            return
        seen.add(url)
        links.append((url, label, context))

    add(fm.brand.website, _source_label(fm.brand.website), "Brand website")
    for url in fm.brand.evidence:
        add(url, _source_label(url), "Brand evidence")
    for t in fm.touchpoints:
        add(t.url, t.handle_or_name or _source_label(t.url), f"{AL_LABEL.get(_al(t.awareness_level), _al(t.awareness_level))} touchpoint")
        for url in t.evidence:
            add(url, _source_label(url), f"{t.handle_or_name} evidence")
    for step in fm.journey_steps:
        for url in step.evidence:
            add(url, _source_label(url), f"{step.label} evidence")
    for offer in fm.offers:
        for url in offer.evidence:
            add(url, _source_label(url), f"{offer.name} evidence")

    if not links:
        return '<p class="empty-note">No public source links were captured.</p>'

    items = "".join(
        f'<a class="source-link-card" href="{_e(url)}" target="_blank" rel="noopener noreferrer">'
        f'<span class="source-context">{_e(context)}</span>'
        f'<span class="source-title">{_e(label)}</span>'
        f'<span class="source-url">{_e(url)}</span>'
        f'</a>'
        for url, label, context in links
    )
    return f'<div class="source-grid">{items}</div>'


def _priority_takeaways(fm: FunnelMap) -> str:
    takeaways = []
    if fm.worth_stealing:
        takeaways.append(("Copy", fm.worth_stealing[0], "#22C55E"))
    if fm.learning_opportunities:
        takeaways.append(("Improve", fm.learning_opportunities[0], "#F59E0B"))
    if fm.ascension_path:
        takeaways.append(("Path", fm.ascension_path, "#3B82F6"))
    if fm.open_questions:
        takeaways.append(("Verify", fm.open_questions[0], "#8B5CF6"))

    if not takeaways:
        return '<p class="empty-note">No priority takeaways were generated.</p>'

    cards = "".join(
        f'<div class="takeaway-card" style="--takeaway-color:{color};">'
        f'<div class="takeaway-label">{_e(label)}</div>'
        f'<p>{_e(text)}</p>'
        f'</div>'
        for label, text, color in takeaways
    )
    return f'<div class="takeaway-grid">{cards}</div>'


def _score_band(score: int) -> tuple[str, str]:
    if score >= 85:
        return "A", "Scale"
    if score >= 70:
        return "B", "Tune"
    if score >= 55:
        return "C", "Repair"
    if score >= 40:
        return "D", "Rebuild"
    return "F", "Diagnose"


def _clamp_score(value: float) -> int:
    return max(0, min(100, round(value)))


def _scorecard_metrics(fm: FunnelMap) -> list[dict]:
    observed_steps = sum(1 for s in fm.journey_steps if s.is_observed)
    observed_touchpoints = sum(1 for t in fm.touchpoints if t.is_observed)
    observed_offers = sum(1 for o in fm.offers if o.is_observed)
    levels = {_al(t.awareness_level) for t in fm.touchpoints}
    step_levels = {_al(s.awareness_level) for s in fm.journey_steps}
    rungs = {
        (s.value_ladder_rung.value if hasattr(s.value_ladder_rung, "value") else str(s.value_ladder_rung))
        for s in fm.journey_steps
        if s.value_ladder_rung
    }
    offer_types = {
        (o.type.value if hasattr(o.type, "value") else str(o.type))
        for o in fm.offers
    }
    steps_with_hso = sum(
        1 for s in fm.journey_steps if s.hook.strip() and s.story.strip() and s.offer_cta.strip()
    )
    steps_with_exits = sum(1 for s in fm.journey_steps if s.exits_to)
    steps_with_working = sum(1 for s in fm.journey_steps if s.whats_working)
    steps_with_missing = sum(1 for s in fm.journey_steps if s.whats_missing)

    journey_score = _clamp_score(
        (len(step_levels) / 7 * 42)
        + (observed_steps / max(len(fm.journey_steps), 1) * 28)
        + (steps_with_exits / max(len(fm.journey_steps), 1) * 30)
    )
    offer_score = _clamp_score(
        (min(len(fm.offers), 4) / 4 * 34)
        + (len(rungs) / 5 * 26)
        + (observed_offers / max(len(fm.offers), 1) * 20 if fm.offers else 0)
        + (20 if {"subscription", "high_ticket", "upsell"} & offer_types else 0)
    )
    conversion_score = _clamp_score(
        (steps_with_hso / max(len(fm.journey_steps), 1) * 45)
        + (steps_with_working / max(len(fm.journey_steps), 1) * 20)
        + (steps_with_missing / max(len(fm.journey_steps), 1) * 20)
        + (15 if fm.ascension_path else 0)
    )
    evidence_score = _clamp_score(
        (observed_touchpoints / max(len(fm.touchpoints), 1) * 40 if fm.touchpoints else 0)
        + (len(levels) / 7 * 30)
        + (min(len(_collect_urls(fm)), 12) / 12 * 30)
    )
    loop_score = _clamp_score(
        (25 if "customer" in levels or "customer" in step_levels else 0)
        + (25 if "advocate" in levels or "advocate" in step_levels else 0)
        + (25 if "continuity" in rungs or "subscription" in offer_types else 0)
        + (25 if any("referr" in s.label.lower() or s.type == "referral" for s in fm.journey_steps) else 0)
    )

    return [
        {
            "label": "Journey Coverage",
            "score": journey_score,
            "why": f"{len(step_levels)} of 7 awareness stages mapped, {observed_steps} observed journey steps.",
        },
        {
            "label": "Offer Ladder",
            "score": offer_score,
            "why": f"{len(fm.offers)} offers across {len(rungs)} value-ladder rungs.",
        },
        {
            "label": "Conversion Clarity",
            "score": conversion_score,
            "why": f"{steps_with_hso} steps include hook, story, and offer/CTA.",
        },
        {
            "label": "Evidence Quality",
            "score": evidence_score,
            "why": f"{observed_touchpoints} observed touchpoints and {len(_collect_urls(fm))} unique source URLs.",
        },
        {
            "label": "Retention Loop",
            "score": loop_score,
            "why": "Checks for customer, advocate, continuity, and referral signals.",
        },
    ]


def _collect_urls(fm: FunnelMap) -> list[str]:
    seen = set()
    urls = []

    def add(url: str) -> None:
        if url and url not in seen:
            seen.add(url)
            urls.append(url)

    add(fm.brand.website)
    for url in fm.brand.evidence:
        add(url)
    for touchpoint in fm.touchpoints:
        add(touchpoint.url)
        for url in touchpoint.evidence:
            add(url)
    for step in fm.journey_steps:
        for url in step.evidence:
            add(url)
    for offer in fm.offers:
        for url in offer.evidence:
            add(url)
    return urls


def _game_scorecard(fm: FunnelMap) -> tuple[str, int, str]:
    metrics = _scorecard_metrics(fm)
    overall = _clamp_score(sum(m["score"] for m in metrics) / max(len(metrics), 1))
    grade, mode = _score_band(overall)

    rows = "".join(
        f'<div class="score-row">'
        f'<div class="score-row-head">'
        f'<span>{_e(metric["label"])}</span>'
        f'<strong>{metric["score"]}</strong>'
        f'</div>'
        f'<div class="score-track"><span style="width:{metric["score"]}%;"></span></div>'
        f'<p>{_e(metric["why"])}</p>'
        f'</div>'
        for metric in metrics
    )

    lowest = min(metrics, key=lambda m: m["score"]) if metrics else {"label": "Evidence Quality", "score": 0}
    html = f"""
<div class="scorecard">
  <div class="score-main">
    <div class="score-kicker">Game Scorecard</div>
    <div class="score-number">{overall}</div>
    <div class="score-grade">Grade {_e(grade)} · {_e(mode)} mode</div>
    <p>Score is based on mapped evidence, full-journey coverage, offer depth, CTA clarity, and retention loops.</p>
    <div class="score-next">Next move: improve <strong>{_e(lowest["label"])}</strong> first.</div>
  </div>
  <div class="score-rows">{rows}</div>
</div>"""
    return html, overall, grade


def _conf_badge(conf: str) -> str:
    color_map = {"high": "#22C55E", "medium": "#F59E0B", "low": "#EF4444"}
    c = color_map.get(str(conf), "#94A3B8")
    return (
        f'<span style="display:inline-flex;align-items:center;gap:4px;'
        f'font-size:11px;font-weight:500;color:{c};'
        f'background:{c}22;padding:2px 8px;border-radius:20px;">'
        f'<span style="width:5px;height:5px;border-radius:50%;background:{c};display:inline-block;"></span>'
        f'{_e(conf)} confidence</span>'
    )


def _observed_badge(is_observed: bool) -> str:
    if is_observed:
        return ('<span style="font-size:11px;font-weight:500;color:#22C55E;'
                'background:#22C55E22;padding:2px 8px;border-radius:20px;">Observed</span>')
    return ('<span style="font-size:11px;font-weight:500;color:#F59E0B;'
            'background:#F59E0B22;padding:2px 8px;border-radius:20px;">Inferred</span>')


def _mermaid_flowchart(steps: list) -> str:
    if not steps:
        return "flowchart LR\n    A[No steps mapped yet]"
    lines = ["flowchart LR"]
    for step in steps:
        label = step.label.replace('"', "'").replace("\n", " ")
        al = _al(step.awareness_level)
        al_text = AL_LABEL.get(al, al)
        suffix = "" if step.is_observed else " ◦"
        lines.append(f'    {_mermaid_id(step.id)}["{label}\\n{al_text}{suffix}"]')
    for step in steps:
        for exit_id in step.exits_to:
            lines.append(f"    {_mermaid_id(step.id)} --> {_mermaid_id(exit_id)}")
    for step in steps:
        al = _al(step.awareness_level)
        c = AL_COLOR.get(al, "#94A3B8")
        lines.append(f"    style {_mermaid_id(step.id)} fill:{c}33,stroke:{c},stroke-width:2px,color:#F1F5F9")
    return "\n".join(lines)


def _mermaid_id(value: str) -> str:
    clean = "".join(c if c.isalnum() or c == "_" else "_" for c in str(value or "step"))
    return clean or "step"


def _coverage_grid(fm: FunnelMap) -> str:
    by_level: dict = {}
    for t in fm.touchpoints:
        al = _al(t.awareness_level)
        by_level.setdefault(al, []).append(t)

    cards = []
    for level in ["unaware", "problem_aware", "solution_aware",
                  "product_aware", "most_aware", "customer", "advocate"]:
        touchpoints = by_level.get(level, [])
        color = AL_COLOR.get(level, "#94A3B8")
        bg = AL_BG.get(level, "rgba(148,163,184,0.1)")
        label = AL_LABEL.get(level, level)
        filled = bool(touchpoints)
        opacity = "1" if filled else "0.4"

        if filled:
            items = "".join(
                f'<a href="{_e(_normalize_url(t.url))}" target="_blank" style="display:block;color:#94A3B8;'
                f'font-size:12px;text-decoration:none;margin-top:4px;'
                f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" '
                f'title="{_e(t.handle_or_name)}">'
                f'<span style="color:{color};">▸</span> {_e(t.handle_or_name)}</a>'
                for t in touchpoints
            )
        else:
            items = '<span style="color:#374151;font-size:12px;">No touchpoint mapped</span>'

        cards.append(
            f'<div style="background:{bg};border:1px solid {color}44;border-radius:10px;'
            f'padding:14px 16px;opacity:{opacity};">'
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">'
            f'<span style="width:8px;height:8px;border-radius:50%;background:{color};flex-shrink:0;"></span>'
            f'<span style="font-size:12px;font-weight:600;color:{color};text-transform:uppercase;'
            f'letter-spacing:0.05em;">{_e(label)}</span>'
            f'</div>'
            f'{items}'
            f'</div>'
        )

    return (
        '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));'
        'gap:12px;margin:16px 0;">' + "".join(cards) + "</div>"
    )


def _step_cards(steps: list) -> str:
    cards = []
    for i, step in enumerate(steps):
        al = _al(step.awareness_level)
        al_label = AL_LABEL.get(al, al)
        color = AL_COLOR.get(al, "#94A3B8")
        bg = AL_BG.get(al, "rgba(148,163,184,0.1)")
        conf_v = step.confidence.value if hasattr(step.confidence, "value") else str(step.confidence)
        type_v = step.type.value if hasattr(step.type, "value") else str(step.type)
        icon = STEP_TYPE_ICON.get(type_v, "•")

        # Brunson fields
        rung_v = step.value_ladder_rung.value if hasattr(step.value_ladder_rung, "value") else str(step.value_ladder_rung or "free")
        vl_badge = _vl_rung_badge(rung_v)
        hso_html = _hso_row(step.hook or "", step.story or "", step.offer_cta or "")

        working_items = "".join(
            f'<li style="margin-bottom:6px;padding-left:4px;">{_e(w)}</li>'
            for w in step.whats_working
        ) or '<li style="color:#4B5563;">—</li>'

        missing_items = "".join(
            f'<li style="margin-bottom:6px;padding-left:4px;">{_e(m)}</li>'
            for m in step.whats_missing
        ) or '<li style="color:#4B5563;">—</li>'

        evidence_links = " ".join(
            f'<a href="{_e(_normalize_url(e))}" target="_blank" style="color:#3B82F6;font-size:11px;'
            f'text-decoration:none;padding:2px 6px;background:#3B82F611;border-radius:4px;">'
            f'source {j+1}</a>'
            for j, e in enumerate(step.evidence)
        )

        exits = ", ".join(f'<code style="background:#1E2333;padding:1px 5px;border-radius:3px;'
                          f'font-size:11px;color:#94A3B8;">{_e(e)}</code>'
                          for e in step.exits_to) or "—"

        cards.append(f"""
<div style="background:#13151F;border:1px solid #1E2333;border-radius:12px;
     overflow:hidden;margin-bottom:16px;">
  <div style="background:{bg};border-bottom:1px solid {color}33;padding:16px 20px;
       display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap;">
    <div style="display:flex;align-items:center;gap:12px;">
      <div style="width:32px;height:32px;border-radius:8px;background:{color}22;border:1px solid {color}44;
           display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0;">
        {icon}
      </div>
      <div>
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
          <span style="font-size:11px;font-weight:600;letter-spacing:0.08em;
               text-transform:uppercase;color:{color};">{_e(al_label)}</span>
          <span style="color:#374151;font-size:11px;">·</span>
          <span style="font-size:11px;color:#64748B;">{_e(type_v.replace("_"," "))}</span>
          <span style="color:#374151;font-size:11px;">·</span>
          {vl_badge}
        </div>
        <h3 style="margin:4px 0 0;font-size:15px;font-weight:600;color:#F1F5F9;line-height:1.3;">
          {_e(step.label)}
        </h3>
      </div>
    </div>
    <div style="display:flex;gap:6px;flex-wrap:wrap;flex-shrink:0;">
      {_observed_badge(step.is_observed)}
      {_conf_badge(conf_v)}
    </div>
  </div>

  <div style="padding:16px 20px;">
    <p style="color:#94A3B8;font-size:14px;margin:0 0 16px;line-height:1.6;">{_e(step.description)}</p>

    {hso_html}

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px;">
      <div style="background:#0C1A0F;border:1px solid #166534;border-radius:8px;padding:14px;">
        <div style="font-size:12px;font-weight:600;color:#22C55E;margin-bottom:10px;
             display:flex;align-items:center;gap:6px;">
          <span style="font-size:14px;">✓</span> What's Working
        </div>
        <ul style="margin:0;padding-left:16px;color:#D1FAE5;font-size:13px;line-height:1.6;">
          {working_items}
        </ul>
      </div>
      <div style="background:#1A0E06;border:1px solid #92400E;border-radius:8px;padding:14px;">
        <div style="font-size:12px;font-weight:600;color:#F59E0B;margin-bottom:10px;
             display:flex;align-items:center;gap:6px;">
          <span style="font-size:14px;">⚡</span> What's Missing
        </div>
        <ul style="margin:0;padding-left:16px;color:#FDE68A;font-size:13px;line-height:1.6;">
          {missing_items}
        </ul>
      </div>
    </div>

    <div style="margin-top:12px;display:flex;align-items:center;justify-content:space-between;
         flex-wrap:wrap;gap:8px;">
      <div style="font-size:12px;color:#4B5563;">
        Exits to: {exits}
      </div>
      <div style="display:flex;gap:6px;">{evidence_links}</div>
    </div>
  </div>
</div>""")
    return "\n".join(cards)


def _offers_section(fm: FunnelMap) -> str:
    if not fm.offers:
        return '<p style="color:#4B5563;font-size:14px;">No offers identified.</p>'

    cards = []
    for o in fm.offers:
        al = _al(o.target_awareness_level)
        al_label = AL_LABEL.get(al, al)
        color = AL_COLOR.get(al, "#94A3B8")
        bg = AL_BG.get(al, "rgba(148,163,184,0.1)")
        price = f"${o.price_usd:.0f}" if o.price_usd is not None else "—"
        conf_v = o.confidence.value if hasattr(o.confidence, "value") else str(o.confidence)
        type_v = o.type.value if hasattr(o.type, "value") else str(o.type)

        cards.append(f"""
<div style="background:#13151F;border:1px solid #1E2333;border-radius:12px;
     padding:20px;display:flex;justify-content:space-between;align-items:flex-start;
     gap:16px;flex-wrap:wrap;margin-bottom:12px;">
  <div style="flex:1;min-width:200px;">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;flex-wrap:wrap;">
      <span style="font-size:13px;font-weight:700;color:#F1F5F9;">{_e(o.name)}</span>
      <span style="font-size:11px;color:#64748B;background:#1E2333;padding:2px 8px;
           border-radius:4px;">{_e(type_v.replace("_"," "))}</span>
      {_observed_badge(o.is_observed)}
    </div>
    <p style="margin:0 0 8px;color:#94A3B8;font-size:13px;font-style:italic;line-height:1.5;">
      "{_e(o.headline_or_promise)}"
    </p>
    <div style="font-size:12px;color:#4B5563;">
      Connected to: <code style="background:#1E2333;padding:1px 5px;border-radius:3px;
      color:#94A3B8;">{_e(o.connected_step_id)}</code>
    </div>
  </div>
  <div style="display:flex;flex-direction:column;align-items:flex-end;gap:8px;flex-shrink:0;">
    <div style="font-size:24px;font-weight:700;color:#F1F5F9;">{price}</div>
    <span style="font-size:11px;font-weight:600;color:{color};background:{bg};
         padding:4px 10px;border-radius:20px;border:1px solid {color}33;">{_e(al_label)}</span>
    {_conf_badge(conf_v)}
  </div>
</div>""")

    return "\n".join(cards)


def _value_ladder_bar(steps: list, ascension_path: str) -> str:
    """Visual horizontal value ladder showing which rungs are present + ascension path sentence."""
    present_rungs: set = set()
    for step in steps:
        rung = getattr(step, "value_ladder_rung", None)
        if rung:
            rung_v = rung.value if hasattr(rung, "value") else str(rung)
            present_rungs.add(rung_v)

    rung_order = ["free", "entry", "core", "high_ticket", "continuity"]
    rung_cells = []
    for rung in rung_order:
        color = VL_COLOR.get(rung, "#64748B")
        label = VL_LABEL.get(rung, rung)
        filled = rung in present_rungs
        bg = f"{color}22" if filled else "#13151F"
        border = f"1px solid {color}66" if filled else "1px solid #1E2333"
        text_color = color if filled else "#374151"
        dot = f'<span style="width:7px;height:7px;border-radius:50%;background:{color};display:inline-block;margin-right:5px;opacity:{1 if filled else 0.3};"></span>'
        rung_cells.append(
            f'<div style="flex:1;text-align:center;padding:10px 8px;background:{bg};'
            f'border:{border};border-radius:8px;">'
            f'<div style="font-size:11px;font-weight:600;color:{text_color};'
            f'display:flex;align-items:center;justify-content:center;">'
            f'{dot}{_e(label)}</div></div>'
        )
    arrow = '<div style="color:#374151;font-size:14px;align-self:center;flex-shrink:0;">→</div>'
    ladder_html = arrow.join(rung_cells)

    path_html = (
        f'<div style="margin-top:12px;padding:12px 16px;background:#13151F;border:1px solid #1E2333;'
        f'border-radius:8px;font-size:13px;color:#94A3B8;font-style:italic;line-height:1.5;">'
        f'<span style="font-size:11px;font-weight:600;color:#4B5563;text-transform:uppercase;'
        f'letter-spacing:0.06em;font-style:normal;">Ascension Path → </span>{_e(ascension_path)}</div>'
        if ascension_path else ""
    )

    return (
        f'<div style="display:flex;align-items:stretch;gap:6px;margin-bottom:4px;">'
        f'{ladder_html}</div>{path_html}'
    )


def _hso_row(hook: str, story: str, offer_cta: str) -> str:
    """Hook → Story → Offer 3-cell inline breakdown row."""
    if not any([hook, story, offer_cta]):
        return ""

    def cell(icon, title, body, accent):
        body_text = body or '<span style="color:#374151;font-style:italic;">Not identified</span>'
        return (
            f'<div style="background:#0C0E17;border:1px solid {accent}33;border-radius:8px;padding:12px 14px;">'
            f'<div style="font-size:11px;font-weight:600;color:{accent};margin-bottom:6px;'
            f'display:flex;align-items:center;gap:5px;text-transform:uppercase;letter-spacing:0.06em;">'
            f'<span>{icon}</span>{title}</div>'
            f'<p style="margin:0;font-size:13px;color:#94A3B8;line-height:1.5;">{body_text if body_text.startswith("<span") else _e(body_text)}</p>'
            f'</div>'
        )

    return (
        f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:12px;">'
        f'{cell("🪝", "Hook", hook, "#F59E0B")}'
        f'{cell("📖", "Story", story, "#3B82F6")}'
        f'{cell("⚡", "Offer / CTA", offer_cta, "#22C55E")}'
        f'</div>'
    )


def _vl_rung_badge(rung: str) -> str:
    color = VL_COLOR.get(rung, "#64748B")
    label = VL_LABEL.get(rung, rung)
    return (
        f'<span style="font-size:10px;font-weight:700;color:{color};'
        f'background:{color}22;padding:2px 8px;border-radius:20px;'
        f'border:1px solid {color}44;text-transform:uppercase;letter-spacing:0.05em;">'
        f'◈ {label}</span>'
    )


def _recap_section(worth_stealing: list, learning_opportunities: list) -> str:
    steal_cards = "".join(
        f'<div style="background:#0C1A0F;border:1px solid #166534;border-radius:10px;'
        f'padding:16px 18px;display:flex;gap:14px;align-items:flex-start;">'
        f'<span style="font-size:18px;flex-shrink:0;">✦</span>'
        f'<p style="margin:0;color:#D1FAE5;font-size:14px;line-height:1.6;">{_e(t)}</p>'
        f'</div>'
        for t in worth_stealing
    ) or '<p style="color:#4B5563;font-size:14px;">—</p>'

    learn_cards = "".join(
        f'<div style="background:#1A0E06;border:1px solid #92400E;border-radius:10px;'
        f'padding:16px 18px;display:flex;gap:14px;align-items:flex-start;">'
        f'<span style="font-size:18px;flex-shrink:0;">⚠</span>'
        f'<p style="margin:0;color:#FDE68A;font-size:14px;line-height:1.6;">{_e(l)}</p>'
        f'</div>'
        for l in learning_opportunities
    ) or '<p style="color:#4B5563;font-size:14px;">—</p>'

    return f"""
<div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-top:4px;">
  <div>
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid #166534;">
      <span style="font-size:14px;">✦</span>
      <span style="font-size:14px;font-weight:600;color:#22C55E;">Worth Stealing</span>
      <span style="font-size:12px;color:#4B5563;background:#1E2333;padding:2px 8px;border-radius:20px;">{len(worth_stealing)}</span>
    </div>
    <div style="display:flex;flex-direction:column;gap:10px;">{steal_cards}</div>
  </div>
  <div>
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid #92400E;">
      <span style="font-size:14px;">⚠</span>
      <span style="font-size:14px;font-weight:600;color:#F59E0B;">Learning Opportunities</span>
      <span style="font-size:12px;color:#4B5563;background:#1E2333;padding:2px 8px;border-radius:20px;">{len(learning_opportunities)}</span>
    </div>
    <div style="display:flex;flex-direction:column;gap:10px;">{learn_cards}</div>
  </div>
</div>"""


def _open_questions_section(questions: list) -> str:
    if not questions:
        return '<p style="color:#22C55E;font-size:14px;">No open questions — excellent coverage.</p>'
    items = "".join(
        f'<li style="margin-bottom:12px;padding:14px 16px;background:#13151F;'
        f'border:1px solid #1E2333;border-left:3px solid #3B82F6;border-radius:0 8px 8px 0;'
        f'color:#94A3B8;font-size:14px;line-height:1.6;">{_e(q)}</li>'
        for q in questions
    )
    return f'<ol style="padding-left:24px;list-style:decimal;">{items}</ol>'


def render_html(fm: FunnelMap) -> str:
    """Render a FunnelMap to a standalone HTML report with dark/light mode support."""
    flowchart = _mermaid_flowchart(fm.journey_steps)
    coverage_html = _coverage_grid(fm)
    steps_html = _step_cards(fm.journey_steps)
    offers_html = _offers_section(fm)
    open_q_html = _open_questions_section(fm.open_questions)
    recap_html = _recap_section(fm.worth_stealing, fm.learning_opportunities)
    vl_bar_html = _value_ladder_bar(fm.journey_steps, fm.ascension_path)
    sources_html = _source_links_section(fm)
    takeaways_html = _priority_takeaways(fm)
    scorecard_html, game_score, game_grade = _game_scorecard(fm)

    meta = fm.run_metadata
    cost_str = f"${meta.total_cost_usd:.4f}"
    duration_str = f"{meta.duration_seconds:.0f}s"
    brand = fm.brand

    # Use brand's theme color if extracted from homepage, else a restrained system blue.
    accent = (brand.theme_color or "#0071E3").strip()
    # Derive a slightly darker shade for hover states (just use the same with opacity adjustments)
    accent_dim = accent + "22"
    accent_mid = accent + "44"
    accent_str = accent + "33"

    n_steps = len(fm.journey_steps)
    n_touchpoints = len(fm.touchpoints)
    n_offers = len(fm.offers)
    n_questions = len(fm.open_questions)

    agent_rows = "".join(
        f'<tr style="border-bottom:1px solid #1E2333;">'
        f'<td style="padding:10px 16px;color:#94A3B8;font-size:13px;">{_e(agent)}</td>'
        f'<td style="padding:10px 16px;color:#64748B;font-size:12px;">'
        f'<code style="background:#1E2333;padding:2px 6px;border-radius:4px;">'
            f'{_e(meta.model_used.get(agent, "—"))}</code></td>'
        f'<td style="padding:10px 16px;color:#22C55E;font-size:13px;font-weight:500;">'
        f'${cost:.4f}</td></tr>'
        for agent, cost in meta.agent_costs.items()
    )

    evidence_links = " ".join(
        f'<a href="{_e(_normalize_url(e))}" target="_blank" style="color:#3B82F6;font-size:12px;'
        f'text-decoration:none;">[{i+1}]</a>'
        for i, e in enumerate(brand.evidence)
    ) or "—"

    founder_row = (
        f'<div class="brand-row">'
        f'<span class="brand-row-label">Founder</span>'
        f'<span class="brand-row-value">{_e(brand.founder)}</span></div>'
        if brand.founder else ""
    )

    logo_html = (
        f'<img src="{_e(brand.logo_url)}" alt="{_e(brand.name)} logo" '
        f'style="max-height:48px;max-width:120px;object-fit:contain;'
        f'border-radius:8px;margin-bottom:12px;">'
        if brand.logo_url else ""
    )

    conf_v = brand.confidence.value if hasattr(brand.confidence, "value") else str(brand.confidence)

    safe_brand_filename = "".join(
        c if c.isalnum() or c in "-_ " else "" for c in brand.name
    ).strip().replace(" ", "-") or "Report"
    report_filename = f"FunnelTeardown-{safe_brand_filename}.html"
    json_filename = f"FunnelTeardown-{safe_brand_filename}.json"
    report_json_b64 = base64.b64encode(
        fm.model_dump_json(indent=2).encode("utf-8")
    ).decode("ascii")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>FunnelTeardown — {_e(brand.name)}</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
  <script>
    mermaid.initialize({{
      startOnLoad: true,
      theme: 'dark',
      themeVariables: {{
        background: '#0C0E17',
        primaryColor: '#13151F',
        primaryTextColor: '#F1F5F9',
        lineColor: '#334155',
        edgeLabelBackground: '#13151F',
        secondaryColor: '#1E2333',
        tertiaryColor: '#1E2333',
        fontSize: '13px'
      }},
      flowchart: {{ curve: 'basis', useMaxWidth: true }}
    }});
  </script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
      --bg: #0C0E17;
      --surface: #13151F;
      --border: #1E2333;
      --border-strong: #2E3347;
      --text: #F1F5F9;
      --text-secondary: #94A3B8;
      --text-muted: #4B5563;
      --accent: {accent};
      --accent-dim: {accent_dim};
      --accent-mid: {accent_mid};
      --accent-str: {accent_str};
      --scheme: dark;
    }}

    /* Light mode via media query */
    @media (prefers-color-scheme: light) {{
      :root:not([data-theme="dark"]) {{
        --bg: #F8FAFC;
        --surface: #FFFFFF;
        --border: #E2E8F0;
        --border-strong: #CBD5E1;
        --text: #0F172A;
        --text-secondary: #475569;
        --text-muted: #94A3B8;
        --scheme: light;
      }}
    }}

    /* Explicit light mode via toggle */
    :root[data-theme="light"] {{
      --bg: #F8FAFC;
      --surface: #FFFFFF;
      --border: #E2E8F0;
      --border-strong: #CBD5E1;
      --text: #0F172A;
      --text-secondary: #475569;
      --text-muted: #94A3B8;
      --scheme: light;
    }}

    /* Explicit dark mode via toggle (overrides media query) */
    :root[data-theme="dark"] {{
      --bg: #0C0E17;
      --surface: #13151F;
      --border: #1E2333;
      --border-strong: #2E3347;
      --text: #F1F5F9;
      --text-secondary: #94A3B8;
      --text-muted: #4B5563;
      --scheme: dark;
    }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Helvetica Neue", Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      line-height: 1.6;
    }}

    html {{
      scroll-behavior: smooth;
    }}

    p, li {{
      max-width: 76ch;
    }}

    /* Sticky header */
    .topbar {{
      position: sticky;
      top: 0;
      z-index: 100;
      background: rgba(12,14,23,0.92);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border);
      padding: 0 24px;
      height: 56px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }}

    :root[data-theme="light"] .topbar {{
      background: rgba(248,250,252,0.92);
    }}

    .topbar-left {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}

    .topbar-logo {{
      font-size: 13px;
      font-weight: 700;
      color: var(--text-muted);
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }}

    .theme-toggle {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 7px;
      padding: 5px 10px;
      font-size: 13px;
      cursor: pointer;
      color: var(--text-secondary);
      transition: background 0.15s, color 0.15s;
    }}
    .theme-toggle:hover {{ background: var(--border); color: var(--text); }}

    .action-link {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 7px;
      padding: 5px 10px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      color: var(--text-secondary);
      text-decoration: none;
      transition: background 0.15s, color 0.15s, border-color 0.15s;
    }}

    .action-link:hover {{
      background: var(--accent-dim);
      border-color: var(--accent-mid);
      color: var(--text);
      text-decoration: none;
    }}

    .topbar-divider {{
      width: 1px;
      height: 20px;
      background: var(--border-strong);
    }}

    .topbar-brand {{
      font-size: 15px;
      font-weight: 600;
      color: var(--text);
    }}

    .topbar-right {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}

    .pill {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 4px 10px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 500;
    }}

    .pill-cost {{
      background: #22C55E22;
      color: #22C55E;
      border: 1px solid #22C55E33;
    }}

    .pill-time {{
      background: var(--surface);
      color: var(--text-secondary);
      border: 1px solid var(--border);
    }}

    /* Nav tabs */
    .section-nav {{
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 0 24px;
      display: flex;
      gap: 0;
      overflow-x: auto;
      scrollbar-width: none;
    }}
    .section-nav::-webkit-scrollbar {{ display: none; }}

    .nav-tab {{
      padding: 12px 16px;
      font-size: 13px;
      font-weight: 500;
      color: var(--text-muted);
      text-decoration: none;
      white-space: nowrap;
      border-bottom: 2px solid transparent;
      transition: color 0.15s, border-color 0.15s;
    }}
    .nav-tab:hover {{ color: var(--text-secondary); }}

    /* Main layout */
    .main {{
      max-width: 1080px;
      margin: 0 auto;
      padding: 32px 24px 80px;
    }}

    .read-first {{
      background: linear-gradient(135deg, var(--accent-dim), transparent 58%), var(--surface);
      border: 1px solid var(--border-strong);
      border-radius: 14px;
      padding: 24px;
      margin-bottom: 28px;
    }}

    .read-first h1 {{
      font-size: 26px;
      line-height: 1.15;
      margin-bottom: 8px;
      letter-spacing: 0;
    }}

    .read-first p {{
      color: var(--text-secondary);
      font-size: 15px;
      margin: 0;
    }}

    .takeaway-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
      margin-top: 18px;
    }}

    .takeaway-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-left: 4px solid var(--takeaway-color);
      border-radius: 10px;
      padding: 14px 16px;
    }}

    .takeaway-label {{
      color: var(--takeaway-color);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 6px;
    }}

    .takeaway-card p {{
      color: var(--text-secondary);
      font-size: 13px;
      line-height: 1.5;
      margin: 0;
    }}

    .scorecard {{
      display: grid;
      grid-template-columns: 280px 1fr;
      gap: 16px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 16px;
      margin-bottom: 32px;
    }}

    .score-main {{
      border-radius: 12px;
      background: linear-gradient(160deg, var(--accent-dim), transparent 70%), var(--bg);
      border: 1px solid var(--border);
      padding: 18px;
    }}

    .score-kicker {{
      color: var(--text-muted);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 8px;
    }}

    .score-number {{
      color: var(--text);
      font-size: 56px;
      font-weight: 800;
      line-height: 0.95;
      letter-spacing: 0;
    }}

    .score-grade {{
      color: var(--accent);
      font-size: 13px;
      font-weight: 750;
      margin-top: 8px;
    }}

    .score-main p {{
      color: var(--text-secondary);
      font-size: 13px;
      line-height: 1.5;
      margin-top: 12px;
    }}

    .score-next {{
      color: var(--text-secondary);
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 9px;
      font-size: 13px;
      line-height: 1.45;
      margin-top: 14px;
      padding: 10px 12px;
    }}

    .score-next strong {{
      color: var(--text);
    }}

    .score-rows {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 10px;
    }}

    .score-row {{
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 13px 14px;
    }}

    .score-row-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 8px;
    }}

    .score-row-head span {{
      color: var(--text);
      font-size: 13px;
      font-weight: 700;
    }}

    .score-row-head strong {{
      color: var(--accent);
      font-size: 16px;
    }}

    .score-track {{
      height: 7px;
      background: var(--border);
      border-radius: 999px;
      overflow: hidden;
      margin-bottom: 8px;
    }}

    .score-track span {{
      display: block;
      height: 100%;
      background: linear-gradient(90deg, var(--accent), #22C55E);
      border-radius: inherit;
    }}

    .score-row p {{
      color: var(--text-muted);
      font-size: 12px;
      line-height: 1.45;
      margin: 0;
    }}

    /* Hero stats */
    .stats-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
      gap: 12px;
      margin-bottom: 40px;
    }}

    .stat-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
    }}

    .stat-value {{
      font-size: 28px;
      font-weight: 700;
      color: var(--text);
      line-height: 1;
      margin-bottom: 6px;
    }}

    .stat-label {{
      font-size: 12px;
      color: var(--text-muted);
      font-weight: 500;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}

    /* Section headers */
    .section {{
      margin-bottom: 48px;
    }}

    .section-header {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 20px;
      padding-bottom: 14px;
      border-bottom: 1px solid var(--border);
    }}

    .section-icon {{
      width: 28px;
      height: 28px;
      border-radius: 7px;
      background: var(--accent-dim);
      border: 1px solid var(--accent-mid);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 13px;
      flex-shrink: 0;
    }}

    .section-title {{
      font-size: 16px;
      font-weight: 600;
      color: var(--text);
    }}

    .section-count {{
      font-size: 12px;
      color: var(--text-muted);
      background: var(--border);
      padding: 2px 8px;
      border-radius: 20px;
    }}

    .section-desc {{
      font-size: 13px;
      color: var(--text-muted);
      margin-bottom: 16px;
    }}

    /* Brand card */
    .brand-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 24px;
    }}

    .brand-name {{
      font-size: 22px;
      font-weight: 700;
      color: var(--text);
      margin-bottom: 4px;
    }}

    .brand-website {{
      color: var(--accent);
      font-size: 13px;
      text-decoration: none;
    }}
    .brand-website:hover {{ text-decoration: underline; }}

    .brand-meta {{
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin-top: 16px;
    }}

    .brand-row {{
      display: flex;
      gap: 12px;
    }}

    .brand-row-label {{
      color: var(--text-muted);
      font-size: 13px;
      min-width: 100px;
      flex-shrink: 0;
    }}

    .brand-row-value {{
      color: var(--text-secondary);
      font-size: 13px;
      line-height: 1.5;
    }}

    /* Mermaid container */
    .mermaid-wrap {{
      background: #0C0E17;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 24px;
      overflow-x: auto;
    }}

    /* Run details table */
    .run-table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: hidden;
    }}

    .run-table th {{
      background: #1E2333;
      padding: 10px 16px;
      text-align: left;
      font-size: 11px;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}

    :root[data-theme="light"] .run-table th {{
      background: #F1F5F9;
    }}

    .source-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 10px;
    }}

    .source-link-card {{
      display: block;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 13px 14px;
      text-decoration: none;
      overflow: hidden;
    }}

    .source-link-card:hover {{
      border-color: var(--accent-mid);
      background: var(--accent-dim);
      text-decoration: none;
    }}

    .source-context {{
      display: block;
      color: var(--text-muted);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      margin-bottom: 3px;
    }}

    .source-title {{
      display: block;
      color: var(--text);
      font-size: 13px;
      font-weight: 650;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    .source-url {{
      display: block;
      color: var(--text-muted);
      font-size: 12px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      margin-top: 2px;
    }}

    .empty-note {{
      color: var(--text-muted);
      font-size: 14px;
    }}

    a {{ color: var(--accent); }}

    @media (max-width: 640px) {{
      .topbar {{
        height: auto;
        align-items: flex-start;
        padding: 12px 16px;
        flex-direction: column;
      }}
      .topbar-left, .topbar-right {{
        width: 100%;
        flex-wrap: wrap;
      }}
      .topbar-right .pill-time {{ display: none; }}
      .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
      .scorecard {{ grid-template-columns: 1fr; }}
      .main {{ padding: 24px 16px 64px; }}
      .read-first h1 {{ font-size: 22px; }}
    }}

    @media print {{
      .topbar, .section-nav, footer {{
        display: none;
      }}
      body {{
        background: #fff;
        color: #111827;
      }}
      .main {{
        max-width: none;
        padding: 0;
      }}
      .section {{
        break-inside: avoid;
      }}
    }}
  </style>
</head>
<body>

<!-- Sticky top bar -->
<div class="topbar">
  <div class="topbar-left">
    <span class="topbar-logo">FunnelTeardown</span>
    <div class="topbar-divider"></div>
    <span class="topbar-brand">{_e(brand.name)}</span>
  </div>
  <div class="topbar-right">
    <button class="action-link" onclick="downloadHtml()" title="Download this report as HTML">Download HTML</button>
    <button class="action-link" onclick="downloadJson()" title="Download the structured JSON data">Download JSON</button>
    <button class="action-link" onclick="window.print()" title="Print or save this report as PDF">Save PDF</button>
    <span class="pill pill-cost">&#36;{meta.total_cost_usd:.4f}</span>
    <span class="pill pill-time">{_e(meta.timestamp[:10])}</span>
    <span class="pill pill-time">{duration_str}</span>
    <button class="theme-toggle" id="themeToggle" onclick="toggleTheme()" title="Toggle light/dark mode">☀︎</button>
  </div>
</div>

<!-- Section nav -->
<nav class="section-nav">
  <a href="#brand" class="nav-tab">Brand</a>
  <a href="#read-first" class="nav-tab">Read First</a>
  <a href="#scorecard" class="nav-tab">Scorecard</a>
  <a href="#coverage" class="nav-tab">Coverage Map</a>
  <a href="#journey" class="nav-tab">Funnel Journey</a>
  <a href="#ladder" class="nav-tab">Value Ladder</a>
  <a href="#steps" class="nav-tab">Step Analysis</a>
  <a href="#offers" class="nav-tab">Offers</a>
  <a href="#recap" class="nav-tab">Recap</a>
  <a href="#sources" class="nav-tab">Sources</a>
  <a href="#questions" class="nav-tab">Open Questions</a>
  <a href="#run" class="nav-tab">Run Details</a>
</nav>

<div class="main">

  <section class="read-first" id="read-first">
    <h1>{_e(brand.name)} funnel teardown</h1>
    <p>Use this report as a working map: inspect the source links, scan the journey diagram, then review the offer gaps and open questions before making changes.</p>
    {takeaways_html}
  </section>

  <section id="scorecard">
    {scorecard_html}
  </section>

  <!-- Hero stats -->
  <div class="stats-grid" style="margin-top:32px;">
    <div class="stat-card">
      <div class="stat-value">{game_score}</div>
      <div class="stat-label">Game Score</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{_e(game_grade)}</div>
      <div class="stat-label">Grade</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{n_touchpoints}</div>
      <div class="stat-label">Touchpoints</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{n_steps}</div>
      <div class="stat-label">Journey Steps</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{n_offers}</div>
      <div class="stat-label">Offers</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{n_questions}</div>
      <div class="stat-label">Open Questions</div>
    </div>
    <div class="stat-card">
      <div class="stat-value" style="font-size:20px;">{cost_str}</div>
      <div class="stat-label">Total Cost</div>
    </div>
  </div>

  <!-- Brand -->
  <section class="section" id="brand">
    <div class="section-header">
      <div class="section-icon">🏷</div>
      <span class="section-title">Brand Overview</span>
      <span class="section-count">{_e(conf_v)} confidence</span>
    </div>
    <div class="brand-card">
      {logo_html}
      <div class="brand-name">{_e(brand.name)}</div>
      <a href="{_e(_normalize_url(brand.website))}" target="_blank" class="brand-website">{_e(brand.website)}</a>
      <div class="brand-meta">
        {founder_row}
        <div class="brand-row">
          <span class="brand-row-label">Description</span>
          <span class="brand-row-value">{_e(brand.description)}</span>
        </div>
        <div class="brand-row">
          <span class="brand-row-label">Primary ICP</span>
          <span class="brand-row-value">{_e(brand.primary_icp)}</span>
        </div>
        <div class="brand-row">
          <span class="brand-row-label">Sources</span>
          <span class="brand-row-value">{evidence_links}</span>
        </div>
      </div>
    </div>
  </section>

  <!-- Coverage map -->
  <section class="section" id="coverage">
    <div class="section-header">
      <div class="section-icon">📡</div>
      <span class="section-title">Awareness Coverage Map</span>
      <span class="section-count">{n_touchpoints} touchpoints</span>
    </div>
    <p class="section-desc">Which Schwartz awareness stages this brand actively reaches — gaps are opportunities.</p>
    {coverage_html}
  </section>

  <!-- Journey diagram -->
  <section class="section" id="journey">
    <div class="section-header">
      <div class="section-icon">⟶</div>
      <span class="section-title">Funnel Journey Diagram</span>
    </div>
    <p class="section-desc">Stranger → Advocate pathway. Solid border = observed. Dashed = inferred.</p>
    <div class="mermaid-wrap">
      <div class="mermaid">{_e(flowchart)}</div>
    </div>
  </section>

  <!-- Value Ladder -->
  <section class="section" id="ladder">
    <div class="section-header">
      <div class="section-icon">◈</div>
      <span class="section-title">Value Ladder</span>
      <span class="section-count">Brunson framework</span>
    </div>
    <p class="section-desc">Which rungs of the value ladder this brand occupies — and the ascension path from stranger to highest-ticket buyer.</p>
    {vl_bar_html}
  </section>

  <!-- Step analysis -->
  <section class="section" id="steps">
    <div class="section-header">
      <div class="section-icon">🔍</div>
      <span class="section-title">Journey Step Analysis</span>
      <span class="section-count">{n_steps} steps</span>
    </div>
    <p class="section-desc">Bustamante + Brunson dual-lens — Hook→Story→Offer per step, what's working, what's missing.</p>
    {steps_html}
  </section>

  <!-- Offers -->
  <section class="section" id="offers">
    <div class="section-header">
      <div class="section-icon">💰</div>
      <span class="section-title">Offers</span>
      <span class="section-count">{n_offers} identified</span>
    </div>
    {offers_html}
  </section>

  <!-- Recap -->
  <section class="section" id="recap">
    <div class="section-header">
      <div class="section-icon">★</div>
      <span class="section-title">Funnel Recap</span>
    </div>
    <p class="section-desc">The top tactics to copy and the gaps to avoid — distilled from this funnel.</p>
    {recap_html}
  </section>

  <!-- Open questions -->
  <section class="section" id="sources">
    <div class="section-header">
      <div class="section-icon">↗</div>
      <span class="section-title">Source Links</span>
      <span class="section-count">clickable</span>
    </div>
    <p class="section-desc">Every public URL captured for the brand, touchpoints, journey steps, and offers.</p>
    {sources_html}
  </section>

  <!-- Open questions -->
  <section class="section" id="questions">
    <div class="section-header">
      <div class="section-icon">❓</div>
      <span class="section-title">Open Questions</span>
      <span class="section-count">{n_questions} unanswered</span>
    </div>
    <p class="section-desc">What couldn't be determined from public data alone — private or ambiguous signals.</p>
    {open_q_html}
  </section>

  <!-- Run details -->
  <section class="section" id="run">
    <div class="section-header">
      <div class="section-icon">⚙</div>
      <span class="section-title">Run Details</span>
    </div>
    <table class="run-table">
      <thead>
        <tr>
          <th>Agent</th>
          <th>Model</th>
          <th>Cost (USD)</th>
        </tr>
      </thead>
      <tbody>
        {agent_rows}
      </tbody>
    </table>
    <p style="margin-top:12px;font-size:12px;color:#374151;">
      Total: <strong style="color:#22C55E;">{cost_str}</strong>
      &nbsp;·&nbsp; Runtime: {duration_str}
      &nbsp;·&nbsp; Generated: {_e(meta.timestamp)}
    </p>
  </section>

</div>

<footer style="border-top:1px solid #1E2333;padding:20px 24px;text-align:center;
     font-size:12px;color:#374151;">
  Generated by <a href="https://funnelteardownai.up.railway.app" target="_blank"
  style="color:#4B5563;text-decoration:none;font-weight:600;">FunnelTeardown AI</a>
  &nbsp;·&nbsp; Input: "{_e(meta.brand_input)}"
</footer>

<script>
  var root = document.documentElement;
  var btn = document.getElementById('themeToggle');

  // Detect initial theme: localStorage → prefers-color-scheme → dark default
  var stored = localStorage.getItem('ft-theme');
  if (stored) {{
    root.dataset.theme = stored;
  }} else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {{
    root.dataset.theme = 'light';
  }} else {{
    root.dataset.theme = 'dark';
  }}
  updateToggleIcon();

  function updateToggleIcon() {{
    btn.textContent = root.dataset.theme === 'dark' ? '☀︎' : '☾';
    btn.title = root.dataset.theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';
  }}

  function toggleTheme() {{
    var next = root.dataset.theme === 'dark' ? 'light' : 'dark';
    root.dataset.theme = next;
    localStorage.setItem('ft-theme', next);
    updateToggleIcon();
  }}

  function downloadHtml() {{
    var html = '<!DOCTYPE html>\\n' + document.documentElement.outerHTML;
    var blob = new Blob([html], {{ type: 'text/html;charset=utf-8' }});
    var link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = '{report_filename}';
    document.body.appendChild(link);
    link.click();
    URL.revokeObjectURL(link.href);
    link.remove();
  }}

  function downloadJson() {{
    var jsonText = atob('{report_json_b64}');
    var blob = new Blob([jsonText], {{ type: 'application/json;charset=utf-8' }});
    var link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = '{json_filename}';
    document.body.appendChild(link);
    link.click();
    URL.revokeObjectURL(link.href);
    link.remove();
  }}
</script>
</body>
</html>"""
