from agents import Agent, ModelSettings
from model import model
from agent_instructions import (
    summarizer_agent_instructions,
    risk_agent_instructions,
    clause_agent_instructions,
    document_detector_agent_instructions,
    friendly_agent_instruction,
    casual_chat_agent_instruction,
)
from pydantic_models import (
    RiskOutput,
    SummaryOutput,
    DocumentCheckOutput,
    FriendlyMessage,
)
from guardrails import friendly_message_validation_guardrail


summarizer_agent = Agent(
    name="SummarizerAgent",
    instructions=summarizer_agent_instructions,
    output_type=SummaryOutput,
    model=model,
    model_settings=ModelSettings(
        temperature=0.0,
        top_p=0.1,
        max_tokens=1200,
    ),
)

risk_detector_agent = Agent(
    name="RiskDetectorAgent",
    instructions=risk_agent_instructions,
    output_type=RiskOutput,
    model=model,
    model_settings=ModelSettings(
        temperature=0.0,
        top_p=0.1,
        max_tokens=1200,
    ),
)

clause_checker_agent = Agent(
    name="ClauseCheckerAgent",
    instructions=clause_agent_instructions,
    output_type=str,
    model=model,
    model_settings=ModelSettings(
        temperature=0.0,
        top_p=0.1,
        max_tokens=1200,
    ),
)

document_detector_agent = Agent(
    name="DocumentDetector",
    instructions=document_detector_agent_instructions,
    output_type=DocumentCheckOutput,
    model=model,
    model_settings=ModelSettings(
        temperature=0.0,
        top_p=0.1,
        max_tokens=1200,
    ),
)

friendly_agent = Agent(
    name="FriendlyResponseAgent",
    instructions=friendly_agent_instruction,
    output_type=FriendlyMessage,
    output_guardrails=[friendly_message_validation_guardrail],
    model=model,
    model_settings=ModelSettings(
        temperature=0.0,
        top_p=0.1,
        max_tokens=1200,
    ),
)

casual_chat_agent = Agent(
    name="CasualChatAgent",
    instructions=casual_chat_agent_instruction,
    output_type=FriendlyMessage,
    output_guardrails=[friendly_message_validation_guardrail],
    model=model,
    model_settings=ModelSettings(
        temperature=0.0,
        top_p=0.1,
        max_tokens=1200,
    ),
)
