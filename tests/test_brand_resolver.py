import pytest
from unittest.mock import MagicMock, patch
from agents.brand_resolver import resolve_brand
from state.teardown_state import TeardownState
from utils.cost_tracker import CostTracker


def _make_openai_response(text: str, input_tokens: int = 500, output_tokens: int = 300):
    """Build a minimal mock of the OpenAI Responses API response object."""
    mock_response = MagicMock()
    mock_response.output_text = text
    mock_response.usage.input_tokens = input_tokens
    mock_response.usage.output_tokens = output_tokens
    return mock_response


AG1_JSON = """
{
  "name": "AG1",
  "website": "https://ag1.com",
  "founder": "Chris Ashenden",
  "description": "AG1 is a daily all-in-one greens supplement targeting health-conscious adults.",
  "primary_icp": "Health-conscious professionals aged 25-45 who want a simple daily nutrition habit.",
  "confidence": "high",
  "evidence": ["https://ag1.com/about", "https://en.wikipedia.org/wiki/Athletic_Greens"],
  "ambiguous": false
}
"""


def test_resolve_brand_populates_state():
    state = TeardownState.new("Athletic Greens", hints={})
    tracker = CostTracker()

    mock_response = _make_openai_response(AG1_JSON)

    with patch("agents.brand_resolver.openai_client") as mock_client:
        mock_client.responses.create.return_value = mock_response
        resolve_brand(state, tracker)

    assert state.funnel_map.brand.name == "AG1"
    assert state.funnel_map.brand.website == "https://ag1.com"
    assert state.funnel_map.brand.founder == "Chris Ashenden"
    assert state.funnel_map.brand.confidence == "high"


def test_resolve_brand_records_cost():
    state = TeardownState.new("Athletic Greens", hints={})
    tracker = CostTracker()

    mock_response = _make_openai_response(AG1_JSON, input_tokens=800, output_tokens=400)

    with patch("agents.brand_resolver.openai_client") as mock_client:
        mock_client.responses.create.return_value = mock_response
        resolve_brand(state, tracker)

    cost = tracker.agent_cost("brand_resolver")
    assert cost > 0


def test_resolve_brand_raises_on_ambiguous():
    state = TeardownState.new("Apple", hints={})
    tracker = CostTracker()

    ambiguous_json = """
    {
      "name": "Apple",
      "website": "",
      "founder": null,
      "description": "",
      "primary_icp": "",
      "confidence": "low",
      "evidence": [],
      "ambiguous": true,
      "ambiguity_note": "Could be Apple Inc (tech), Apple Bank, or Apple Records."
    }
    """
    mock_response = _make_openai_response(ambiguous_json)

    with patch("agents.brand_resolver.openai_client") as mock_client:
        mock_client.responses.create.return_value = mock_response
        with pytest.raises(ValueError, match="ambiguous"):
            resolve_brand(state, tracker)


def test_resolve_brand_uses_hints():
    state = TeardownState.new("Justin Welsh", hints={"url": "justinwelsh.me"})
    tracker = CostTracker()
    mock_response = _make_openai_response(AG1_JSON)

    with patch("agents.brand_resolver.openai_client") as mock_client:
        mock_client.responses.create.return_value = mock_response
        resolve_brand(state, tracker)

    call_args = mock_client.responses.create.call_args
    assert "justinwelsh.me" in call_args.kwargs.get("input", "")
