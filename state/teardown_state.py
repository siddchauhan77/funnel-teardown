from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from models.funnel_map import (
    FunnelMap, Brand, RunMetadata
)

TMP_DIR = Path(".tmp")


def slug_for(brand_name: str) -> str:
    """Normalize a brand name to a filesystem-safe slug."""
    s = brand_name.lower().strip()
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+", "_", s).strip("_")
    return s


class TeardownState(BaseModel):
    brand_input: str
    slug: str
    hints: dict
    funnel_map: FunnelMap

    @classmethod
    def new(cls, brand_input: str, hints: dict) -> "TeardownState":
        sl = slug_for(brand_input)
        empty_map = FunnelMap(
            brand=Brand(
                name="", website="", founder=None,
                description="", primary_icp="",
                confidence="low", evidence=[]
            ),
            touchpoints=[],
            journey_steps=[],
            offers=[],
            open_questions=[],
            run_metadata=RunMetadata(
                brand_input=brand_input,
                hints=hints,
                timestamp="",
                total_cost_usd=0.0,
                agent_costs={},
                model_used={},
                duration_seconds=0.0
            )
        )
        return cls(brand_input=brand_input, slug=sl, hints=hints, funnel_map=empty_map)

    @property
    def cache_path(self) -> Path:
        return TMP_DIR / f"{self.slug}_state.json"

    def save(self) -> None:
        TMP_DIR.mkdir(exist_ok=True)
        self.cache_path.write_text(
            self.model_dump_json(indent=2), encoding="utf-8"
        )

    @classmethod
    def load(cls, brand_input: str) -> Optional["TeardownState"]:
        sl = slug_for(brand_input)
        path = TMP_DIR / f"{sl}_state.json"
        if not path.exists():
            return None
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
