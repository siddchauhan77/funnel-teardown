"""
HTML Report Renderer — pure Python, no LLM.
Converts FunnelMap -> standalone dark-mode HTML report with Mermaid.js diagrams.
Design: dark professional SaaS (Linear/Notion aesthetic) — FunnelTeardown brand.
"""
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
    "other": "•",
}


def _al(obj) -> str:
    """Safely extract awareness level string from enum or str."""
    return obj.value if hasattr(obj, "value") else str(obj)


def _conf_badge(conf: str) -> str:
    color_map = {"high": "#22C55E", "medium": "#F59E0B", "low": "#EF4444"}
    c = color_map.get(str(conf), "#94A3B8")
    return (
        f'<span style="display:inline-flex;align-items:center;gap:4px;'
        f'font-size:11px;font-weight:500;color:{c};'
        f'background:{c}22;padding:2px 8px;border-radius:20px;">'
        f'<span style="width:5px;height:5px;border-radius:50%;background:{c};display:inline-block;"></span>'
        f'{conf} confidence</span>'
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
        lines.append(f'    {step.id}["{label}\\n{al_text}{suffix}"]')
    for step in steps:
        for exit_id in step.exits_to:
            lines.append(f"    {step.id} --> {exit_id}")
    for step in steps:
        al = _al(step.awareness_level)
        c = AL_COLOR.get(al, "#94A3B8")
        lines.append(f"    style {step.id} fill:{c}33,stroke:{c},stroke-width:2px,color:#F1F5F9")
    return "\n".join(lines)


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
                f'<a href="{t.url}" target="_blank" style="display:block;color:#94A3B8;'
                f'font-size:12px;text-decoration:none;margin-top:4px;'
                f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" '
                f'title="{t.handle_or_name}">'
                f'<span style="color:{color};">▸</span> {t.handle_or_name}</a>'
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
            f'letter-spacing:0.05em;">{label}</span>'
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

        working_items = "".join(
            f'<li style="margin-bottom:6px;padding-left:4px;">{w}</li>'
            for w in step.whats_working
        ) or '<li style="color:#4B5563;">—</li>'

        missing_items = "".join(
            f'<li style="margin-bottom:6px;padding-left:4px;">{m}</li>'
            for m in step.whats_missing
        ) or '<li style="color:#4B5563;">—</li>'

        evidence_links = " ".join(
            f'<a href="{e}" target="_blank" style="color:#3B82F6;font-size:11px;'
            f'text-decoration:none;padding:2px 6px;background:#3B82F611;border-radius:4px;">'
            f'source {j+1}</a>'
            for j, e in enumerate(step.evidence)
        )

        exits = ", ".join(f'<code style="background:#1E2333;padding:1px 5px;border-radius:3px;'
                          f'font-size:11px;color:#94A3B8;">{e}</code>'
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
               text-transform:uppercase;color:{color};">{al_label}</span>
          <span style="color:#374151;font-size:11px;">·</span>
          <span style="font-size:11px;color:#64748B;">{type_v.replace("_"," ")}</span>
        </div>
        <h3 style="margin:4px 0 0;font-size:15px;font-weight:600;color:#F1F5F9;line-height:1.3;">
          {step.label}
        </h3>
      </div>
    </div>
    <div style="display:flex;gap:6px;flex-wrap:wrap;flex-shrink:0;">
      {_observed_badge(step.is_observed)}
      {_conf_badge(conf_v)}
    </div>
  </div>

  <div style="padding:16px 20px;">
    <p style="color:#94A3B8;font-size:14px;margin:0 0 16px;line-height:1.6;">{step.description}</p>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
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
      <span style="font-size:13px;font-weight:700;color:#F1F5F9;">{o.name}</span>
      <span style="font-size:11px;color:#64748B;background:#1E2333;padding:2px 8px;
           border-radius:4px;">{type_v.replace("_"," ")}</span>
      {_observed_badge(o.is_observed)}
    </div>
    <p style="margin:0 0 8px;color:#94A3B8;font-size:13px;font-style:italic;line-height:1.5;">
      "{o.headline_or_promise}"
    </p>
    <div style="font-size:12px;color:#4B5563;">
      Connected to: <code style="background:#1E2333;padding:1px 5px;border-radius:3px;
      color:#94A3B8;">{o.connected_step_id}</code>
    </div>
  </div>
  <div style="display:flex;flex-direction:column;align-items:flex-end;gap:8px;flex-shrink:0;">
    <div style="font-size:24px;font-weight:700;color:#F1F5F9;">{price}</div>
    <span style="font-size:11px;font-weight:600;color:{color};background:{bg};
         padding:4px 10px;border-radius:20px;border:1px solid {color}33;">{al_label}</span>
    {_conf_badge(conf_v)}
  </div>
</div>""")

    return "\n".join(cards)


def _open_questions_section(questions: list) -> str:
    if not questions:
        return '<p style="color:#22C55E;font-size:14px;">No open questions — excellent coverage.</p>'
    items = "".join(
        f'<li style="margin-bottom:12px;padding:14px 16px;background:#13151F;'
        f'border:1px solid #1E2333;border-left:3px solid #3B82F6;border-radius:0 8px 8px 0;'
        f'color:#94A3B8;font-size:14px;line-height:1.6;">{q}</li>'
        for q in questions
    )
    return f'<ol style="padding-left:24px;list-style:decimal;">{items}</ol>'


def render_html(fm: FunnelMap) -> str:
    """Render a FunnelMap to a standalone dark-mode HTML report."""
    flowchart = _mermaid_flowchart(fm.journey_steps)
    coverage_html = _coverage_grid(fm)
    steps_html = _step_cards(fm.journey_steps)
    offers_html = _offers_section(fm)
    open_q_html = _open_questions_section(fm.open_questions)

    meta = fm.run_metadata
    cost_str = f"${meta.total_cost_usd:.4f}"
    duration_str = f"{meta.duration_seconds:.0f}s"
    brand = fm.brand

    n_steps = len(fm.journey_steps)
    n_touchpoints = len(fm.touchpoints)
    n_offers = len(fm.offers)
    n_questions = len(fm.open_questions)

    agent_rows = "".join(
        f'<tr style="border-bottom:1px solid #1E2333;">'
        f'<td style="padding:10px 16px;color:#94A3B8;font-size:13px;">{agent}</td>'
        f'<td style="padding:10px 16px;color:#64748B;font-size:12px;">'
        f'<code style="background:#1E2333;padding:2px 6px;border-radius:4px;">'
        f'{meta.model_used.get(agent, "—")}</code></td>'
        f'<td style="padding:10px 16px;color:#22C55E;font-size:13px;font-weight:500;">'
        f'${cost:.4f}</td></tr>'
        for agent, cost in meta.agent_costs.items()
    )

    evidence_links = " ".join(
        f'<a href="{e}" target="_blank" style="color:#3B82F6;font-size:12px;'
        f'text-decoration:none;">[{i+1}]</a>'
        for i, e in enumerate(brand.evidence)
    ) or "—"

    founder_row = (
        f'<div style="display:flex;gap:8px;">'
        f'<span style="color:#4B5563;font-size:13px;min-width:80px;">Founder</span>'
        f'<span style="color:#94A3B8;font-size:13px;">{brand.founder}</span></div>'
        if brand.founder else ""
    )

    conf_v = brand.confidence.value if hasattr(brand.confidence, "value") else str(brand.confidence)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>FunnelTeardown — {brand.name}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
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
      --accent: #3B82F6;
    }}

    body {{
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      line-height: 1.6;
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
      max-width: 960px;
      margin: 0 auto;
      padding: 32px 24px 80px;
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
      background: var(--accent)22;
      border: 1px solid var(--accent)44;
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

    a {{ color: var(--accent); }}

    @media (max-width: 640px) {{
      .topbar-right .pill-time {{ display: none; }}
      .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
    }}
  </style>
</head>
<body>

<!-- Sticky top bar -->
<div class="topbar">
  <div class="topbar-left">
    <span class="topbar-logo">FunnelTeardown</span>
    <div class="topbar-divider"></div>
    <span class="topbar-brand">{brand.name}</span>
  </div>
  <div class="topbar-right">
    <span class="pill pill-cost">&#36;{meta.total_cost_usd:.4f}</span>
    <span class="pill pill-time">{meta.timestamp[:10]}</span>
    <span class="pill pill-time">{duration_str}</span>
  </div>
</div>

<!-- Section nav -->
<nav class="section-nav">
  <a href="#brand" class="nav-tab">Brand</a>
  <a href="#coverage" class="nav-tab">Coverage Map</a>
  <a href="#journey" class="nav-tab">Funnel Journey</a>
  <a href="#steps" class="nav-tab">Step Analysis</a>
  <a href="#offers" class="nav-tab">Offers</a>
  <a href="#questions" class="nav-tab">Open Questions</a>
  <a href="#run" class="nav-tab">Run Details</a>
</nav>

<div class="main">

  <!-- Hero stats -->
  <div class="stats-grid" style="margin-top:32px;">
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
      <span class="section-count">{conf_v} confidence</span>
    </div>
    <div class="brand-card">
      <div class="brand-name">{brand.name}</div>
      <a href="{brand.website}" target="_blank" class="brand-website">{brand.website}</a>
      <div class="brand-meta">
        {founder_row}
        <div class="brand-row">
          <span class="brand-row-label">Description</span>
          <span class="brand-row-value">{brand.description}</span>
        </div>
        <div class="brand-row">
          <span class="brand-row-label">Primary ICP</span>
          <span class="brand-row-value">{brand.primary_icp}</span>
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
      <div class="mermaid">{flowchart}</div>
    </div>
  </section>

  <!-- Step analysis -->
  <section class="section" id="steps">
    <div class="section-header">
      <div class="section-icon">🔍</div>
      <span class="section-title">Journey Step Analysis</span>
      <span class="section-count">{n_steps} steps</span>
    </div>
    <p class="section-desc">Bustamante-style dual-lens review — what's working, what's missing — per funnel step.</p>
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
      &nbsp;·&nbsp; Generated: {meta.timestamp}
    </p>
  </section>

</div>

<footer style="border-top:1px solid #1E2333;padding:20px 24px;text-align:center;
     font-size:12px;color:#374151;">
  Generated by <strong style="color:#4B5563;">FunnelTeardown AI</strong>
  &nbsp;·&nbsp; Input: "{meta.brand_input}"
  &nbsp;·&nbsp; <a href="https://github.com/siddchauhan77/funnel-teardown"
  target="_blank" style="color:#3B82F6;text-decoration:none;">github.com/siddchauhan77/funnel-teardown</a>
</footer>

</body>
</html>"""
