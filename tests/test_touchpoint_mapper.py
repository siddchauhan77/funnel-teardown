import pytest
from unittest.mock import MagicMock, patch
from agents.touchpoint_mapper import map_touchpoints
from state.teardown_state import TeardownState
from utils.cost_tracker import CostTracker
from models.funnel_map import Brand


def _state_with_brand(name="AG1", website="https://ag1.com") -> TeardownState:
    state = TeardownState.new("Athletic Greens", hints={})
    state.funnel_map.brand = Brand(
        name=name, website=website, founder="Chris Ashenden",
        description="Greens supplement", primary_icp="Health-conscious adults",
        confidence="high", evidence=[]
    )
    return state


TOUCHPOINTS_JSON = """
[
  {
    "platform": "youtube",
    "handle_or_name": "DrinkAG1",
    "url": "https://youtube.com/@drinkag1",
    "awareness_level": "unaware",
    "is_observed": true,
    "confidence": "high",
    "evidence": ["https://ag1.com"]
  },
  {
    "platform": "instagram",
    "handle_or_name": "@drinkag1",
    "url": "https://instagram.com/drinkag1",
    "awareness_level": "problem_aware",
    "is_observed": true,
    "confidence": "high",
    "evidence": ["https://ag1.com"]
  },
  {
    "platform": "newsletter",
    "handle_or_name": "AG1 Newsletter",
    "url": "https://ag1.com/newsletter",
    "awareness_level": "solution_aware",
    "is_observed": false,
    "confidence": "medium",
    "evidence": []
  }
]
"""

FAKE_HTML = """
<html><body>
<a href="https://youtube.com/@drinkag1">YouTube</a>
<a href="https://instagram.com/drinkag1">Instagram</a>
<a href="/subscribe">Newsletter</a>
</body></html>
"""


def test_map_touchpoints_populates_state():
    state = _state_with_brand()
    tracker = CostTracker()

    mock_response = MagicMock()
    mock_response.output_text = TOUCHPOINTS_JSON
    mock_response.usage.input_tokens = 600
    mock_response.usage.output_tokens = 400

    mock_http = MagicMock()
    mock_http_response = MagicMock()
    mock_http_response.text = FAKE_HTML
    mock_http_response.status_code = 200
    mock_http.get.return_value = mock_http_response

    with patch("agents.touchpoint_mapper.openai_client") as mock_client, \
         patch("agents.touchpoint_mapper.http_client", mock_http):
        mock_client.responses.create.return_value = mock_response
        map_touchpoints(state, tracker)

    assert len(state.funnel_map.touchpoints) == 3
    platforms = [t.platform for t in state.funnel_map.touchpoints]
    assert "youtube" in platforms
    assert "instagram" in platforms


def test_map_touchpoints_records_cost():
    state = _state_with_brand()
    tracker = CostTracker()

    mock_response = MagicMock()
    mock_response.output_text = TOUCHPOINTS_JSON
    mock_response.usage.input_tokens = 600
    mock_response.usage.output_tokens = 400

    mock_http = MagicMock()
    mock_http_response = MagicMock()
    mock_http_response.text = FAKE_HTML
    mock_http_response.status_code = 200
    mock_http.get.return_value = mock_http_response

    with patch("agents.touchpoint_mapper.openai_client") as mock_client, \
         patch("agents.touchpoint_mapper.http_client", mock_http):
        mock_client.responses.create.return_value = mock_response
        map_touchpoints(state, tracker)

    assert tracker.agent_cost("touchpoint_mapper") > 0


def test_map_touchpoints_includes_scraped_html_in_prompt():
    state = _state_with_brand()
    tracker = CostTracker()

    mock_response = MagicMock()
    mock_response.output_text = TOUCHPOINTS_JSON
    mock_response.usage.input_tokens = 600
    mock_response.usage.output_tokens = 400

    mock_http = MagicMock()
    mock_http_response = MagicMock()
    mock_http_response.text = FAKE_HTML
    mock_http_response.status_code = 200
    mock_http.get.return_value = mock_http_response

    with patch("agents.touchpoint_mapper.openai_client") as mock_client, \
         patch("agents.touchpoint_mapper.http_client", mock_http):
        mock_client.responses.create.return_value = mock_response
        map_touchpoints(state, tracker)

    call_kwargs = mock_client.responses.create.call_args.kwargs
    assert "ag1.com" in call_kwargs.get("input", "")
