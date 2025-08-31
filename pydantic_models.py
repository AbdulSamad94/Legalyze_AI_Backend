from pydantic import BaseModel, Field
from typing import List, Dict
from datetime import datetime
from enum import Enum


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentInsights(BaseModel):
    word_count: int
    character_count: int
    estimated_pages: int
    estimated_read_time: int
    document_type: str = ""
    confidence_score: float = 0.0


class SensitiveCheckOutput(BaseModel):
    contains_sensitive_info: bool
    reasoning: str
    flagged_content_types: List[str] = Field(default_factory=list)


class SummaryOutput(BaseModel):
    summary: str
    key_points: List[str] = Field(default_factory=list)


class RiskItem(BaseModel):
    description: str
    level: str
    category: str
    recommendation: str
    clause_reference: str = ""


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
    tone: str = "friendly"


class DocumentCheckOutput(BaseModel):
    is_legal_document: bool
    document_type: str
    reasoning: str
    confidence_score: float


class AgentDecision(BaseModel):
    action: str
    reasoning: str
    confidence_score: float = 0.8


class AnalysisResult(BaseModel):
    type: str
    document_info: Dict[str, str] = Field(default_factory=dict)
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


class SharedContext(BaseModel):
    document_text: str
    analysis_stage: str = "starting"
    previous_outputs: Dict[str, str] = Field(default_factory=dict)
    session_id: str | None = None
    document_insights: DocumentInsights | None = None
