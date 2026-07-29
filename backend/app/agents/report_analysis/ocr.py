"""
OCR abstraction layer for MedicalReportAnalysisAgent.

Supports:
  - Searchable PDFs (text extraction via pypdf)
  - Scanned PDFs / images (pytesseract, optional)
  - PNG, JPEG, TIFF (pytesseract, optional)

The OCRProcessor is an abstract base class — swap the engine by
subclassing and overriding _extract_from_image().
"""

import io
import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger("report_analysis.ocr")

# Optional heavy dependencies — gracefully absent in test environments
try:
    import pypdf
    _PYPDF_AVAILABLE = True
except ImportError:
    pypdf = None
    _PYPDF_AVAILABLE = False

try:
    from PIL import Image
    import pytesseract
    _TESSERACT_AVAILABLE = True
except ImportError:
    Image = None
    pytesseract = None
    _TESSERACT_AVAILABLE = False

try:
    import pdf2image
    _PDF2IMAGE_AVAILABLE = True
except ImportError:
    pdf2image = None
    _PDF2IMAGE_AVAILABLE = False


class OCRResult:
    """Result of an OCR extraction."""
    def __init__(self, text: str, confidence: float, pages: int = 1, engine: str = "none"):
        self.text = text.strip()
        self.confidence = confidence          # 0.0–1.0
        self.pages = pages
        self.engine = engine

    def is_empty(self) -> bool:
        return len(self.text) < 10


class BaseOCRProcessor(ABC):
    """Abstract OCR processor — subclass to plug in a different engine."""

    @abstractmethod
    def extract(self, file_bytes: bytes, mime_type: str) -> OCRResult:
        """Extract text from file bytes. Must be synchronous."""

    def clean_text(self, text: str) -> str:
        """Basic text cleaning — remove excessive whitespace."""
        import re
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text.strip()


class DefaultOCRProcessor(BaseOCRProcessor):
    """
    Default OCR processor.
    - PDFs: text layer via pypdf; falls back to pytesseract if text layer is empty.
    - Images (PNG/JPEG/TIFF): pytesseract.
    - Graceful degradation: returns empty OCRResult if no engine is available.
    """

    def extract(self, file_bytes: bytes, mime_type: str) -> OCRResult:
        mime = (mime_type or "").lower()

        if "pdf" in mime:
            return self._extract_pdf(file_bytes)
        elif any(fmt in mime for fmt in ("png", "jpeg", "jpg", "tiff", "tif", "image")):
            return self._extract_image(file_bytes)
        else:
            logger.warning("Unsupported MIME type: %s — attempting PDF extraction", mime_type)
            return self._extract_pdf(file_bytes)

    def _extract_pdf(self, file_bytes: bytes) -> OCRResult:
        if not _PYPDF_AVAILABLE:
            logger.warning("pypdf not installed — cannot extract PDF text")
            return OCRResult("", 0.0, engine="none")

        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            pages_text = []
            for page in reader.pages:
                text = page.extract_text() or ""
                pages_text.append(text)

            full_text = "\n\n".join(pages_text)
            full_text = self.clean_text(full_text)

            if len(full_text) > 50:
                logger.info("PDF text layer extracted: %d chars, %d pages", len(full_text), len(reader.pages))
                return OCRResult(full_text, confidence=0.95, pages=len(reader.pages), engine="pypdf")

            # Text layer empty — try image-based OCR on each page
            logger.info("PDF text layer empty — attempting image OCR")
            return self._extract_pdf_as_images(file_bytes, len(reader.pages))

        except Exception as exc:
            logger.error("PDF extraction failed: %s", exc)
            return OCRResult("", 0.0, engine="error")

    def _extract_pdf_as_images(self, file_bytes: bytes, page_count: int) -> OCRResult:
        """Render PDF pages as images and OCR them (requires pdf2image + tesseract)."""
        if pdf2image is None:
            logger.warning("pdf2image not installed — cannot OCR scanned PDF")
            return OCRResult("", 0.0, engine="none")
        try:
            images = pdf2image.convert_from_bytes(file_bytes, dpi=200)
            texts = [self._ocr_pil_image(img) for img in images]
            full_text = self.clean_text("\n\n".join(texts))
            return OCRResult(full_text, confidence=0.75, pages=page_count, engine="tesseract_pdf")
        except Exception as exc:
            logger.error("PDF image OCR failed: %s", exc)
            return OCRResult("", 0.0, engine="error")

    def _extract_image(self, file_bytes: bytes) -> OCRResult:
        if not _TESSERACT_AVAILABLE:
            logger.warning("pytesseract/Pillow not installed — cannot OCR image")
            return OCRResult("", 0.0, engine="none")
        try:
            image = Image.open(io.BytesIO(file_bytes))
            text = self._ocr_pil_image(image)
            text = self.clean_text(text)
            return OCRResult(text, confidence=0.80, pages=1, engine="tesseract")
        except Exception as exc:
            logger.error("Image OCR failed: %s", exc)
            return OCRResult("", 0.0, engine="error")

    def _ocr_pil_image(self, image) -> str:
        if not _TESSERACT_AVAILABLE:
            return ""
        try:
            return pytesseract.image_to_string(image, config="--psm 6")
        except Exception as exc:
            logger.error("Tesseract OCR failed: %s", exc)
            return ""


