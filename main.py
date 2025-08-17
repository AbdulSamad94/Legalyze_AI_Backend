import asyncio
import os
import sys
import logging
import json
from typing import Optional, AsyncGenerator
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
import tempfile

from agents import (
    Agent,
    Runner,
    RunConfig,
    InputGuardrailTripwireTriggered,
    OutputGuardrailTripwireTriggered,
)
from pydantic_models import (
    FinalOutput,
    SharedContext,
    AgentDecision,
)
from agent_instructions import (
    analysis_agent_instruction,
    summarizer_agent_instructions,
    risk_agent_instructions,
    clause_agent_instructions,
    document_detector_agent_instructions,
    main_agent_instruction,
)
from model import model, client
from agents_definitions import (
    summarizer_agent,
    risk_detector_agent,
    clause_checker_agent,
    document_detector_agent,
    friendly_agent,
    casual_chat_agent,
)
from guardrails import (
    sensitive_input_guardrail,
    final_output_validation_guardrail,
)
from Logger import SimpleLogger
from converter import (
    extract_text_from_pdf,
    extract_text_from_docx,
    extract_text_from_txt,
    try_ocr_from_image,
    try_ocr_from_scanned_pdf,
)


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://*.vercel.app",
        "https://legalyze-ai.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPPORTED_TEXT_EXTS = {".txt"}
SUPPORTED_DOC_EXTS = {".docx"}
SUPPORTED_PDF_EXTS = {".pdf"}
SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".tiff"}


def load_text_from_path(path: str) -> Optional[str]:
    """Return extracted text for supported file types, otherwise None."""
    if not path:
        return None
    if not os.path.exists(path):
        SimpleLogger.log("❌ FILE", f"Not found: {path}")
        return None

    ext = os.path.splitext(path)[1].lower()

    if ext in SUPPORTED_TEXT_EXTS:
        SimpleLogger.log("📄 FILE", f"TXT detected: {path}")
        return extract_text_from_txt(path)
    if ext in SUPPORTED_DOC_EXTS:
        SimpleLogger.log("📄 FILE", f"DOCX detected: {path}")
        return extract_text_from_docx(path)
    if ext in SUPPORTED_PDF_EXTS:
        SimpleLogger.log("📄 FILE", f"PDF detected: {path}")
        text = extract_text_from_pdf(path)
        if text and len(text.strip()) >= 30:
            return text
        SimpleLogger.log("🔍 OCR", "PDF appears scanned or text-light, trying OCR...")
        ocr_text = try_ocr_from_scanned_pdf(path)
        return ocr_text
    if ext in SUPPORTED_IMAGE_EXTS:
        SimpleLogger.log("🖼️ FILE", f"Image detected: {path}, running OCR...")
        return try_ocr_from_image(path)

    SimpleLogger.log("⚠️ FILE", f"Unsupported extension: {ext}")
    return None


analysis_agent = Agent(
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
)

main_agent = Agent(
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
)


async def run_pipeline_streamed(user_text: str) -> AsyncGenerator[str, None]:
    config = RunConfig(tracing_disabled=True, model=model, model_provider=client)

    def create_status_message(step: str, status: str, message: str) -> str:
        """Helper to format the data for SSE."""
        payload = json.dumps({"step": step, "status": status, "message": message})
        return f"data: {payload}\n\n"

    try:
        yield create_status_message(
            "Input Received",
            "completed",
            f"Received {len(user_text)} characters for analysis.",
        )
        await asyncio.sleep(1)

        context = SharedContext(document_text=user_text, analysis_stage="starting")

        yield create_status_message(
            "Decision Phase",
            "processing",
            "Processing with Main Agent to determine document type...",
        )
        decision_result = await Runner.run(
            main_agent, user_text, run_config=config, context=context
        )
        decision: AgentDecision = decision_result.final_output
        yield create_status_message(
            "Decision Phase", "completed", f"Agent decided action: {decision.action}"
        )
        await asyncio.sleep(1)

        final_response_message = ""
        if decision.action == "analyze_document":
            yield create_status_message(
                "Analysis Phase",
                "processing",
                "Document detected. Proceeding with full analysis...",
            )
            analysis_output = await Runner.run(
                analysis_agent,
                decision.document_content or user_text,
                run_config=config,
            )
            yield create_status_message(
                "Analysis Phase",
                "completed",
                "Core analysis finished. Generating friendly response...",
            )
            await asyncio.sleep(1)

            friendly_output = await Runner.run(
                friendly_agent,
                analysis_output.final_output.model_dump_json(),
                run_config=config,
            )
            final_response_message = friendly_output.final_output.message

        elif decision.action == "casual_chat":
            yield create_status_message(
                "Casual Chat", "processing", "Casual chat mode activated..."
            )
            casual_output = await Runner.run(
                casual_chat_agent, user_text, run_config=config
            )
            final_response_message = casual_output.final_output.message
            yield create_status_message(
                "Casual Chat", "completed", "Generated a casual response."
            )

        else:
            final_response_message = "I couldn't determine if that was a document. Please provide a clear legal document or ask a general question."
            yield create_status_message(
                "Determination Failed", "failed", "Could not determine document type."
            )

        final_payload = json.dumps({"final_message": final_response_message})
        yield f"data: {final_payload}\n\n"

    except InputGuardrailTripwireTriggered as e:
        error_message = (
            f"Input blocked by guardrail: {e.guardrail_result.output.output_info}"
        )
        yield create_status_message("Guardrail Triggered", "failed", error_message)
    except OutputGuardrailTripwireTriggered as e:
        error_message = (
            f"Output validation failed: {e.guardrail_result.output.output_info}"
        )
        yield create_status_message("Validation Failed", "failed", error_message)
    except Exception as e:
        error_message = f"An unexpected error occurred: {str(e)}"
        yield create_status_message("System Error", "failed", error_message)

    yield "data: [DONE]\n\n"


@app.get("/")
async def root():
    return {"message": "Legalyze API is running!", "status": "healthy"}


@app.post("/analyze/")
async def analyze_document(file: UploadFile = File(...)):
    try:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=os.path.splitext(file.filename)[1]
        ) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        user_text = load_text_from_path(tmp_path)

        if not user_text:
            raise HTTPException(
                status_code=400,
                detail="Could not extract text from the file. It might be empty, corrupted, or an unsupported format.",
            )

    finally:
        if "tmp_path" in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    if not user_text:
        raise HTTPException(
            status_code=400, detail="Could not extract text from the provided file."
        )

    return StreamingResponse(
        run_pipeline_streamed(user_text), media_type="text/event-stream"
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
