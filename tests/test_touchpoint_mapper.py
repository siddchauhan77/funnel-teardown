import json
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


TOUCHPOINTS_JSON = {
    "touchpoints": [
        {
            "platform": "youtube",
            "handle_or_name": "DrinkAG1",
            "url": "https://youtube.com/@drinkag1",
            "awareness_level": "unaware",
            "is_observed": True,
            "confidence": "high",
            "evidence": ["https://ag1.com"]
        },
        {
            "platform": "instagram",
            "handle_or_name": "@drinkag1",
            "url": "https://instagram.com/drinkag1",
            "awareness_level": "problem_aware",
            "is_observed": True,
            "confidence": "high",
            "evidence": ["https://ag1.com"]
        },
        {
            "platform": "newsletter",
            "handle_or_name": "AG1 Newsletter",
            "url": "https://ag1.com/newsletter",
            "awareness_level": "solution_aware",
            "is_observed": False,
            "confidence": "medium",
            "evidence": []
        }
    ]
}

FAKE_HTML = """
<html><body>
<a href="https://youtube.com/@drinkag1">YouTube</a>
<a href="https://instagram.com/drinkag1">Instagram</a>
<a href="/subscribe">Newsletter</a>
</body></html>
"""


def _make_search_response(text="Found channels for AG1.", in_tok=600, out_tok=400):
    """Mock a single responses.create() web search result (returns prose text)."""
    mock_block = MagicMock()
    mock_block.text = text
    mock_item = MagicMock()
    mock_item.content = [mock_block]
    mock_item.type = "message"
    mock_response = MagicMock()
    mock_response.output = [mock_item]
    mock_response.usage.input_tokens = in_tok
    mock_response.usage.output_tokens = out_tok
    return mock_response


def _make_format_response():
    """Mock chat.completions.create() that returns the structured JSON."""
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(TOUCHPOINTS_JSON)
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    return mock_response


def _setup_client_mock(mock_get_client):
    """Wire up responses.create (search) and chat.completions.create (format)."""
    mock_client = MagicMock()
    mock_client.responses.create.return_value = _make_search_response()
    mock_client.chat.completions.create.return_value = _make_format_response()
    mock_get_client.return_value = mock_client
    return mock_client


def _mock_http():
    mock_http = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = FAKE_HTML
    mock_resp.status_code = 200
    mock_http.get.return_value = mock_resp
    return mock_http


def test_map_touchpoints_populates_state():
    state = _state_with_brand()
    tracker = CostTracker()

    with patch("agents.touchpoint_mapper._get_client") as mock_get_client, \
         patch("agents.touchpoint_mapper.http_client", _mock_http()):
        _setup_client_mock(mock_get_client)
        map_touchpoints(state, tracker)

    assert len(state.funnel_map.touchpoints) == 3
    platforms = [t.platform for t in state.funnel_map.touchpoints]
    assert "youtube" in platforms
    assert "instagram" in platforms
    assert "newsletter" in platforms


def test_map_touchpoints_records_cost():
    state = _state_with_brand()
    tracker = CostTracker()

    with patch("agents.touchpoint_mapper._get_client") as mock_get_client, \
         patch("agents.touchpoint_mapper.http_client", _mock_http()):
        _setup_client_mock(mock_get_client)
        map_touchpoints(state, tracker)

    assert tracker.agent_cost("touchpoint_mapper") > 0


def test_map_touchpoints_runs_multiple_searches():
    """Agent 2 should fire 5 web searches — one per funnel layer."""
    state = _state_with_brand()
    tracker = CostTracker()

    with patch("agents.touchpoint_mapper._get_client") as mock_get_client, \
         patch("agents.touchpoint_mapper.http_client", _mock_http()):
        mock_client = _setup_client_mock(mock_get_client)
        map_touchpoints(state, tracker)

    # Should have called responses.create 5 times (5 targeted searches)
    assert mock_client.responses.create.call_count == 5
    # Should have called chat.completions.create once (formatting pass)
    assert mock_client.chat.completions.create.call_count == 1


def test_map_touchpoints_includes_scraped_html_in_format_prompt():
    """Homepage links should be included in the formatting prompt."""
    state = _state_with_brand()
    tracker = CostTracker()

    with patch("agents.touchpoint_mapper._get_client") as mock_get_client, \
         patch("agents.touchpoint_mapper.http_client", _mock_http()):
        mock_client = _setup_client_mock(mock_get_client)
        map_touchpoints(state, tracker)

    format_call = mock_client.chat.completions.create.call_args
    messages_content = str(format_call)
    assert "ag1.com" in messages_content.lower() or "drinkag1" in messages_content.lower()