class GeminiOCRProcessor(BaseOCRProcessor):
    """
    Wraps a fallback processor and uses Gemini Multimodal Vision to extract text
    if the local processor fails (e.g., image-only PDF without Tesseract installed).
    """
    def __init__(self, fallback_processor: BaseOCRProcessor):
        self.fallback = fallback_processor
        import os
        from app.core.settings import settings
        self.api_key = (
            os.environ.get("GEMINI_API_KEY") 
            or os.environ.get("GOOGLE_API_KEY") 
            or getattr(settings, "gemini_api_key", "")
        )

    def extract(self, file_bytes: bytes, mime_type: str) -> OCRResult:
        # Try local extraction first
        result = self.fallback.extract(file_bytes, mime_type)
        
        # If extraction worked (e.g. standard PDF), return it
        if not result.is_empty() and result.engine not in ("none", "error"):
            return result
            
        if not self.api_key or self.api_key.startswith("nvapi-"):
            logger.warning("No valid Gemini API key found. Cannot use Multimodal OCR fallback.")
            return result
            
        try:
            logger.info("Local OCR returned empty text. Falling back to Gemini Multimodal OCR.")
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            
            # Use a list of models to gracefully fallback if free-tier daily quotas are exceeded
            models_to_try = ['gemini-2.5-flash', 'gemini-flash-lite-latest', 'gemini-2.5-pro']
            response = None
            
            gemini_mime = (mime_type or "").lower()
            if gemini_mime not in ['application/pdf', 'image/png', 'image/jpeg', 'image/jpg', 'image/webp', 'image/heic', 'image/heif']:
                gemini_mime = 'application/pdf' if 'pdf' in gemini_mime else 'image/jpeg'
                
            last_err = None
            for model_name in models_to_try:
                try:
                    logger.info(f"Attempting Gemini OCR with model: {model_name}")
                    model = genai.GenerativeModel(model_name)
                    response = model.generate_content([
                        {'mime_type': gemini_mime, 'data': file_bytes},
                        "Extract all clinical text, lab values, and data from this medical document exactly as written. "
                        "Do not summarize or explain, just transcribe the raw text."
                    ])
                    break # Success
                except Exception as e:
                    logger.warning(f"Model {model_name} failed (possibly quota exceeded): {e}")
                    last_err = e
            
            if not response:
                raise Exception(f"All Gemini fallback models exhausted. Last error: {last_err}")
                
            extracted_text = self.clean_text(response.text)
            if len(extracted_text) > 10:
                logger.info("Gemini Multimodal OCR extracted %d chars.", len(extracted_text))
                return OCRResult(extracted_text, confidence=0.99, pages=result.pages or 1, engine="gemini_multimodal")
            
        except Exception as exc:
            logger.error("Gemini Multimodal OCR failed: %s", exc)
            
        return result

# Default singleton — wrapped with Gemini fallback
default_ocr_processor = GeminiOCRProcessor(DefaultOCRProcessor())
