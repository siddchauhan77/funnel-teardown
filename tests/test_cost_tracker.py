from utils.cost_tracker import CostTracker

# GPT-4o-mini pricing per 1M tokens
GPT4O_MINI_INPUT_PER_M = 0.15
GPT4O_MINI_OUTPUT_PER_M = 0.60

# Claude Sonnet 4.6 pricing per 1M tokens
CLAUDE_SONNET_INPUT_PER_M = 3.00
CLAUDE_SONNET_OUTPUT_PER_M = 15.00


def test_record_and_retrieve_agent_cost():
    tracker = CostTracker()
    tracker.record("brand_resolver", "gpt-4o-mini-search-preview",
                   input_tokens=1000, output_tokens=500)
    cost = tracker.agent_cost("brand_resolver")
    expected = (1000 / 1_000_000 * GPT4O_MINI_INPUT_PER_M +
                500 / 1_000_000 * GPT4O_MINI_OUTPUT_PER_M)
    assert abs(cost - expected) < 0.0001


def test_total_cost_across_agents():
    tracker = CostTracker()
    tracker.record("brand_resolver", "gpt-4o-mini-search-preview",
                   input_tokens=2000, output_tokens=800)
    tracker.record("journey_mapper", "claude-sonnet-4-6",
                   input_tokens=5000, output_tokens=2000)
    total = tracker.total_cost()
    expected = (
        2000 / 1_000_000 * GPT4O_MINI_INPUT_PER_M +
        800 / 1_000_000 * GPT4O_MINI_OUTPUT_PER_M +
        5000 / 1_000_000 * CLAUDE_SONNET_INPUT_PER_M +
        2000 / 1_000_000 * CLAUDE_SONNET_OUTPUT_PER_M
    )
    assert abs(total - expected) < 0.0001


def test_agent_costs_dict():
    tracker = CostTracker()
    tracker.record("brand_resolver", "gpt-4o-mini-search-preview",
                   input_tokens=1000, output_tokens=500)
    tracker.record("touchpoint_mapper", "gpt-4o-mini-search-preview",
                   input_tokens=1000, output_tokens=500)
    costs = tracker.agent_costs_dict()
    assert "brand_resolver" in costs
    assert "touchpoint_mapper" in costs


def test_format_usd():
    tracker = CostTracker()
    assert tracker.format_usd(0.1234) == "$0.12"
    assert tracker.format_usd(0.005) == "$0.01"
    assert tracker.format_usd(0.0) == "$0.00"


def test_unknown_model_raises():
    tracker = CostTracker()
    try:
        tracker.record("agent", "gpt-99-turbo", input_tokens=100, output_tokens=50)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "gpt-99-turbo" in str(e)
