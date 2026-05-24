"""
TrustHire AI — Resume parser service.
Step 1: extract raw text (PDF/DOCX/image).
Step 2: LLM structured extraction.
Step 3: normalise and return JSON.
"""

import io
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# TEXT EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

async def extract_text(file_bytes: bytes, mime_type: str) -> str:
    """
    Extract plain text from a resume file.
    Tries fast path first; falls back to OCR for scanned images.
    """
    if mime_type == "application/pdf":
        text = _extract_pdf(file_bytes)
        if text and len(text.strip()) > 100:
            return text
        # Scanned PDF — fall through to OCR
        logger.info("PDF text too short, falling back to OCR")
        return await _ocr_pdf(file_bytes)

    if mime_type in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ):
        return _extract_docx(file_bytes)

    if mime_type in ("image/png", "image/jpeg", "image/webp"):
        return await _ocr_image(file_bytes)

    raise ValueError(f"Unsupported MIME type: {mime_type}")


def _extract_pdf(file_bytes: bytes) -> str:
    """Fast digital PDF extraction with PyMuPDF."""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages = [page.get_text() for page in doc]
        doc.close()
        return "\n\n".join(pages)
    except ImportError:
        logger.warning("PyMuPDF not installed; using pdfminer fallback")
        return ""
    except Exception as exc:
        logger.error("PDF extraction failed: %s", exc)
        return ""


def _extract_docx(file_bytes: bytes) -> str:
    """Extract text from .docx using python-docx."""
    try:
        import docx

        doc = docx.Document(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError:
        logger.warning("python-docx not installed")
        return ""
    except Exception as exc:
        logger.error("DOCX extraction failed: %s", exc)
        return ""


async def _ocr_pdf(file_bytes: bytes) -> str:
    """Convert PDF pages to images then OCR each page."""
    try:
        import fitz

        doc = fitz.open(stream=file_bytes, filetype="pdf")
        texts = []
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            text = await _ocr_image(img_bytes)
            texts.append(text)
        doc.close()
        return "\n\n".join(texts)
    except Exception as exc:
        logger.error("OCR PDF failed: %s", exc)
        return ""


async def _ocr_image(image_bytes: bytes) -> str:
    """OCR a single image with PaddleOCR, falling back to pytesseract."""
    # Try PaddleOCR first (better accuracy)
    try:
        from paddleocr import PaddleOCR
        import numpy as np
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_array = np.array(img)

        ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        result = ocr.ocr(img_array, cls=True)

        lines = []
        if result and result[0]:
            for line in result[0]:
                if line and len(line) >= 2:
                    text_info = line[1]
                    if isinstance(text_info, (list, tuple)) and len(text_info) >= 1:
                        lines.append(str(text_info[0]))
        return "\n".join(lines)

    except ImportError:
        pass  # Fall through to tesseract
    except Exception as exc:
        logger.warning("PaddleOCR failed: %s, trying tesseract", exc)

    # Fallback: pytesseract
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))
        return pytesseract.image_to_string(img)
    except ImportError:
        logger.error("Neither PaddleOCR nor pytesseract is installed")
        return ""
    except Exception as exc:
        logger.error("Tesseract OCR failed: %s", exc)
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# LLM EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

EXTRACTION_PROMPT = """\
You are an expert resume parser. Extract structured information from the resume text below.

RULES:
- Only extract information explicitly stated in the text. NEVER infer or hallucinate.
- Dates must be in "YYYY-MM" format. If only year is given use "YYYY-01".
- If the end date is current/present, use "present".
- For company_domain, make a best guess based on the company name (e.g. "google.com"). If unsure, use null.
- Return ONLY valid JSON — no markdown fences, no preamble, no explanation.

Resume text:
{resume_text}

Return JSON exactly matching this schema:
{{
  "full_name": "string or null",
  "email": "string or null",
  "phone": "string or null",
  "linkedin_url": "string or null",
  "employment_history": [
    {{
      "company_name": "string",
      "job_title": "string or null",
      "start_date": "YYYY-MM or null",
      "end_date": "YYYY-MM or present or null",
      "location": "string or null",
      "responsibilities": ["string"],
      "company_domain": "string or null"
    }}
  ],
  "education_history": [
    {{
      "institution_name": "string",
      "degree": "string or null",
      "field_of_study": "string or null",
      "graduation_year": integer_or_null
    }}
  ],
  "skills": ["string"],
  "certifications": ["string"]
}}
"""


async def parse_resume(raw_text: str) -> dict:
    """
    Send resume text to LLM and return structured dict.
    Falls back to empty structure if parsing fails.
    """
    from services.ai.model_router import ainvoke_llm

    if not raw_text or len(raw_text.strip()) < 50:
        logger.warning("Resume text too short to parse")
        return _empty_parsed()

    prompt = EXTRACTION_PROMPT.format(resume_text=raw_text[:8000])  # Token safety

    try:
        raw = await ainvoke_llm(prompt, task="extraction")
        # Strip accidental markdown fences
        clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        data = json.loads(clean)
        return _validate_parsed(data)
    except json.JSONDecodeError as exc:
        logger.error("LLM returned invalid JSON: %s\nRaw: %s", exc, raw[:500])
        return _empty_parsed()
    except Exception as exc:
        logger.error("Resume parsing error: %s", exc)
        return _empty_parsed()


def _validate_parsed(data: dict) -> dict:
    """Ensure required keys exist and lists are lists."""
    data.setdefault("full_name", None)
    data.setdefault("email", None)
    data.setdefault("phone", None)
    data.setdefault("linkedin_url", None)
    data.setdefault("employment_history", [])
    data.setdefault("education_history", [])
    data.setdefault("skills", [])
    data.setdefault("certifications", [])

    if not isinstance(data["employment_history"], list):
        data["employment_history"] = []
    if not isinstance(data["education_history"], list):
        data["education_history"] = []

    return data


def _empty_parsed() -> dict:
    return {
        "full_name": None,
        "email": None,
        "phone": None,
        "linkedin_url": None,
        "employment_history": [],
        "education_history": [],
        "skills": [],
        "certifications": [],
    }
