from report.html_renderer import render_html
from models.funnel_map import (
    FunnelMap, Brand, Touchpoint, JourneyStep, Offer, RunMetadata
)


def _sample_funnel_map() -> FunnelMap:
    return FunnelMap(
        brand=Brand(
            name="AG1", website="https://ag1.com",
            founder="Chris Ashenden",
            description="Daily greens supplement",
            primary_icp="Health-conscious professionals",
            confidence="high",
            evidence=["https://ag1.com/about"]
        ),
        touchpoints=[
            Touchpoint(
                platform="youtube", handle_or_name="DrinkAG1",
                url="https://youtube.com/@drinkag1",
                awareness_level="unaware",
                is_observed=True, confidence="high",
                evidence=["https://ag1.com"]
            )
        ],
        journey_steps=[
            JourneyStep(
                id="step_1",
                label="YouTube ad — energy crashes",
                awareness_level="unaware",
                type="content",
                description="Pre-roll ad targeting people with low energy.",
                entry_from=[],
                exits_to=["step_2"],
                whats_working=["Universal pain-point hook"],
                whats_missing=["No soft CTA"],
                is_observed=True,
                confidence="high",
                evidence=["https://youtube.com/@drinkag1"]
            )
        ],
        offers=[
            Offer(
                name="AG1 Subscription",
                type="subscription",
                headline_or_promise="All-in-one daily nutrition",
                target_awareness_level="most_aware",
                price_usd=79.0,
                connected_step_id="step_1",
                is_observed=True,
                confidence="high",
                evidence=["https://ag1.com/products"]
            )
        ],
        open_questions=["Does AG1 run Facebook retargeting?"],
        run_metadata=RunMetadata(
            brand_input="Athletic Greens",
            hints={},
            timestamp="2026-04-05T14:00:00",
            total_cost_usd=0.20,
            agent_costs={"brand_resolver": 0.02, "journey_mapper": 0.18},
            model_used={"brand_resolver": "gpt-4o-mini-search-preview",
                        "journey_mapper": "claude-sonnet-4-6"},
            duration_seconds=47.0
        )
    )


def test_render_returns_html_string():
    html = render_html(_sample_funnel_map())
    assert isinstance(html, str)
    assert html.startswith("<!DOCTYPE html>")


def test_render_includes_brand_name():
    html = render_html(_sample_funnel_map())
    assert "AG1" in html


def test_render_includes_mermaid_cdn():
    html = render_html(_sample_funnel_map())
    assert "mermaid" in html.lower()


def test_render_includes_funnel_flowchart():
    html = render_html(_sample_funnel_map())
    assert "flowchart" in html or "graph" in html
    assert "step_1" in html or "YouTube ad" in html


def test_render_includes_touchpoints_section():
    html = render_html(_sample_funnel_map())
    assert "youtube" in html.lower() or "DrinkAG1" in html


def test_render_includes_whats_working_and_missing():
    html = render_html(_sample_funnel_map())
    assert "Universal pain-point hook" in html
    assert "No soft CTA" in html


def test_render_includes_offers_table():
    html = render_html(_sample_funnel_map())
    assert "AG1 Subscription" in html
    assert "79" in html  # price


def test_render_includes_open_questions():
    html = render_html(_sample_funnel_map())
    assert "Facebook retargeting" in html


def test_render_includes_cost_in_header():
    html = render_html(_sample_funnel_map())
    assert "0.20" in html or "$0.20" in html


def test_render_includes_run_details_section():
    html = render_html(_sample_funnel_map())
    assert "gpt-4o-mini" in html or "claude-sonnet" in html


def test_render_includes_download_controls():
    html = render_html(_sample_funnel_map())
    assert "Download HTML" in html
    assert "Download JSON" in html
    assert "Save PDF" in html
    assert "downloadHtml()" in html
    assert "downloadJson()" in html


def test_render_includes_source_links_section():
    html = render_html(_sample_funnel_map())
    assert "Source Links" in html
    assert "https://youtube.com/@drinkag1" in html
    assert "https://ag1.com/products" in html


def test_render_normalizes_markdown_source_urls():
    fm = _sample_funnel_map()
    fm.brand.evidence = ["[AG1 About](https://ag1.com/about)"]

    html = render_html(fm)

    assert 'href="https://ag1.com/about"' in html
    assert 'href="[AG1 About]' not in html


def test_render_includes_read_first_summary():
    html = render_html(_sample_funnel_map())
    assert "Read First" in html
    assert "AG1 funnel teardown" in html


def test_render_includes_game_scorecard():
    html = render_html(_sample_funnel_map())
    assert "Game Scorecard" in html
    assert "Journey Coverage" in html
    assert "Offer Ladder" in html
    assert "Conversion Clarity" in html
    assert "Evidence Quality" in html
    assert "Retention Loop" in html
    assert "Game Score" in html


def test_render_uses_native_design_system_typography():
    html = render_html(_sample_funnel_map())

    assert "fonts.googleapis.com" not in html
    assert "font-family: -apple-system" in html


def test_render_escapes_dynamic_text():
    fm = _sample_funnel_map()
    fm.brand.name = '<script>alert("x")</script>'
    fm.journey_steps[0].whats_working = ['<img src=x onerror=alert(1)>']

    html = render_html(fm)

    assert '<script>alert("x")</script>' not in html
    assert '<img src=x onerror=alert(1)>' not in html
    assert '&lt;script&gt;' in html
    assert '&lt;img' in html
