from pydantic import BaseModel, Field
from typing import List, Dict
from datetime import datetime
from enum import Enum

# -------------------------------------------------------
# Note:
# Gemini ko bhejne wale output models me Optional/Any na rakho.
# Datetime ko ISO string me rakho.
# -------------------------------------------------------


# ---------- Non-Gemini utility enums/models (safe to keep) ----------
class ProcessingStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


# Yeh API side pe kaam aayega, Gemini ke output_type me use mat karna
class DocumentInsights(BaseModel):
    word_count: int
    character_count: int
    estimated_pages: int
    estimated_read_time: int
    document_type: str = ""  # avoid Optional
    confidence_score: float = 0.0  # avoid Optional


# ---------- Gemini output models (STRICT, no Optional/Any) ----------
class SensitiveCheckOutput(BaseModel):
    contains_sensitive_info: bool
    reasoning: str
    flagged_content_types: List[str] = Field(default_factory=list)


class SummaryOutput(BaseModel):
    summary: str
    key_points: List[str] = Field(default_factory=list)


class RiskItem(BaseModel):
    description: str
    level: str  # "low" | "medium" | "high" | "critical"
    category: str  # "Financial" | "Legal" etc.
    recommendation: str
    clause_reference: str = ""  # no Optional


class RiskOutput(BaseModel):
    risks: List[RiskItem] = Field(default_factory=list)
    overall_risk_level: str = "low"


class FinalOutput(BaseModel):
    summary: str
    risks: List[RiskItem] = Field(default_factory=list)
    verdict: str
    disclaimer: str = (
        "This analysis is for informational purposes only and does not constitute "
        "legal advice. Please consult with a qualified attorney."
    )
    confidence_score: float = 0.8
    processed_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class FriendlyMessage(BaseModel):
    message: str
    tone: str = "friendly"  # no Optional


class DocumentCheckOutput(BaseModel):
    is_legal_document: bool
    document_type: str
    reasoning: str
    confidence_score: float


class AgentDecision(BaseModel):
    # allowed: "analyze_document" | "casual_chat" | "no_document_found"
    action: str
    reasoning: str
    confidence_score: float = 0.8


# ---------- API-layer models (not used as Gemini output_type) ----------
# In models below Optional/Dict is acceptable kyun ke ye Gemini ko schema me nahi ja rahe.
class AnalysisResult(BaseModel):
    # "legal_analysis" | "casual_response" | "error"
    type: str
    # Loose containers for your REST responses only
    document_info: Dict[str, str] = Field(default_factory=dict)
    # FinalOutput ko yahan optional rakhne se Gemini par asar nahi hota
    analysis: FinalOutput | None = None
    friendly_message: str | None = None
    session_id: str
    processed_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class APIResponse(BaseModel):
    success: bool
    message: str
    data: Dict[str, str] | None = None
    error: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# Context model Gemini ko output_type me mat dena
class SharedContext(BaseModel):
    document_text: str
    analysis_stage: str = "starting"
    previous_outputs: Dict[str, str] = Field(default_factory=dict)  # no Any
    session_id: str | None = None
    document_insights: DocumentInsights | None = None
