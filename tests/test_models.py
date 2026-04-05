import pytest
from pydantic import ValidationError
from models.funnel_map import (
    AwarenessLevel, Confidence, Brand, Touchpoint,
    JourneyStep, Offer, RunMetadata, FunnelMap
)


def test_awareness_level_valid_values():
    valid = ["unaware", "problem_aware", "solution_aware",
             "product_aware", "most_aware", "customer", "advocate"]
    for v in valid:
        assert AwarenessLevel(v) == v


def test_awareness_level_rejects_invalid():
    with pytest.raises(ValueError):
        AwarenessLevel("confused")


def test_brand_requires_name_and_website():
    with pytest.raises(ValidationError):
        Brand(name="", website="", description="d", primary_icp="i",
              confidence="high", evidence=[])


def test_brand_valid():
    b = Brand(
        name="AG1",
        website="ag1.com",
        founder="Chris Ashenden",
        description="Daily greens supplement",
        primary_icp="Health-conscious professionals 25-45",
        confidence="high",
        evidence=["https://ag1.com/about"]
    )
    assert b.name == "AG1"
    assert b.founder == "Chris Ashenden"


def test_touchpoint_valid():
    t = Touchpoint(
        platform="youtube",
        handle_or_name="DrinkAG1",
        url="https://youtube.com/@drinkag1",
        awareness_level="unaware",
        is_observed=True,
        confidence="high",
        evidence=["https://ag1.com"]
    )
    assert t.platform == "youtube"
    assert t.is_observed is True


def test_touchpoint_rejects_invalid_platform():
    with pytest.raises(ValidationError):
        Touchpoint(
            platform="myspace",
            handle_or_name="x",
            url="http://x.com",
            awareness_level="unaware",
            is_observed=True,
            confidence="high",
            evidence=[]
        )


def test_journey_step_valid():
    s = JourneyStep(
        id="step_1",
        label="YouTube ad about energy crashes",
        awareness_level="unaware",
        type="content",
        description="Pre-roll ad targeting people searching for energy tips",
        entry_from=[],
        exits_to=["step_2"],
        whats_working=["Strong hook targeting a universal problem"],
        whats_missing=["No clear CTA to visit site"],
        is_observed=True,
        confidence="high",
        evidence=["https://youtube.com/watch?v=xyz"]
    )
    assert s.id == "step_1"
    assert len(s.whats_working) == 1


def test_offer_price_can_be_none():
    o = Offer(
        name="Free Starter Kit",
        type="lead_magnet",
        headline_or_promise="Get your free 5-day supply",
        target_awareness_level="most_aware",
        price_usd=None,
        connected_step_id="step_3",
        is_observed=True,
        confidence="medium",
        evidence=[]
    )
    assert o.price_usd is None


def test_funnel_map_assembles_correctly():
    brand = Brand(
        name="TestBrand", website="test.com", founder=None,
        description="Test", primary_icp="Testers",
        confidence="low", evidence=[]
    )
    metadata = RunMetadata(
        brand_input="TestBrand",
        hints={},
        timestamp="2026-04-05T14:00:00",
        total_cost_usd=0.0,
        agent_costs={},
        model_used={},
        duration_seconds=0.0
    )
    fm = FunnelMap(
        brand=brand,
        touchpoints=[],
        journey_steps=[],
        offers=[],
        open_questions=["Does TestBrand run paid ads?"],
        run_metadata=metadata
    )
    assert fm.brand.name == "TestBrand"
    assert len(fm.open_questions) == 1
