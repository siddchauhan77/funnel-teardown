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
