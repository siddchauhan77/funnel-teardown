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
    "thank_you_page", "call", "checkout", "onboarding", "referral", "other"
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


class Touchpoint(BaseModel):
    platform: Platform
    handle_or_name: str
    url: str
    awareness_level: AwarenessLevel
    is_observed: bool
    confidence: Confidence
    evidence: list[str]


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
    is_observed: bool
    confidence: Confidence
    evidence: list[str]


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
    run_metadata: RunMetadata
