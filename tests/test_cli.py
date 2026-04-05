import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from models.funnel_map import (
    Brand, Touchpoint, JourneyStep, Offer, RunMetadata, FunnelMap
)


def _mock_brand_resolver(state, tracker):
    state.funnel_map.brand = Brand(
        name="AG1", website="https://ag1.com", founder="Chris Ashenden",
        description="Greens supplement", primary_icp="Health-conscious adults",
        confidence="high", evidence=[]
    )
    tracker.record("brand_resolver", "gpt-4o-mini-search-preview",
                   input_tokens=500, output_tokens=200)


def _mock_touchpoint_mapper(state, tracker):
    state.funnel_map.touchpoints = [
        Touchpoint(
            platform="youtube", handle_or_name="DrinkAG1",
            url="https://youtube.com/@drinkag1",
            awareness_level="unaware", is_observed=True,
            confidence="high", evidence=[]
        )
    ]
    tracker.record("touchpoint_mapper", "gpt-4o-mini-search-preview",
                   input_tokens=600, output_tokens=300)


def _mock_journey_mapper(state, tracker):
    state.funnel_map.journey_steps = [
        JourneyStep(
            id="step_1", label="YouTube ad", awareness_level="unaware",
            type="content", description="Pre-roll ad",
            entry_from=[], exits_to=[],
            whats_working=["Strong hook"], whats_missing=["No CTA"],
            is_observed=True, confidence="high", evidence=[]
        )
    ]
    state.funnel_map.offers = [
        Offer(
            name="AG1 Sub", type="subscription",
            headline_or_promise="Daily nutrition", target_awareness_level="most_aware",
            price_usd=79.0, connected_step_id="step_1",
            is_observed=True, confidence="high", evidence=[]
        )
    ]
    state.funnel_map.open_questions = ["Does AG1 run Facebook ads?"]
    tracker.record("journey_mapper", "claude-sonnet-4-6",
                   input_tokens=3000, output_tokens=1500)


def _patched_run(tmp_path, brand_name="Athletic Greens"):
    """Helper: run teardown with output and cache in isolated subdirs."""
    out_dir = tmp_path / "output"
    cache_dir = tmp_path / ".tmp"
    with patch("teardown.OUTPUT_DIR", out_dir), \
         patch("teardown.resolve_brand", side_effect=_mock_brand_resolver), \
         patch("teardown.map_touchpoints", side_effect=_mock_touchpoint_mapper), \
         patch("teardown.map_journey", side_effect=_mock_journey_mapper), \
         patch("state.teardown_state.TMP_DIR", cache_dir):
        from teardown import run_teardown
        run_teardown(brand_name, hints={})
    return out_dir


def test_full_pipeline_produces_output_files(tmp_path):
    """End-to-end: all 3 agents mocked, verify output files are created."""
    out_dir = _patched_run(tmp_path)
    output_dirs = list(out_dir.glob("athletic_greens_*"))
    assert len(output_dirs) == 1
    output_dir = output_dirs[0]
    assert (output_dir / "funnel_map.json").exists()
    assert (output_dir / "teardown_report.html").exists()


def test_output_json_is_valid_funnel_map(tmp_path):
    """funnel_map.json should be parseable as a FunnelMap."""
    out_dir = _patched_run(tmp_path)
    output_dir = list(out_dir.glob("athletic_greens_*"))[0]
    data = json.loads((output_dir / "funnel_map.json").read_text())
    fm = FunnelMap.model_validate(data)
    assert fm.brand.name == "AG1"
    assert len(fm.touchpoints) == 1
    assert len(fm.journey_steps) == 1


def test_html_report_contains_brand_name(tmp_path):
    out_dir = _patched_run(tmp_path)
    output_dir = list(out_dir.glob("athletic_greens_*"))[0]
    html = (output_dir / "teardown_report.html").read_text()
    assert "AG1" in html
    assert "mermaid" in html.lower()
