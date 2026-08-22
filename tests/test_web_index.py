from pathlib import Path


WEB_INDEX = Path("web/index.html")


def _html() -> str:
    return WEB_INDEX.read_text(encoding="utf-8")


def test_homepage_maps_user_journey():
    html = _html()

    for text in [
        "Give a brand",
        "Choose depth",
        "Map the funnel",
        "Use the report",
        "Selected mode",
        "Report output",
    ]:
        assert text in html


def test_homepage_explains_report_outputs():
    html = _html()

    for text in [
        "Game Scorecard",
        "Journey Map",
        "Source Links",
        "Exports",
        "Download HTML, JSON, or save as PDF.",
    ]:
        assert text in html


def test_guide_includes_scorecard_section():
    html = _html()

    assert "What is the funnel's current score, and what should improve first?" in html
    assert "Journey Coverage, Offer Ladder, Conversion Clarity, Evidence Quality, and Retention Loop" in html


def test_homepage_uses_native_design_system_typography():
    html = _html()

    assert "fonts.googleapis.com" not in html
    assert "font-family: -apple-system" in html
    assert "clamp(" not in html
    assert "letter-spacing: -" not in html
