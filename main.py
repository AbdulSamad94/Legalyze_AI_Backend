import uuid
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware

from file_handlers import process_uploaded_file, get_supported_extensions
from processing_pipeline import run_demo_pipeline, run_enhanced_pipeline_streamed


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
analysis_sessions = {}


@app.get("/")
async def root():
    """Root endpoint with API information"""
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
        "supported_formats": get_supported_extensions(),
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "LegalyzeAI Backend",
        "active_sessions": len(analysis_sessions),
    }


@app.post("/demo/")
async def demo_analysis(file: UploadFile = File(...)):
    """Simplified demo endpoint for quick document analysis"""
    session_id = str(uuid.uuid4())

    user_text, filename = await process_uploaded_file(file)

    return StreamingResponse(
        run_demo_pipeline(user_text, filename, session_id),
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

    # Process the uploaded file
    user_text, filename = await process_uploaded_file(file)

    # Stream the enhanced analysis
    return StreamingResponse(
        run_enhanced_pipeline_streamed(user_text, filename, session_id),
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


@app.get("/sessions/")
async def list_active_sessions():
    """List all active analysis sessions"""
    return {
        "active_sessions": len(analysis_sessions),
        "sessions": {
            session_id: {
                "status": session_data.get("status"),
                "filename": session_data.get("filename"),
                "started_at": session_data.get("started_at"),
            }
            for session_id, session_data in analysis_sessions.items()
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
