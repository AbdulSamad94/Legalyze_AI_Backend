from agents import Agent, ModelSettings
from model import model
from agent_instructions import (
    summarizer_agent_instructions,
    risk_agent_instructions,
    clause_agent_instructions,
    document_detector_agent_instructions,
)
from pydantic_models import (
    RiskOutput,
    SummaryOutput,
    DocumentCheckOutput,
)


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
