from pydantic import BaseModel
from typing import Literal
from datetime import datetime
from uuid import UUID


# --- Users ---

class Profiles(BaseModel):
    user_id: UUID
    email: str
    name: str
    role: Literal["client", "freelancer"]
    created_at: datetime


class ClientProfile(BaseModel):
    client_profile_id: UUID
    user_id: UUID
    company_name: str | None
    industry: str | None


class FreelancerProfile(BaseModel):
    freelancer_profile_id: UUID
    user_id: UUID
    skills: list[str]
    years_experience: int
    rate_expectation: float



# --- Subscription ---

class Subscription(BaseModel):
    subscription_id: UUID
    user_id: UUID
    plan: Literal["free", "pro", "agency"]
    status: Literal["active", "cancelled", "past_due"]
    started_at: datetime
    renews_at: datetime | None



# --- Project ---

class Project(BaseModel):
    project_id: UUID
    client_profile_id: UUID
    freelancer_profile_id: UUID | None
    title: str
    description: str | None
    status: Literal[
        "draft",
        "requirements_extracted",
        "clarifications_pending",
        "pricing_ready",
        "negotiating",
        "contract_generated",
        "signed",
        "completed",
        "cancelled"
    ]
    created_at: datetime
    ai_processing_status: Literal["pending", "processing", "done", "failed"] = "pending"
    error_message: str | None = None



class ProjectVersion(BaseModel):
    version_id: UUID
    project_id: UUID
    version_number: int
    created_at: datetime



# --- Requirements ---

class Requirement(BaseModel):
    requirement_id: UUID
    version_id: UUID
    type: str
    value: str
    timeline: str | None
    budget_hint: float | None
    confidence: float



class Deliverable(BaseModel):
    deliverable_id: UUID
    requirement_id: UUID
    text: str
    priority: Literal["High", "Medium", "Low"]
    status: Literal["Delivered", "Pending"]
    estimated_hours: float



class Gap(BaseModel):
    gap_id: UUID
    requirement_id: UUID
    description: str



class ClarificationRequest(BaseModel):
    clarification_id: UUID
    gap_id: UUID
    question_text: str
    answer_text: str | None
    status: Literal["pending", "answered"]
    asked_at: datetime
    answered_at: datetime | None
    answered_by: UUID | None



class FieldConflict(BaseModel):
    conflict_id: UUID
    requirement_id: UUID
    field_name: str
    old_value: str
    new_value: str
    detected_at: datetime
    resolved: bool



# --- Scope ---

class ScopeDocument(BaseModel):
    scope_id: UUID
    project_id: UUID



class ScopeItem(BaseModel):
    scope_item_id: UUID
    scope_id: UUID

    item_type: Literal[
        "included",
        "excluded",
        "assumption"
    ]

    text: str



# --- Milestones ---

class Milestone(BaseModel):
    milestone_id: UUID
    project_id: UUID

    title: str
    description: str

    amount: float
    due_date: datetime

    sequence: int

    status: Literal[
        "pending",
        "completed"
    ]



class ChangeOrder(BaseModel):
    change_order_id: UUID
    milestone_id: UUID

    requested_by: Literal[
        "client",
        "freelancer"
    ]

    description: str

    delta_amount: float

    status: Literal[
        "proposed",
        "approved",
        "rejected"
    ]

    created_at: datetime



# --- Pricing ---

class PriceFloor(BaseModel):
    price_floor_id: UUID
    version_id: UUID

    amount: float
    reasoning: str

    confidence: float



class Comparable(BaseModel):
    comparable_id: UUID
    price_floor_id: UUID

    text: str

    source: str | None
    url: str | None

    price: float | None

    similarity_rank: int | None



class HumanPriceAdjustment(BaseModel):
    adjustment_id: UUID
    price_floor_id: UUID

    adjusted_amount: float

    adjusted_by: UUID

    reason: str

    adjusted_at: datetime



# --- Negotiation ---

class NegotiationState(BaseModel):
    negotiation_id: UUID
    project_id: UUID

    floor: float
    ceiling: float

    current_offer: float

    round_count: int

    status: Literal[
        "open",
        "converged",
        "capped_no_deal"
    ]



class NegotiationRound(BaseModel):
    round_id: UUID
    negotiation_id: UUID

    round_number: int

    actor: Literal[
        "client",
        "freelancer",
        "mediator"
    ]

    offer: float

    message: str

    timestamp: datetime



# --- Risk ---

class Risk(BaseModel):
    risk_id: UUID
    version_id: UUID

    category: Literal[
        "Technical",
        "Timeline",
        "Scope",
        "Budget",
        "Communication",
        "All"
    ]

    score: float

    text: str



# --- Signing ---

class Signature(BaseModel):
    signature_id: UUID
    project_id: UUID

    signer_role: Literal[
        "client",
        "freelancer"
    ]

    signed_at: datetime



# --- Processing ---

class ProcessingLock(BaseModel):
    project_id: UUID

    locked: bool

    locked_at: datetime | None
    locked_by: UUID | None



# --- AI Logs ---

class GemmaCallLog(BaseModel):
    call_id: UUID
    project_id: UUID

    agent_name: str
    purpose: str

    latency_ms: int

    success: bool



class RankingLog(BaseModel):
    log_id: UUID
    project_id: UUID

    query_text: str
    comparable_text: str

    similarity_score: float

    ran_on_gpu: bool



# --- Contract ---

class Contract(BaseModel):
    contract_id: UUID
    project_id: UUID

    version: int

    storage_path: str

    file_type: Literal[
        "pdf",
        "md"
    ]

    status: Literal[
        "draft",
        "signed",
        "archived"
    ]

    generated_by: str

    generated_at: datetime



# --- Notifications ---

class Notification(BaseModel):
    notification_id: UUID
    user_id: UUID

    notification_type: Literal[
        "Urgent",
        "Priority",
        "Project Related"
    ]

    read: bool
    text: str
    created_at: datetime









