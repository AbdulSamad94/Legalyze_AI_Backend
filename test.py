from agents import Agent, Runner, OpenAIChatCompletionsModel, AsyncOpenAI, RunConfig
from pydantic import BaseModel
from typing import Literal, Optional, Any, Dict
from dotenv import load_dotenv
import os
from agent_instructions import (
    analysis_agent_instruction,
    summarizer_agent_instructions,
    risk_agent_instructions,
    clause_agent_instructions,
    main_agent_instruction,
    document_detector_agent_instructions,
)
from agents_definitions import (
    risk_detector_agent,
    summarizer_agent,
    clause_checker_agent,
    document_detector_agent,
    friendly_agent,
    casual_chat_agent,
)
from guardrails import final_output_validation_guardrail, sensitive_input_guardrail
from input import user_text
from rich import print


load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set.")

client = AsyncOpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)
model = OpenAIChatCompletionsModel(openai_client=client, model="gemini-2.0-flash")


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
    # document_content: Optional[str] = None


analysis_agent = Agent(
    name="LegalAnalysisAgent",
    instructions=analysis_agent_instruction,
    # input_guardrails=[sensitive_input_guardrail],
    # output_guardrails=[final_output_validation_guardrail],
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
)


main_agent = Agent(
    name="MainLegalAgent",
    instructions=main_agent_instruction,
    model=model,
    # input_guardrails=[sensitive_input_guardrail],
    tools=[
        document_detector_agent.as_tool(
            tool_name="detect_document_type",
            tool_description=document_detector_agent_instructions,
        )
    ],
    output_type=AgentDecision,
)


async def main():

    context = SharedContext(document_text=user_text)
    config = RunConfig(tracing_disabled=True, model=model, model_provider=client)
    decision_result = await Runner.run(
        main_agent, user_text, run_config=config, context=context
    )
    decision: AgentDecision = decision_result.final_output
    print(decision.action)

    final_response_message = ""

    if decision.action == "analyze_document":
        analysis_output = await Runner.run(
            analysis_agent,
            user_text,
            run_config=config,
        )
        print(analysis_output.final_output)

        friendly_output = await Runner.run(
            friendly_agent,
            analysis_output.final_output.model_dump_json(),
            run_config=config,
        )
        final_response_message = friendly_output.final_output.message

    elif decision.action == "casual_chat":
        casual_output = await Runner.run(
            casual_chat_agent, user_text, run_config=config
        )
        final_response_message = casual_output.final_output.message

    elif decision.action == "no_document_found":
        final_response_message = "No document found to analyze."

    print("\n=== Final Response ===")
    print(final_response_message)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
