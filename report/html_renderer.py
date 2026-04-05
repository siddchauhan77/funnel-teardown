"""
HTML Report Renderer — pure Python, no LLM.
Converts FunnelMap → standalone HTML with Mermaid.js diagrams.
"""
from models.funnel_map import FunnelMap, JourneyStep

AWARENESS_COLORS = {
    "unaware": "#6B7280",
    "problem_aware": "#F59E0B",
    "solution_aware": "#3B82F6",
    "product_aware": "#8B5CF6",
    "most_aware": "#10B981",
    "customer": "#059669",
    "advocate": "#EC4899",
}

AWARENESS_LABELS = {
    "unaware": "Unaware",
    "problem_aware": "Problem Aware",
    "solution_aware": "Solution Aware",
    "product_aware": "Product Aware",
    "most_aware": "Most Aware",
    "customer": "Customer",
    "advocate": "Advocate",
}


def _mermaid_flowchart(steps: list) -> str:
    """Generate Mermaid LR flowchart of journey steps."""
    if not steps:
        return "flowchart LR\n    A[No steps mapped]"

    lines = ["flowchart LR"]
    for step in steps:
        label = step.label.replace('"', "'")
        al_val = step.awareness_level.value if hasattr(step.awareness_level, 'value') else str(step.awareness_level)
        al = AWARENESS_LABELS.get(al_val, al_val)
        observed_mark = "" if step.is_observed else " ⚬"
        lines.append(f'    {step.id}["{label}\\n({al}){observed_mark}"]')

    for step in steps:
        for exit_id in step.exits_to:
            lines.append(f"    {step.id} --> {exit_id}")

    for step in steps:
        al_val = step.awareness_level.value if hasattr(step.awareness_level, 'value') else str(step.awareness_level)
        color = AWARENESS_COLORS.get(al_val, "#9CA3AF")
        lines.append(f"    style {step.id} fill:{color},color:#fff,stroke:{color}")

    return "\n".join(lines)


def _awareness_coverage_table(fm: FunnelMap) -> str:
    """HTML table: touchpoints grouped by awareness level."""
    by_level: dict = {}
    for t in fm.touchpoints:
        al_val = t.awareness_level.value if hasattr(t.awareness_level, 'value') else str(t.awareness_level)
        by_level.setdefault(al_val, []).append(t)

    rows = []
    for level in ["unaware", "problem_aware", "solution_aware",
                  "product_aware", "most_aware", "customer", "advocate"]:
        touchpoints = by_level.get(level, [])
        color = AWARENESS_COLORS.get(level, "#9CA3AF")
        label = AWARENESS_LABELS.get(level, level)
        if touchpoints:
            platforms = ", ".join(
                f'<a href="{t.url}" target="_blank">{t.handle_or_name} ({t.platform})</a>'
                for t in touchpoints
            )
        else:
            platforms = '<span style="color:#9CA3AF;">—</span>'
        rows.append(
            f'<tr><td style="background:{color};color:#fff;padding:6px 12px;'
            f'font-weight:600;white-space:nowrap;">{label}</td>'
            f'<td style="padding:6px 12px;">{platforms}</td></tr>'
        )
    return (
        '<table style="border-collapse:collapse;width:100%;margin:16px 0;">'
        '<thead><tr>'
        '<th style="text-align:left;padding:6px 12px;background:#1F2937;color:#fff;">Awareness Level</th>'
        '<th style="text-align:left;padding:6px 12px;background:#1F2937;color:#fff;">Touchpoints</th>'
        '</tr></thead><tbody>' + "".join(rows) + "</tbody></table>"
    )


