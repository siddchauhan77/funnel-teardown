import json
import pytest
from unittest.mock import MagicMock, patch
from agents.journey_mapper import map_journey
from state.teardown_state import TeardownState
from utils.cost_tracker import CostTracker
from models.funnel_map import Brand, Touchpoint


def _state_with_brand_and_touchpoints() -> TeardownState:
    state = TeardownState.new("Athletic Greens", hints={})
    state.funnel_map.brand = Brand(
        name="AG1", website="https://ag1.com", founder="Chris Ashenden",
        description="Daily greens supplement", primary_icp="Health-conscious adults",
        confidence="high", evidence=[]
    )
    state.funnel_map.touchpoints = [
        Touchpoint(
            platform="youtube", handle_or_name="DrinkAG1",
            url="https://youtube.com/@drinkag1",
            awareness_level="unaware", is_observed=True,
            confidence="high", evidence=[]
        ),
        Touchpoint(
            platform="newsletter", handle_or_name="AG1 Newsletter",
            url="https://ag1.com/subscribe",
            awareness_level="solution_aware", is_observed=True,
            confidence="high", evidence=[]
        ),
    ]
    return state


JOURNEY_JSON = json.dumps({
    "journey_steps": [
        {
            "id": "step_1",
            "label": "YouTube ad — 'Why your energy crashes at 2pm'",
            "awareness_level": "unaware",
            "type": "content",
            "description": "Pre-roll ads targeting people who haven't heard of AG1.",
            "entry_from": [],
            "exits_to": ["step_2"],
            "whats_working": ["Universal hook targeting a felt problem"],
            "whats_missing": ["No soft CTA to learn more"],
            "is_observed": True,
            "confidence": "high",
            "evidence": ["https://youtube.com/@drinkag1"]
        },
        {
            "id": "step_2",
            "label": "AG1 homepage — subscribe & save CTA",
            "awareness_level": "most_aware",
            "type": "landing_page",
            "description": "Homepage drives subscription purchase with free shaker offer.",
            "entry_from": ["step_1"],
            "exits_to": ["step_3"],
            "whats_working": ["Strong risk reversal: 90-day money-back guarantee"],
            "whats_missing": ["No lead magnet for people not ready to buy"],
            "is_observed": True,
            "confidence": "high",
            "evidence": ["https://ag1.com"]
        }
    ],
    "offers": [
        {
            "name": "AG1 Subscription",
            "type": "subscription",
            "headline_or_promise": "The all-in-one daily nutrition habit",
            "target_awareness_level": "most_aware",
            "price_usd": 79.0,
            "connected_step_id": "step_2",
            "is_observed": True,
            "confidence": "high",
            "evidence": ["https://ag1.com/products"]
        }
    ],
    "open_questions": [
        "Does AG1 run Facebook/Instagram retargeting for cart abandoners?",
        "Is there an email nurture sequence between opt-in and first purchase?"
    ]
})


def test_map_journey_populates_steps_and_offers():
    state = _state_with_brand_and_touchpoints()
    tracker = CostTracker()

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=JOURNEY_JSON)]
    mock_response.usage.input_tokens = 3000
    mock_response.usage.output_tokens = 1500

    with patch("agents.journey_mapper.anthropic_client") as mock_client:
        mock_client.messages.create.return_value = mock_response
        map_journey(state, tracker)

    assert len(state.funnel_map.journey_steps) == 2
    assert len(state.funnel_map.offers) == 1
    assert len(state.funnel_map.open_questions) == 2
    assert state.funnel_map.journey_steps[0].id == "step_1"


def test_map_journey_records_cost():
    state = _state_with_brand_and_touchpoints()
    tracker = CostTracker()

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=JOURNEY_JSON)]
    mock_response.usage.input_tokens = 3000
    mock_response.usage.output_tokens = 1500

    with patch("agents.journey_mapper.anthropic_client") as mock_client:
        mock_client.messages.create.return_value = mock_response
        map_journey(state, tracker)

    assert tracker.agent_cost("journey_mapper") > 0


def test_map_journey_whats_working_populated():
    state = _state_with_brand_and_touchpoints()
    tracker = CostTracker()

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=JOURNEY_JSON)]
    mock_response.usage.input_tokens = 3000
    mock_response.usage.output_tokens = 1500

    with patch("agents.journey_mapper.anthropic_client") as mock_client:
        mock_client.messages.create.return_value = mock_response
        map_journey(state, tracker)

    step = state.funnel_map.journey_steps[0]
    assert len(step.whats_working) > 0
    assert len(step.whats_missing) > 0
