from __future__ import annotations

import uuid
from typing import List, Optional

from pydantic import BaseModel, field_validator, model_validator


class ChatRequest(BaseModel):
    request_id: Optional[str] = None
    user_id: str
    role: str
    doc_id: str
    patient_id: str
    message: str
    security_mode: str = "NORMAL"

    @model_validator(mode="after")
    def assign_request_id(self) -> "ChatRequest":
        if not self.request_id:
            self.request_id = str(uuid.uuid4())
        return self

    @field_validator("security_mode")
    @classmethod
    def validate_security_mode(cls, v: str) -> str:
        allowed = {"NORMAL", "STRICT_MODE", "LOCKDOWN"}
        if v not in allowed:
            raise ValueError(f"security_mode must be one of {allowed}, got '{v}'")
        return v


class IntentDecision(BaseModel):
    intent: str  # TREATMENT | BILLING | ADMIN | UNKNOWN
    needs_patient_context: bool
    confidence: float  # 0.0 – 1.0
    reason: str

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


class PolicyDecision(BaseModel):
    authorized: bool
    scope: str  # FULL | LIMITED_ALLERGIES_MEDS | NONE
    break_glass: bool = False
    reason_code: str = ""
    confidence_score: int = 0
    audit_trail: List[str] = []


class SafetyDecision(BaseModel):
    action: str  # ALLOW | BLOCK
    risk_score: int  # 0 – 100
    phi_exposure_risk: float  # 0.0 – 1.0
    attack_types: List[str] = []
    reason: str = ""

    @field_validator("risk_score")
    @classmethod
    def clamp_risk_score(cls, v: int) -> int:
        return max(0, min(100, v))

    @field_validator("phi_exposure_risk")
    @classmethod
    def clamp_phi_exposure_risk(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


class ResponseDecision(BaseModel):
    final_text: str = ""
    blocked: bool = False
    redaction_count: int = 0
    reason_codes: List[str] = []
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    cost_usd: Optional[float] = None
