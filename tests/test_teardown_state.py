import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from state.teardown_state import TeardownState, slug_for
from models.funnel_map import Brand, RunMetadata, FunnelMap


def _minimal_funnel_map(brand_input: str = "TestBrand") -> FunnelMap:
    return FunnelMap(
        brand=Brand(
            name="TestBrand", website="test.com", founder=None,
            description="Test", primary_icp="Testers",
            confidence="low", evidence=[]
        ),
        touchpoints=[],
        journey_steps=[],
        offers=[],
        open_questions=[],
        run_metadata=RunMetadata(
            brand_input=brand_input,
            hints={},
            timestamp="2026-04-05T00:00:00",
            total_cost_usd=0.0,
            agent_costs={},
            model_used={},
            duration_seconds=0.0
        )
    )


def test_slug_for_normalizes_brand_name():
    assert slug_for("Athletic Greens") == "athletic_greens"
    assert slug_for("AG1") == "ag1"
    assert slug_for("  spaces  ") == "spaces"
    assert slug_for("Blaine 'The Dating Coach'") == "blaine_the_dating_coach"


def test_new_state_has_empty_funnel_map():
    state = TeardownState.new("TestBrand", hints={})
    assert state.funnel_map.brand.name == ""
    assert state.funnel_map.touchpoints == []
    assert state.slug == "testbrand"


def test_save_and_load_roundtrip(tmp_path):
    state = TeardownState.new("TestBrand", hints={"founder": "Alice"})
    state.funnel_map = _minimal_funnel_map()

    with patch("state.teardown_state.TMP_DIR", tmp_path):
        state.save()
        loaded = TeardownState.load("TestBrand")

    assert loaded.funnel_map.brand.name == "TestBrand"
    assert loaded.hints == {"founder": "Alice"}


def test_load_returns_none_if_no_cache(tmp_path):
    with patch("state.teardown_state.TMP_DIR", tmp_path):
        result = TeardownState.load("NonExistentBrand")
    assert result is None


def test_cache_file_path():
    state = TeardownState.new("Athletic Greens", hints={})
    assert state.cache_path.name == "athletic_greens_state.json"
