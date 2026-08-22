from agents.simple_mapper import run_simple_analysis
from state.teardown_state import TeardownState
from utils.cost_tracker import CostTracker


def test_simple_mapper_builds_report_without_network_success(mocker):
    mocker.patch("agents.simple_mapper.scan_homepage").return_value = mocker.Mock(
        url="https://example.com",
        title="Example Brand",
        description="Example promise",
        text_sample="Example page copy",
        links=[],
        theme_color=None,
        logo_url=None,
    )
    state = TeardownState.new("Example", hints={"url": "example.com"})
    tracker = CostTracker()

    run_simple_analysis(state, tracker)

    assert state.funnel_map.brand.name == "Example"
    assert len(state.funnel_map.touchpoints) >= 1
    assert len(state.funnel_map.journey_steps) == 7
    assert len(state.funnel_map.offers) == 1
    assert state.funnel_map.offers[0].is_observed is False
    assert tracker.total_cost() == 0


def test_simple_mapper_detects_visible_offer_links(mocker):
    mocker.patch("agents.simple_mapper.scan_homepage").return_value = mocker.Mock(
        url="https://example.com",
        title="Example Brand",
        description="Example promise",
        text_sample="Example page copy",
        links=[("Pricing", "https://example.com/pricing")],
        theme_color=None,
        logo_url=None,
    )
    state = TeardownState.new("Example", hints={"url": "example.com"})

    run_simple_analysis(state)

    assert state.funnel_map.offers[0].name == "Pricing"
    assert state.funnel_map.offers[0].is_observed is True
