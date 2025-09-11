from agents import Agent, ModelSettings
from pydantic_models import FinalOutput, AgentDecision
from agent_instructions import (
    analysis_agent_instruction,
    main_agent_instruction,
)
from model import model
from agents_definitions import (
    summarizer_agent,
    risk_detector_agent,
    clause_checker_agent,
    document_detector_agent,
)
from agent_instructions import (
    summarizer_agent_instructions,
    risk_agent_instructions,
    clause_agent_instructions,
    document_detector_agent_instructions,
)
from guardrails import (
    sensitive_input_guardrail,
    final_output_validation_guardrail,
)


def create_analysis_agent() -> Agent:
    """Create and configure the main analysis agent with all sub-agents as tools"""
    return Agent(
        name="LegalAnalysisAgent",
        instructions=analysis_agent_instruction,
        input_guardrails=[sensitive_input_guardrail],
        output_guardrails=[final_output_validation_guardrail],
        output_type=FinalOutput,
        model=model,
        tools=[
            summarizer_agent.as_tool(
                tool_name="summarize_document",
                tool_description=summarizer_agent_instructions,
            ),
            risk_detector_agent.as_tool(
                tool_name="detect_risks",
                tool_description=risk_agent_instructions,
            ),
            clause_checker_agent.as_tool(
                tool_name="check_clause",
                tool_description=clause_agent_instructions,
            ),
        ],
        model_settings=ModelSettings(
            temperature=0.0,
            top_p=0.1,
            max_tokens=1200,
        ),
    )


def create_main_agent() -> Agent:
    """Create and configure the main routing agent"""
    return Agent(
        name="MainLegalAgent",
        instructions=main_agent_instruction,
        model=model,
        input_guardrails=[sensitive_input_guardrail],
        tools=[
            document_detector_agent.as_tool(
                tool_name="detect_document_type",
                tool_description=document_detector_agent_instructions,
            )
        ],
        output_type=AgentDecision,
        model_settings=ModelSettings(
            temperature=0.0,
            top_p=0.1,
            max_tokens=1200,
        ),
    )


analysis_agent = create_analysis_agent()
main_agent = create_main_agent()
