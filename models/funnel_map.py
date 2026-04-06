from __future__ import annotations
from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel


class AwarenessLevel(str, Enum):
    unaware = "unaware"
    problem_aware = "problem_aware"
    solution_aware = "solution_aware"
    product_aware = "product_aware"
    most_aware = "most_aware"
    customer = "customer"
    advocate = "advocate"


Confidence = Literal["high", "medium", "low"]

Platform = Literal[
    "youtube", "linkedin", "instagram", "tiktok",
    "newsletter", "blog", "podcast", "seo", "paid_ads", "twitter", "other"
]

StepType = Literal[
    "content", "landing_page", "lead_magnet", "email_sequence",
    "thank_you_page", "call", "checkout", "onboarding", "referral",
    "live_event", "other"
]

OfferType = Literal[
    "lead_magnet", "free_trial", "low_ticket", "core_product",
    "upsell", "subscription", "high_ticket", "other"
]


class Brand(BaseModel):
    name: str
    website: str
    founder: Optional[str] = None
    description: str
    primary_icp: str
    confidence: Confidence
    evidence: list[str]
    # Visual branding extracted from homepage (populated by touchpoint_mapper)
    theme_color: Optional[str] = None   # e.g. "#1DB954" from <meta name="theme-color">
    logo_url: Optional[str] = None      # e.g. og:image URL


class Touchpoint(BaseModel):
    platform: Platform
    handle_or_name: str
    url: str
    awareness_level: AwarenessLevel
    is_observed: bool
    confidence: Confidence
    evidence: list[str]


ValueLadderRung = Literal["free", "entry", "core", "high_ticket", "continuity"]


class JourneyStep(BaseModel):
    id: str
    label: str
    awareness_level: AwarenessLevel
    type: StepType
    description: str
    entry_from: list[str]
    exits_to: list[str]
    whats_working: list[str]
    whats_missing: list[str]
    # Brunson frameworks
    value_ladder_rung: ValueLadderRung = "free"
    hook: str = ""       # What grabs attention / stops the scroll at this step
    story: str = ""      # What belief shift / proof is being built
    offer_cta: str = ""  # What action is being asked for / what's being presented
    is_observed: bool = True
    confidence: Confidence = "medium"
    evidence: list[str] = []


class Offer(BaseModel):
    name: str
    type: OfferType
    headline_or_promise: str
    target_awareness_level: AwarenessLevel
    price_usd: Optional[float] = None
    connected_step_id: str
    is_observed: bool
    confidence: Confidence
    evidence: list[str]


class RunMetadata(BaseModel):
    brand_input: str
    hints: dict
    timestamp: str
    total_cost_usd: float
    agent_costs: dict[str, float]
    model_used: dict[str, str]
    duration_seconds: float


class FunnelMap(BaseModel):
    brand: Brand
    touchpoints: list[Touchpoint]
    journey_steps: list[JourneyStep]
    offers: list[Offer]
    open_questions: list[str]
    worth_stealing: list[str] = []
    learning_opportunities: list[str] = []
    ascension_path: str = ""  # One-sentence narrative of the full value ladder climb
    run_metadata: RunMetadata