def _journey_steps_html(steps: list) -> str:
    cards = []
    for step in steps:
        al_val = step.awareness_level.value if hasattr(step.awareness_level, 'value') else str(step.awareness_level)
        al = AWARENESS_LABELS.get(al_val, al_val)
        color = AWARENESS_COLORS.get(al_val, "#9CA3AF")
        observed_badge = (
            '<span style="background:#D1FAE5;color:#065F46;padding:2px 8px;'
            'border-radius:4px;font-size:12px;">Observed</span>'
            if step.is_observed else
            '<span style="background:#FEF3C7;color:#92400E;padding:2px 8px;'
            'border-radius:4px;font-size:12px;">Inferred</span>'
        )
        conf_badge = (
            f'<span style="background:#F3F4F6;color:#374151;padding:2px 8px;'
            f'border-radius:4px;font-size:12px;">{step.confidence} confidence</span>'
        )
        working = "".join(f"<li>{w}</li>" for w in step.whats_working) or "<li>—</li>"
        missing = "".join(f"<li>{m}</li>" for m in step.whats_missing) or "<li>—</li>"
        evidence = " ".join(
            f'<a href="{e}" target="_blank" style="font-size:12px;color:#6B7280;">[source]</a>'
            for e in step.evidence
        )
        cards.append(f"""
<div style="border:1px solid #E5E7EB;border-left:4px solid {color};
     border-radius:8px;padding:20px;margin-bottom:16px;">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
    <h3 style="margin:0;font-size:16px;">{step.label}</h3>
    {observed_badge} {conf_badge}
  </div>
  <p style="color:#6B7280;font-size:13px;margin:0 0 4px;">
    Stage: <strong style="color:{color};">{al}</strong> &nbsp;|&nbsp;
    Type: {step.type}
  </p>
  <p style="margin:8px 0;">{step.description}</p>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:12px;">
    <div style="background:#F0FDF4;border-radius:6px;padding:12px;">
      <p style="margin:0 0 6px;font-weight:600;color:#065F46;">&#x2705; What's Working</p>
      <ul style="margin:0;padding-left:16px;color:#374151;">{working}</ul>
    </div>
    <div style="background:#FFFBEB;border-radius:6px;padding:12px;">
      <p style="margin:0 0 6px;font-weight:600;color:#92400E;">&#x1F527; What's Missing</p>
      <ul style="margin:0;padding-left:16px;color:#374151;">{missing}</ul>
    </div>
  </div>
  <p style="margin:8px 0 0;font-size:12px;color:#9CA3AF;">{evidence}</p>
</div>""")
    return "\n".join(cards)


def _offers_table(fm: FunnelMap) -> str:
    if not fm.offers:
        return "<p style='color:#9CA3AF;'>No offers identified.</p>"
    rows = []
    for o in fm.offers:
        price = f"${o.price_usd:.0f}" if o.price_usd is not None else "—"
        observed = "&#x2713;" if o.is_observed else "&#x26AC; inferred"
        al_val = o.target_awareness_level.value if hasattr(o.target_awareness_level, 'value') else str(o.target_awareness_level)
        rows.append(
            f"<tr>"
            f"<td style='padding:8px 12px;'><strong>{o.name}</strong></td>"
            f"<td style='padding:8px 12px;'>{o.type}</td>"
            f"<td style='padding:8px 12px;font-style:italic;'>{o.headline_or_promise}</td>"
            f"<td style='padding:8px 12px;'>{price}</td>"
            f"<td style='padding:8px 12px;'>{AWARENESS_LABELS.get(al_val, al_val)}</td>"
            f"<td style='padding:8px 12px;color:#6B7280;font-size:13px;'>{observed}</td>"
            f"</tr>"
        )
    th = "padding:8px 12px;background:#1F2937;color:#fff;text-align:left;"
    return (
        f'<table style="border-collapse:collapse;width:100%;">'
        f'<thead><tr>'
        f'<th style="{th}">Offer</th>'
        f'<th style="{th}">Type</th>'
        f'<th style="{th}">Promise</th>'
        f'<th style="{th}">Price</th>'
        f'<th style="{th}">Stage</th>'
        f'<th style="{th}">Source</th>'
        f'</tr></thead><tbody>' + "".join(rows) + "</tbody></table>"
    )


