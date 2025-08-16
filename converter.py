import pdfplumber
import docx

try:
    from PIL import Image
    import pytesseract
except Exception:
    Image = None
    pytesseract = None

# Optional: convert PDF pages to images for OCR fallback
try:
    from pdf2image import convert_from_path
except Exception:
    convert_from_path = None


def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from text-based PDFs using pdfplumber. Returns empty string if none found."""
    text_chunks = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            try:
                extracted = page.extract_text() or ""
            except Exception:
                extracted = ""
            if extracted:
                text_chunks.append(extracted)
    return "\n".join(text_chunks).strip()


def extract_text_from_docx(file_path: str) -> str:
    doc = docx.Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs]).strip()


def extract_text_from_txt(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read().strip()


def try_ocr_from_image(image_path: str) -> str:
    """OCR for image files if pytesseract + PIL available. Returns empty string if not available."""
    if not (Image and pytesseract):
        return ""
    try:
        img = Image.open(image_path)
        return pytesseract.image_to_string(img) or ""
    except Exception:
        return ""


def try_ocr_from_scanned_pdf(pdf_path: str) -> str:
    """OCR fallback for scanned PDFs: convert each page to image then run Tesseract.
    Requires `pdf2image`, `pytesseract`, and `Pillow`. Returns empty string if unavailable.
    """
    if not (convert_from_path and Image and pytesseract):
        return ""
    try:
        pages = convert_from_path(pdf_path)
        ocr_text = []
        for img in pages:
            ocr_text.append(pytesseract.image_to_string(img) or "")
        return "\n".join(ocr_text).strip()
    except Exception:
        return ""
