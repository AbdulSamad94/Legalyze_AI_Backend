import asyncio
import json
from typing import AsyncGenerator, Dict, Any
from datetime import datetime

from agents import (
    Runner,
    RunConfig,
    InputGuardrailTripwireTriggered,
    OutputGuardrailTripwireTriggered,
)
from pydantic_models import SharedContext, AgentDecision
from model import model, client
from agents_definitions import casual_chat_agent, friendly_agent
from agents_setup import analysis_agent, main_agent
from Logger import SimpleLogger


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
    estimated_pages = max(1, word_count // 250)

    return {
        "word_count": word_count,
        "character_count": char_count,
        "estimated_pages": estimated_pages,
        "estimated_read_time": max(1, word_count // 200),
    }


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
        # Step 1: Document recieved
        yield create_status_message(
            "Document Processing",
            "completed",
            f"Successfully received '{filename}' ({len(user_text)} characters)",
        )
        await asyncio.sleep(0.5)

        # Step 2: Text extract
        word_count = len(user_text.split())
        yield create_status_message(
            "Text Extraction",
            "completed",
            f"Extracted {word_count} words from document",
        )
        await asyncio.sleep(0.5)

        context = SharedContext(document_text=user_text, analysis_stage="starting")

        # Step 3: Document tpye detect
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

        # Step 4: Process based on agents decision
        final_message = ""

        if decision.action == "analyze_document":
            yield create_status_message(
                "AI Analysis",
                "processing",
                "Running comprehensive legal analysis...",
            )

            # Run the analysis agent
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

            # Convert analysis to dictionaar
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

                # Normalizee the risks
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
        from main import analysis_sessions

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
            friendly_message = ""
            try:
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

            if not friendly_message or len(friendly_message.strip()) < 20:
                summary = analysis_dict.get("summary", "")
                if summary:
                    friendly_message = f"Analysis complete. {summary[:200]}..."
                else:
                    friendly_message = "Your document analysis is complete. Please review the detailed report below for key findings and recommendations."

            final_result = {
                "type": "legal_analysis",
                "document_info": {
                    "filename": filename,
                    "word_count": get_document_insights(user_text).get("word_count"),
                    "estimated_pages": get_document_insights(user_text).get(
                        "estimated_pages"
                    ),
                    "estimated_read_time": get_document_insights(user_text).get(
                        "estimated_read_time"
                    ),
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
            from main import analysis_sessions

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
