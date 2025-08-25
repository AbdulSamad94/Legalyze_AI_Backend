from pydantic import BaseModel
from typing import Literal, Optional, Any, Dict


class SensitiveCheckOutput(BaseModel):
    """Output for checking sensitive information."""

    contains_sensitive_info: bool
    reasoning: str


class SummaryOutput(BaseModel):
    """Contains the summarized text of a document."""

    summary: str


class RiskOutput(BaseModel):
    """Contains a list of identified risks."""

    risks: list[str]


class FinalOutput(BaseModel):
    """The final, consolidated analysis output for a legal document."""

    summary: str
    risks: list[str]
    verdict: str
    disclaimer: str = (
        "This summary is for informational purposes only and does not constitute legal advice."
    )


class FriendlyMessage(BaseModel):
    """A friendly, conversational message for the user."""

    message: str


class SharedContext(BaseModel):
    """Shared context passed between agents during a run."""

    document_text: str
    analysis_stage: str = "starting"
    previous_outputs: Dict[str, Any] = {}


class DocumentCheckOutput(BaseModel):
    """Output after checking if a text is a legal document."""

    is_legal_document: bool
    document_type: str
    reasoning: str


class AgentDecision(BaseModel):
    """Represents the main agent's decision on how to proceed."""

    action: Literal["analyze_document", "casual_chat", "no_document_found"]
    reasoning: str = ""
