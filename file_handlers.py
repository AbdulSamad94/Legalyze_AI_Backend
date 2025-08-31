import os
import tempfile
from typing import Optional
from fastapi import UploadFile, HTTPException

from converter import (
    extract_text_from_pdf,
    extract_text_from_docx,
    extract_text_from_txt,
    try_ocr_from_image,
    try_ocr_from_scanned_pdf,
)
from Logger import SimpleLogger


SUPPORTED_TEXT_EXTS = {".txt"}
SUPPORTED_DOC_EXTS = {".docx"}
SUPPORTED_PDF_EXTS = {".pdf"}
SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".tiff"}

ALL_SUPPORTED_EXTS = (
    SUPPORTED_TEXT_EXTS | SUPPORTED_DOC_EXTS | SUPPORTED_PDF_EXTS | SUPPORTED_IMAGE_EXTS
)


def load_text_from_path(path: str) -> Optional[str]:
    """Return extracted text for supported file types, otherwise None."""
    if not path:
        return None
    if not os.path.exists(path):
        SimpleLogger.log("⌐ FILE", f"Not found: {path}")
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


async def process_uploaded_file(file: UploadFile) -> tuple[str, str]:
    """
    Process an uploaded file and extract text content.

    Returns:
        tuple: (extracted_text, filename)

    Raises:
        HTTPException: If file processing fails or file is invalid
    """
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    file_ext = os.path.splitext(file.filename)[1].lower()

    if file_ext not in ALL_SUPPORTED_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_ext}. Supported types: {', '.join(ALL_SUPPORTED_EXTS)}",
        )

    # Check file size (10MB limit)
    file_content = await file.read()
    if len(file_content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=413, detail="File too large. Maximum size: 10MB"
        )

    tmp_path = None
    try:
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name

        # Extract text
        user_text = load_text_from_path(tmp_path)

        if not user_text or len(user_text.strip()) < 10:
            raise HTTPException(
                status_code=400,
                detail="Could not extract meaningful text from the file. Please ensure the document contains readable text.",
            )

        return user_text, file.filename

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
    finally:
        # Clean up temporary file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception as e:
                SimpleLogger.log(
                    "CLEANUP_ERROR", f"Failed to delete temp file: {str(e)}"
                )


def validate_file_type(filename: str) -> bool:
    """Validate if the file type is supported"""
    if not filename:
        return False

    file_ext = os.path.splitext(filename)[1].lower()
    return file_ext in ALL_SUPPORTED_EXTS


def get_supported_extensions() -> list[str]:
    """Get list of all supported file extensions"""
    return list(ALL_SUPPORTED_EXTS)
