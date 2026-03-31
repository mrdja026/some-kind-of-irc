from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, RootModel

ClaimStatus = Literal[
    "new",
    "pending_documents",
    "investigating",
    "coverage_review",
    "reopened",
    "paid",
    "partially_paid",
    "denied",
    "closed_no_payment",
]

ClaimType = Literal[
    "fire_damage",
    "glass_breakage",
    "smoke_damage",
    "storm_damage",
    "theft",
    "water_damage",
]

ReportedBy = Literal["broker", "insured", "spouse"]
IntakeChannel = Literal["broker_portal", "email", "mobile_app", "phone"]
CoverageDecision = Literal["covered", "not_covered", "pending"]
ResolutionOutcome = Literal["closed_no_payment", "denied", "paid", "partially_paid", "pending"]
PaymentMethod = Literal["bank_transfer", "check"] | None
PolicyProduct = Literal["Condo Protect", "Homeowners Basic", "Homeowners Plus"]
DocumentType = Literal[
    "adjuster_report",
    "claim_form",
    "cleaning_estimate",
    "contents_inventory",
    "fire_report",
    "photo_set",
    "plumber_invoice",
    "police_report",
    "repair_quote",
    "roofer_estimate",
    "weather_report",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CoverageLimits(StrictModel):
    dwelling_eur: int = Field(ge=0)
    contents_eur: int = Field(ge=0)
    water_damage_eur: int = Field(ge=0)


class Insured(StrictModel):
    full_name: str
    email: str
    phone: str
    property_address: str


class Policy(StrictModel):
    product: PolicyProduct
    effective_date: date
    expiration_date: date
    deductible_eur: int = Field(ge=0)
    coverage_limits: CoverageLimits
    endorsements: list[str]
    exclusions: list[str]


class ClaimIntake(StrictModel):
    reported_by: ReportedBy
    channel: IntakeChannel
    summary: str
    cause_of_loss: str
    initial_damage_estimate_eur: Optional[int] = Field(default=None, ge=0)
    emergency_mitigation_completed: Optional[bool] = None
    injuries_reported: bool


class ClaimDocument(StrictModel):
    doc_id: str
    doc_type: DocumentType
    title: str
    created_at: datetime
    file_path: Optional[str] = None


class AdjusterNote(StrictModel):
    timestamp: datetime
    author: str
    note: str


class CoverageReview(StrictModel):
    reviewed_by: str
    decision: CoverageDecision
    reasoning: Optional[str] = None
    applied_deductible_eur: int = Field(ge=0)
    approved_repairs_eur: int = Field(ge=0)
    approved_contents_eur: int = Field(ge=0)


class Resolution(StrictModel):
    resolution_date: date | None
    outcome: ResolutionOutcome
    gross_settlement_eur: int = Field(ge=0)
    deductible_eur: int = Field(ge=0)
    net_payment_eur: int = Field(ge=0)
    payment_method: PaymentMethod
    customer_letter_summary: Optional[str] = None


class Claim(StrictModel):
    claim_id: str
    policy_id: str
    status: ClaimStatus
    claim_type: ClaimType
    loss_date: date
    reported_date: date
    insured: Insured
    policy: Policy
    claim_intake: Optional[ClaimIntake] = None
    documents: Optional[list[ClaimDocument]] = None
    adjuster_notes: Optional[list[AdjusterNote]] = None
    coverage_review: Optional[CoverageReview] = None
    resolution: Optional[Resolution] = None
    conversation_seed_questions: list[str]
    data_path: Optional[str] = None


class ClaimDataset(RootModel[list[Claim]]):
    pass


__all__ = [
    "AdjusterNote",
    "Claim",
    "ClaimDataset",
    "ClaimDocument",
    "ClaimIntake",
    "ClaimStatus",
    "ClaimType",
    "CoverageDecision",
    "CoverageLimits",
    "CoverageReview",
    "DocumentType",
    "Insured",
    "IntakeChannel",
    "PaymentMethod",
    "Policy",
    "PolicyProduct",
    "ReportedBy",
    "Resolution",
    "ResolutionOutcome",
]