def render_html(fm: FunnelMap) -> str:
    """Render a FunnelMap to a standalone HTML report string."""
    flowchart = _mermaid_flowchart(fm.journey_steps)
    coverage_table = _awareness_coverage_table(fm)
    steps_html = _journey_steps_html(fm.journey_steps)
    offers_html = _offers_table(fm)

    open_q_html = "".join(
        f"<li>{q}</li>" for q in fm.open_questions
    ) or "<li>None — great coverage!</li>"

    meta = fm.run_metadata
    cost_str = f"${meta.total_cost_usd:.2f}"
    duration_str = f"{meta.duration_seconds:.0f}s"
    agent_cost_rows = "".join(
        f"<tr><td style='padding:4px 12px;'>{agent}</td>"
        f"<td style='padding:4px 12px;'>{meta.model_used.get(agent, '—')}</td>"
        f"<td style='padding:4px 12px;'>${cost:.4f}</td></tr>"
        for agent, cost in meta.agent_costs.items()
    )

    brand = fm.brand
    founder_html = f"<p><strong>Founder:</strong> {brand.founder}</p>" if brand.founder else ""
    evidence_links = " ".join(
        f'<a href="{e}" target="_blank" style="color:#3B82F6;">[{i+1}]</a>'
        for i, e in enumerate(brand.evidence)
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>FunnelTeardown: {brand.name}</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
  <script>mermaid.initialize({{ startOnLoad: true, theme: 'base' }});</script>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           max-width: 960px; margin: 0 auto; padding: 32px 24px; color: #111827;
           background: #F9FAFB; }}
    h1 {{ font-size: 28px; margin-bottom: 4px; }}
    h2 {{ font-size: 20px; border-bottom: 2px solid #E5E7EB;
          padding-bottom: 8px; margin-top: 40px; }}
    .meta {{ color: #6B7280; font-size: 14px; margin-bottom: 32px; }}
    .brand-card {{ background: #fff; border-radius: 12px; padding: 24px;
                  border: 1px solid #E5E7EB; margin-bottom: 24px; }}
    .mermaid {{ background: #fff; border-radius: 12px; padding: 24px;
               border: 1px solid #E5E7EB; overflow-x: auto; }}
    ol {{ padding-left: 20px; line-height: 1.8; }}
    table {{ border-radius: 8px; overflow: hidden; }}
    a {{ color: #3B82F6; }}
  </style>
</head>
<body>
  <h1>FunnelTeardown: {brand.name}</h1>
  <p class="meta">
    Generated {meta.timestamp} &nbsp;|&nbsp;
    Total cost: <strong>{cost_str}</strong> &nbsp;|&nbsp;
    Runtime: {duration_str} &nbsp;|&nbsp;
    Input: {meta.brand_input}
  </p>

  <h2>Brand Overview</h2>
  <div class="brand-card">
    <p><strong>Name:</strong> {brand.name}</p>
    <p><strong>Website:</strong> <a href="{brand.website}" target="_blank">{brand.website}</a></p>
    {founder_html}
    <p><strong>Description:</strong> {brand.description}</p>
    <p><strong>Primary ICP:</strong> {brand.primary_icp}</p>
    <p style="color:#6B7280;font-size:13px;">
      Brand confidence: {brand.confidence} &nbsp;|&nbsp;
      Sources: {evidence_links}
    </p>
  </div>

  <h2>Awareness Coverage Map</h2>
  <p style="color:#6B7280;font-size:14px;">Which Schwartz awareness levels each discovered touchpoint serves.</p>
  {coverage_table}

  <h2>Funnel Journey</h2>
  <div class="mermaid">
{flowchart}
  </div>

  <h2>Journey Step Analysis</h2>
  <p style="color:#6B7280;font-size:14px;">
    Observed = found direct evidence &nbsp;|&nbsp; Inferred = hypothesis based on business type
  </p>
  {steps_html}

  <h2>Offers</h2>
  {offers_html}

  <h2>Open Questions</h2>
  <ol>{open_q_html}</ol>

  <h2>Run Details</h2>
  <table style="border-collapse:collapse;">
    <thead><tr>
      <th style="padding:4px 12px;background:#1F2937;color:#fff;text-align:left;">Agent</th>
      <th style="padding:4px 12px;background:#1F2937;color:#fff;text-align:left;">Model</th>
      <th style="padding:4px 12px;background:#1F2937;color:#fff;text-align:left;">Cost</th>
    </tr></thead>
    <tbody>{agent_cost_rows}</tbody>
  </table>
</body>
</html>"""
