from agents import (
    input_guardrail,
    output_guardrail,
    RunContextWrapper,
    GuardrailFunctionOutput,
    Agent,
    TResponseInputItem,
    Runner,
)
from Logger import SimpleLogger
from pydantic_models import (
    FinalOutput,
    FriendlyMessage,
    SharedContext,
    SensitiveCheckOutput,
)
from model import model
from agent_instructions import guardrail_instructions

sensitive_check_agent = Agent(
    name="SensitiveInfoChecker",
    instructions=guardrail_instructions,
    output_type=SensitiveCheckOutput,
    model=model,
)


@input_guardrail
async def sensitive_input_guardrail(
    ctx: RunContextWrapper[SharedContext],
    agent: Agent,
    input: str | list[TResponseInputItem],
) -> GuardrailFunctionOutput:
    SimpleLogger.log("🛡️ GUARDRAIL", "Checking for sensitive info...")

    if isinstance(input, list):
        user_inputs = [item["content"] for item in input if item["role"] == "user"]
        last_input = user_inputs[-1] if user_inputs else ""
    else:
        last_input = input

    if not ctx.context:
        ctx.context = SharedContext(document_text=last_input)
    else:
        ctx.context.document_text = last_input

    result = await Runner.run(sensitive_check_agent, last_input)

    SimpleLogger.log(
        "🛡️ GUARDRAIL",
        f"Result: {'BLOCKED' if result.final_output.contains_sensitive_info else 'PASSED'}",
    )

    return GuardrailFunctionOutput(
        output_info=result.final_output,
        tripwire_triggered=result.final_output.contains_sensitive_info,
    )


@output_guardrail
async def final_output_validation_guardrail(
    ctx: RunContextWrapper[SharedContext],
    agent: Agent,
    output: FinalOutput,
) -> GuardrailFunctionOutput:
    SimpleLogger.log("🛡️ FINAL_OUTPUT_GUARDRAIL", "Validating final analysis output...")

    has_summary = bool(output.summary and len(output.summary.strip()) > 10)
    has_risks = output.risks is not None and isinstance(output.risks, list)
    has_verdict = bool(output.verdict and len(output.verdict.strip()) > 5)
    has_disclaimer = bool(output.disclaimer and len(output.disclaimer.strip()) > 10)

    is_valid = has_summary and has_risks and has_verdict and has_disclaimer

    SimpleLogger.log(
        "🛡️ FINAL_OUTPUT_GUARDRAIL",
        f"Summary: {'✓' if has_summary else '✗'} | "
        f"Risks: {'✓' if has_risks else '✗'} | "
        f"Verdict: {'✓' if has_verdict else '✗'} | "
        f"Disclaimer: {'✓' if has_disclaimer else '✗'} | "
        f"Result: {'VALID' if is_valid else 'INVALID'}",
    )

    return GuardrailFunctionOutput(
        output_info={
            "validation_passed": is_valid,
            "summary_valid": has_summary,
            "risks_valid": has_risks,
            "verdict_valid": has_verdict,
            "disclaimer_valid": has_disclaimer,
        },
        tripwire_triggered=not is_valid,
    )


@output_guardrail
async def friendly_message_validation_guardrail(
    ctx: RunContextWrapper[SharedContext],
    agent: Agent,
    output: FriendlyMessage,
) -> GuardrailFunctionOutput:
    SimpleLogger.log(
        "🛡️ FRIENDLY_OUTPUT_GUARDRAIL", "Validating friendly message output..."
    )

    has_message = bool(output.message and len(output.message.strip()) > 5)
    is_not_too_long = len(output.message) < 2000

    contains_inappropriate = any(
        word in output.message.lower()
        for word in ["i cannot", "i can't", "sorry, i cannot", "i'm unable to"]
    )

    is_valid = has_message and is_not_too_long and not contains_inappropriate

    SimpleLogger.log(
        "🛡️ FRIENDLY_OUTPUT_GUARDRAIL",
        f"Has message: {'✓' if has_message else '✗'} | "
        f"Length OK: {'✓' if is_not_too_long else '✗'} | "
        f"Appropriate: {'✓' if not contains_inappropriate else '✗'} | "
        f"Result: {'VALID' if is_valid else 'INVALID'}",
    )

    return GuardrailFunctionOutput(
        output_info={
            "validation_passed": is_valid,
            "has_message": has_message,
            "length_ok": is_not_too_long,
            "appropriate_content": not contains_inappropriate,
        },
        tripwire_triggered=not is_valid,
    )
