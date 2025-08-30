import asyncio
import os
import sys
import logging
import json
from typing import Optional, AsyncGenerator, Dict, Any
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
import tempfile
from datetime import datetime
import uuid

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
    AnalysisResult,
    ProcessingStatus,
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

app = FastAPI(
    title="LegalyzeAI API",
    description="AI-powered legal document analysis and risk assessment",
    version="1.0.0",
)

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

# In-memory storage for analysis sessions (in production, use Redis or database)
analysis_sessions = {}


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


def estimate_processing_time(text_length: int) -> int:
    """Estimate processing time in seconds based on text length"""
    if text_length < 1000:
        return 15
    elif text_length < 5000:
        return 30
    elif text_length < 10000:
        return 45
    else:
        return 60


def get_document_insights(text: str) -> Dict[str, Any]:
    """Extract basic document insights"""
    word_count = len(text.split())
    char_count = len(text)
    estimated_pages = max(1, word_count // 250)  # ~250 words per page

    return {
        "word_count": word_count,
        "character_count": char_count,
        "estimated_pages": estimated_pages,
        "estimated_read_time": max(1, word_count // 200),  # ~200 words per minute
    }


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


async def run_demo_pipeline(
    user_text: str, filename: str, session_id: str
) -> AsyncGenerator[str, None]:
    """Simplified demo pipeline with basic analysis - FIXED VERSION"""

    config = RunConfig(tracing_disabled=True, model=model, model_provider=client)

    def create_status_message(step: str, status: str, message: str) -> str:
        """Helper to format the data for SSE."""
        payload = json.dumps({"step": step, "status": status, "message": message})
        return f"data: {payload}\n\n"

    try:
        # Step 1: Document received
        yield create_status_message(
            "Document Processing",
            "completed",
            f"Successfully received '{filename}' ({len(user_text)} characters)",
        )
        await asyncio.sleep(0.5)

        # Step 2: Text extraction
        word_count = len(user_text.split())
        yield create_status_message(
            "Text Extraction",
            "completed",
            f"Extracted {word_count} words from document",
        )
        await asyncio.sleep(0.5)

        context = SharedContext(document_text=user_text, analysis_stage="starting")

        # Step 3: Document type detection
        yield create_status_message(
            "Document Analysis",
            "processing",
            "Analyzing document type and structure...",
        )

        decision_result = await Runner.run(
            main_agent, user_text, run_config=config, context=context
        )
        decision: AgentDecision = decision_result.final_output

        yield create_status_message(
            "Document Analysis",
            "completed",
            f"Document type identified: {decision.action.replace('_', ' ').title()}",
        )
        await asyncio.sleep(0.5)

        # Step 4: Process based on decision
        final_message = ""

        if decision.action == "analyze_document":
            yield create_status_message(
                "AI Analysis",
                "processing",
                "Running comprehensive legal analysis...",
            )

            # Run the analysis
            analysis_output = await Runner.run(
                analysis_agent,
                user_text,
                run_config=config,
            )

            yield create_status_message(
                "AI Analysis",
                "completed",
                "Legal analysis completed successfully",
            )
            await asyncio.sleep(0.5)

            # Generate friendly response
            yield create_status_message(
                "Report Generation",
                "processing",
                "Creating your personalized report...",
            )

            # Convert analysis to dict safely
            try:
                if hasattr(analysis_output.final_output, "model_dump"):
                    analysis_dict = analysis_output.final_output.model_dump()
                else:
                    analysis_dict = {
                        "summary": getattr(analysis_output.final_output, "summary", ""),
                        "risks": getattr(analysis_output.final_output, "risks", []),
                        "verdict": getattr(analysis_output.final_output, "verdict", ""),
                        "disclaimer": getattr(
                            analysis_output.final_output, "disclaimer", ""
                        ),
                        "confidence_score": getattr(
                            analysis_output.final_output, "confidence_score", 0.8
                        ),
                    }

                # Normalize risks for display
                normalized_risks = []
                risks = analysis_dict.get("risks", [])
                for r in risks:
                    try:
                        rd = r.model_dump() if hasattr(r, "model_dump") else dict(r)
                    except Exception:
                        rd = r if isinstance(r, dict) else {}

                    normalized_risks.append(
                        {
                            "description": str(rd.get("description", "")),
                            "level": str(rd.get("level", "unknown")).lower(),
                            "category": str(rd.get("category", "")),
                            "recommendation": str(rd.get("recommendation", "")),
                        }
                    )

                # Send structured data instead of markdown text
                final_structured_data = {
                    "summary": analysis_dict.get("summary", ""),
                    "risks": normalized_risks,
                    "verdict": analysis_dict.get("verdict", ""),
                    "disclaimer": analysis_dict.get("disclaimer", ""),
                    "risk_count": len(normalized_risks),
                    "confidence_score": analysis_dict.get("confidence_score", 0.8),
                }

            except Exception as e:
                SimpleLogger.log(
                    "ANALYSIS_ERROR", f"Analysis processing failed: {str(e)}"
                )
                # Fallback structured data
                final_structured_data = {
                    "summary": "Document analysis completed but some details could not be extracted.",
                    "risks": [],
                    "verdict": "Please review the document manually for potential issues.",
                    "disclaimer": "This analysis is for informational purposes only and does not constitute legal advice.",
                    "risk_count": 0,
                    "confidence_score": 0.5,
                }

            yield create_status_message(
                "Report Generation",
                "completed",
                "Your analysis report is ready!",
            )

        elif decision.action == "casual_chat":
            yield create_status_message(
                "Response Generation", "processing", "Generating response..."
            )

            casual_output = await Runner.run(
                casual_chat_agent, user_text, run_config=config
            )
            final_message = casual_output.final_output.message

            yield create_status_message(
                "Response Generation", "completed", "Response ready!"
            )

        else:
            final_message = """I couldn't identify this as a legal document. 

Please upload a clear legal document such as:
- Contracts and agreements
- NDAs and confidentiality agreements  
- Terms of service
- Privacy policies
- Legal notices

Or feel free to ask me any general legal questions!"""

            yield create_status_message(
                "Processing Complete",
                "completed",
                "Analysis finished - document type unclear",
            )

        # Send structured data for proper rendering
        if decision.action == "analyze_document":
            final_payload = json.dumps({"structured_data": final_structured_data})
        else:
            final_payload = json.dumps({"final_message": final_message})
        yield f"data: {final_payload}\n\n"

    except InputGuardrailTripwireTriggered as e:
        error_message = "This document contains sensitive information that cannot be processed for security reasons."
        yield create_status_message("Security Check", "failed", error_message)

        final_payload = json.dumps({"final_message": error_message})
        yield f"data: {final_payload}\n\n"

    except OutputGuardrailTripwireTriggered as e:
        error_message = "Analysis output validation failed. Please try again with a different document."
        yield create_status_message("Validation Check", "failed", error_message)

        final_payload = json.dumps({"final_message": error_message})
        yield f"data: {final_payload}\n\n"

    except Exception as e:
        SimpleLogger.log("DEMO_ERROR", f"Demo pipeline failed: {str(e)}")
        error_message = "Sorry, something went wrong during analysis. Please try uploading your document again."
        yield create_status_message("System Error", "failed", error_message)

        final_payload = json.dumps({"final_message": error_message})
        yield f"data: {final_payload}\n\n"

    yield "data: [DONE]\n\n"


async def run_enhanced_pipeline_streamed(
    user_text: str, filename: str, session_id: str
) -> AsyncGenerator[str, None]:
    """Enhanced pipeline with better user experience and detailed feedback"""
    config = RunConfig(tracing_disabled=True, model=model, model_provider=client)

    def create_status_message(
        step: str,
        status: str,
        message: str,
        progress: int = 0,
        details: Dict[str, Any] = None,
    ) -> str:
        """Enhanced status message with progress and details"""
        payload = {
            "step": step,
            "status": status,
            "message": message,
            "progress": progress,
            "timestamp": datetime.now().isoformat(),
            "details": details or {},
        }
        return f"data: {json.dumps(payload)}\n\n"

    try:
        # Initialize session
        document_insights = get_document_insights(user_text)
        estimated_time = estimate_processing_time(len(user_text))

        analysis_sessions[session_id] = {
            "status": "processing",
            "filename": filename,
            "started_at": datetime.now(),
            "insights": document_insights,
        }

        yield create_status_message(
            "Document Received",
            "completed",
            f"Successfully processed your document '{filename}'",
            10,
            {
                "filename": filename,
                "word_count": document_insights["word_count"],
                "estimated_pages": document_insights["estimated_pages"],
                "estimated_time": estimated_time,
            },
        )
        await asyncio.sleep(1)

        yield create_status_message(
            "Text Extraction",
            "completed",
            f"Extracted {document_insights['word_count']} words from {document_insights['estimated_pages']} pages",
            20,
            document_insights,
        )
        await asyncio.sleep(1)

        context = SharedContext(document_text=user_text, analysis_stage="starting")

        yield create_status_message(
            "Document Classification",
            "processing",
            "Analyzing document type and structure...",
            30,
        )

        decision_result = await Runner.run(
            main_agent, user_text, run_config=config, context=context
        )
        decision: AgentDecision = decision_result.final_output

        yield create_status_message(
            "Document Classification",
            "completed",
            f"Identified as: {decision.action.replace('_', ' ').title()}",
            40,
            {"decision": decision.action, "reasoning": decision.reasoning},
        )
        await asyncio.sleep(1)

        if decision.action == "analyze_document":
            yield create_status_message(
                "AI Analysis",
                "processing",
                "Our AI legal experts are analyzing your document...",
                50,
            )
            analysis_output = await Runner.run(
                analysis_agent,
                user_text,
                run_config=config,
            )

            yield create_status_message(
                "AI Analysis",
                "completed",
                "Document analysis completed successfully",
                80,
                {
                    "risks_found": (
                        len(analysis_output.final_output.risks)
                        if analysis_output.final_output.risks
                        else 0
                    ),
                    "summary_length": len(analysis_output.final_output.summary.split()),
                },
            )
            await asyncio.sleep(1)

            yield create_status_message(
                "Generating Report",
                "processing",
                "Creating your personalized legal analysis report...",
                90,
            )

            # Get the analysis data
            try:
                analysis_dict = (
                    analysis_output.final_output.model_dump()
                    if hasattr(analysis_output.final_output, "model_dump")
                    else dict(analysis_output.final_output)
                )
            except Exception:
                analysis_dict = {
                    "summary": getattr(analysis_output.final_output, "summary", ""),
                    "risks": getattr(analysis_output.final_output, "risks", []),
                    "verdict": getattr(analysis_output.final_output, "verdict", ""),
                    "disclaimer": getattr(
                        analysis_output.final_output, "disclaimer", ""
                    ),
                    "confidence_score": getattr(
                        analysis_output.final_output, "confidence_score", 0.8
                    ),
                    "processed_at": getattr(
                        analysis_output.final_output,
                        "processed_at",
                        datetime.now().isoformat(),
                    ),
                }

            # Normalize risks
            normalized_risks = []
            for r in analysis_dict.get("risks", []):
                try:
                    rd = r.model_dump() if hasattr(r, "model_dump") else dict(r)
                except Exception:
                    rd = r if isinstance(r, dict) else {}

                norm = {
                    "description": str(rd.get("description", "")),
                    "level": str(rd.get("level", "unknown")).lower(),
                    "category": str(rd.get("category", "")),
                    "recommendation": str(rd.get("recommendation", "")),
                    "clause_reference": str(rd.get("clause_reference", "")),
                }
                normalized_risks.append(norm)

            analysis_dict["risks"] = normalized_risks

            # Try to get a friendly message, but don't fail the whole process if it doesn't work
            friendly_message = ""
            try:
                # Convert to JSON string for the friendly agent
                friendly_input = json.dumps(analysis_dict)

                SimpleLogger.log(
                    "DEBUG",
                    f"Passing to friendly agent: {friendly_input[:500]}...",
                )

                friendly_output = await Runner.run(
                    friendly_agent,
                    friendly_input,
                    run_config=config,
                )

                # Extract friendly message
                friendly_final = (
                    friendly_output.final_output
                    if hasattr(friendly_output, "final_output")
                    else friendly_output
                )

                if hasattr(friendly_final, "message"):
                    friendly_message = str(getattr(friendly_final, "message", ""))
                elif isinstance(friendly_final, dict):
                    friendly_message = str(
                        friendly_final.get("message", "")
                        or friendly_final.get("text", "")
                    )
                else:
                    friendly_message = str(friendly_final)

            except Exception as e:
                SimpleLogger.log("FRIENDLY_AGENT_FAIL", f"Error: {str(e)}")
                # Don't fail - just use a fallback message

            # If no friendly message or it's too short, create a fallback
            if not friendly_message or len(friendly_message.strip()) < 20:
                summary = analysis_dict.get("summary", "")
                if summary:
                    friendly_message = f"Analysis complete. {summary[:200]}..."
                else:
                    friendly_message = "Your document analysis is complete. Please review the detailed report below for key findings and recommendations."

            # Build the successful final result
            final_result = {
                "type": "legal_analysis",
                "document_info": {
                    "filename": filename,
                    "word_count": document_insights.get("word_count"),
                    "estimated_pages": document_insights.get("estimated_pages"),
                    "estimated_read_time": document_insights.get("estimated_read_time"),
                    "processed_at": datetime.now().isoformat(),
                },
                "analysis": {
                    "summary": analysis_dict.get("summary", ""),
                    "risks": analysis_dict.get("risks", []),
                    "verdict": analysis_dict.get("verdict", ""),
                    "disclaimer": analysis_dict.get("disclaimer", ""),
                },
                "friendly_message": friendly_message,
                "session_id": session_id,
            }

            analysis_sessions[session_id]["status"] = "completed"
            analysis_sessions[session_id]["result"] = final_result

            yield create_status_message(
                "Report Ready",
                "completed",
                "Your legal analysis report is ready!",
                100,
                {"session_id": session_id},
            )

            yield f"data: {json.dumps({'final_result': final_result}, default=str)}\n\n"

        elif decision.action == "casual_chat":
            yield create_status_message(
                "Processing Query", "processing", "Understanding your question...", 70
            )

            casual_output = await Runner.run(
                casual_chat_agent, user_text, run_config=config
            )

            final_result = {
                "type": "casual_response",
                "message": casual_output.final_output.message,
                "session_id": session_id,
            }

            yield create_status_message(
                "Response Ready",
                "completed",
                "Generated response to your question",
                100,
            )

            yield f"data: {json.dumps({'final_result': final_result})}\n\n"

        else:
            final_result = {
                "type": "error",
                "message": "I couldn't determine if that was a legal document. Please provide a clear legal document or ask a general question.",
                "session_id": session_id,
            }
            yield f"data: {json.dumps({'final_result': final_result})}\n\n"

    except InputGuardrailTripwireTriggered as e:
        error_result = {
            "type": "error",
            "message": "Your document contains sensitive information that cannot be processed.",
            "details": str(e.guardrail_result.output.output_info),
            "session_id": session_id,
        }
        yield create_status_message(
            "Security Check Failed", "failed", error_result["message"]
        )
        yield f"data: {json.dumps({'final_result': error_result})}\n\n"

    except Exception as e:
        SimpleLogger.log("CRITICAL_ERROR", f"Pipeline failed: {str(e)}")
        error_result = {
            "type": "error",
            "message": "An error occurred during analysis. Please try again.",
            "session_id": session_id,
        }
        yield create_status_message("System Error", "failed", error_result["message"])
        yield f"data: {json.dumps({'final_result': error_result})}\n\n"

    yield "data: [DONE]\n\n"


@app.get("/")
async def root():

    return {
        "message": "LegalyzeAI API is running!",
        "status": "healthy",
        "version": "1.0.0",
        "features": [
            "Legal document analysis",
            "Risk assessment",
            "Clause checking",
            "Document summarization",
        ],
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "LegalyzeAI Backend",
    }


@app.post("/demo/")
async def demo_analysis(file: UploadFile = File(...)):
    """Simplified demo endpoint for quick document analysis"""
    session_id = str(uuid.uuid4())

    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    file_ext = os.path.splitext(file.filename)[1].lower()
    supported_exts = (
        SUPPORTED_TEXT_EXTS
        | SUPPORTED_DOC_EXTS
        | SUPPORTED_PDF_EXTS
        | SUPPORTED_IMAGE_EXTS
    )

    if file_ext not in supported_exts:
        raise HTTPException(
            status_code=400, detail=f"Unsupported file type: {file_ext}"
        )

    # Check file size (10MB limit)
    file_content = await file.read()
    if len(file_content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=413, detail="File too large. Maximum size: 10MB"
        )

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name

        user_text = load_text_from_path(tmp_path)

        if not user_text or len(user_text.strip()) < 10:
            raise HTTPException(
                status_code=400,
                detail="Could not extract meaningful text from the file.",
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
    finally:
        if "tmp_path" in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    # Stream the demo analysis
    return StreamingResponse(
        run_demo_pipeline(user_text, file.filename, session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Session-ID": session_id,
        },
    )


@app.post("/analyze/")
async def analyze_document(file: UploadFile = File(...)):
    """Enhanced document analysis endpoint with session tracking"""
    session_id = str(uuid.uuid4())

    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    file_ext = os.path.splitext(file.filename)[1].lower()
    supported_exts = (
        SUPPORTED_TEXT_EXTS
        | SUPPORTED_DOC_EXTS
        | SUPPORTED_PDF_EXTS
        | SUPPORTED_IMAGE_EXTS
    )

    if file_ext not in supported_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_ext}. Supported types: {', '.join(supported_exts)}",
        )

    # Check file size (10MB limit)
    file_content = await file.read()
    if len(file_content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=413, detail="File too large. Maximum size: 10MB"
        )

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name

        user_text = load_text_from_path(tmp_path)

        if not user_text or len(user_text.strip()) < 10:
            raise HTTPException(
                status_code=400,
                detail="Could not extract meaningful text from the file. Please ensure the document contains readable text.",
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
    finally:
        if "tmp_path" in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return StreamingResponse(
        run_enhanced_pipeline_streamed(user_text, file.filename, session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Session-ID": session_id,
        },
    )


@app.get("/session/{session_id}")
async def get_session_status(session_id: str):
    """Get the status of an analysis session"""
    if session_id not in analysis_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    return analysis_sessions[session_id]


@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete an analysis session"""
    if session_id in analysis_sessions:
        del analysis_sessions[session_id]
        return {"message": "Session deleted successfully"}

    raise HTTPException(status_code=404, detail="Session not found")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
