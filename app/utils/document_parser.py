import asyncio
import io
import os
import re
import tempfile
import uuid
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image

try:
    import pypdf
except ImportError:
    pypdf = None

try:
    import docx
except ImportError:
    docx = None

# Windows native OCR imports
try:
    import winsdk.windows.media.ocr as win_ocr
    import winsdk.windows.graphics.imaging as win_imaging
    import winsdk.windows.storage.streams as win_streams
    WINSDK_OCR_AVAILABLE = True
except Exception:
    WINSDK_OCR_AVAILABLE = False


# Maximum upload size configurable via environment variable (default: 10 MB)
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

OFFER_LETTER_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".jpg", ".jpeg", ".png"}
SCREENSHOT_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/pjpeg",
}


class DocumentValidationError(Exception):
    pass


def validate_file_upload(filename: str, content: bytes, allowed_extensions: set) -> None:
    """
    Validates file size, extension, and basic magic byte / MIME safety.
    """
    if not content:
        raise DocumentValidationError("The uploaded file is empty.")

    if len(content) > MAX_UPLOAD_BYTES:
        raise DocumentValidationError(
            f"File exceeds maximum allowed size of {MAX_UPLOAD_SIZE_MB} MB."
        )

    # Safe extension check
    _, ext = os.path.splitext(filename.lower())
    if ext not in allowed_extensions:
        allowed_list = ", ".join(sorted(allowed_extensions))
        raise DocumentValidationError(
            f"Unsupported file format '{ext}'. Allowed formats: {allowed_list}."
        )

    # Magic byte verification
    if ext == ".pdf" and not content.startswith(b"%PDF-"):
        raise DocumentValidationError("Corrupted or invalid PDF file header.")
    elif ext in {".jpg", ".jpeg"} and not (content.startswith(b"\xff\xd8\xff")):
        raise DocumentValidationError("Corrupted or invalid JPEG image header.")
    elif ext == ".png" and not (content.startswith(b"\x89PNG\r\n\x1a\n")):
        raise DocumentValidationError("Corrupted or invalid PNG image header.")
    elif ext == ".webp" and not (content[:4] == b"RIFF" and content[8:12] == b"WEBP"):
        raise DocumentValidationError("Corrupted or invalid WEBP image header.")
    elif ext == ".docx" and not (content.startswith(b"PK\x03\x04") or content.startswith(b"PK\x05\x06")):
        raise DocumentValidationError("Corrupted or invalid DOCX document archive.")


async def _run_windows_native_ocr_async(image_bytes: bytes) -> Tuple[str, float]:
    """
    Executes Windows 10/11 native OCR via winsdk on image bytes.
    Returns (extracted_text, confidence_score).
    """
    if not WINSDK_OCR_AVAILABLE:
        return "", 0.0

    mem_stream = win_streams.InMemoryRandomAccessStream()
    writer = win_streams.DataWriter(mem_stream)
    writer.write_bytes(bytearray(image_bytes))
    await writer.store_async()
    await writer.flush_async()
    writer.detach_stream()
    mem_stream.seek(0)

    decoder = await win_imaging.BitmapDecoder.create_async(mem_stream)
    software_bitmap = await decoder.get_software_bitmap_async()

    engine = win_ocr.OcrEngine.try_create_from_user_profile_languages()
    if not engine:
        return "", 0.0

    ocr_result = await engine.recognize_async(software_bitmap)
    if not ocr_result or not ocr_result.lines:
        return "", 0.0

    lines: List[str] = []
    total_words = 0
    valid_words = 0

    for line in ocr_result.lines:
        lines.append(line.text)
        for w in line.words:
            total_words += 1
            # Check if word contains recognizable alphanumeric characters
            if re.search(r"[a-zA-Z0-9]", w.text):
                valid_words += 1

    extracted_text = "\n".join(lines).strip()
    if not extracted_text or total_words == 0:
        return extracted_text, 0.0

    # Calculate confidence: combination of valid alphanumeric word ratio and text length
    validity_ratio = valid_words / total_words if total_words > 0 else 0.0
    # Baseline for native Windows OCR engine when text is cleanly read
    confidence = min(1.0, max(0.2, validity_ratio * 0.95))
    if len(extracted_text) < 15:
        confidence = min(confidence, 0.50)

    return extracted_text, round(confidence, 2)


def run_ocr_on_image(image_bytes: bytes) -> Tuple[str, float]:
    """
    Synchronous wrapper to run OCR on image bytes using winsdk native OCR.
    Pre-processes image with Pillow to normalize dimensions and format if needed.
    """
    try:
        with Image.open(io.BytesIO(image_bytes)) as pil_img:
            if pil_img.mode in ("RGBA", "P", "LA"):
                bg = Image.new("RGB", pil_img.size, (255, 255, 255))
                if pil_img.mode == "P":
                    pil_img = pil_img.convert("RGBA")
                bg.paste(pil_img, mask=pil_img.split()[-1] if pil_img.mode == "RGBA" else None)
                proc_img = bg
            else:
                proc_img = pil_img.convert("RGB")

            max_dimension = 2400
            if max(proc_img.size) > max_dimension:
                proc_img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            elif max(proc_img.size) < 1200:
                scale = min(3.0, 1200.0 / max(proc_img.size))
                if scale > 1.2:
                    new_size = (int(proc_img.width * scale), int(proc_img.height * scale))
                    proc_img = proc_img.resize(new_size, Image.Resampling.LANCZOS)

            buf = io.BytesIO()
            proc_img.save(buf, format="PNG")
            normalized_bytes = buf.getvalue()
    except Exception as e:
        raise DocumentValidationError(f"Could not process image: {str(e)}")

    if WINSDK_OCR_AVAILABLE:
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(lambda: asyncio.run(_run_windows_native_ocr_async(normalized_bytes)))
                    return future.result()
            else:
                return asyncio.run(_run_windows_native_ocr_async(normalized_bytes))
        except Exception:
            pass

    return "", 0.0


def extract_text_from_pdf(content_bytes: bytes) -> Tuple[str, float]:
    """
    Extracts text from PDF bytes.
    First attempts digital text extraction with pypdf.
    If digital text is absent or sparse (< 35 chars), performs OCR on embedded page images.
    """
    if not pypdf:
        raise DocumentValidationError("pypdf library is not installed.")

    extracted_pages: List[str] = []
    has_scanned_pages = False

    try:
        pdf_reader = pypdf.PdfReader(io.BytesIO(content_bytes))
        for page_idx, page in enumerate(pdf_reader.pages):
            page_text = (page.extract_text() or "").strip()
            image_texts: List[str] = []
            if len(page_text) < 50:
                has_scanned_pages = True
                if hasattr(page, "images"):
                    for img_obj in page.images:
                        try:
                            ocr_text, _ = run_ocr_on_image(img_obj.data)
                            if ocr_text:
                                image_texts.append(ocr_text)
                        except Exception:
                            continue

            combined_page_parts = []
            if page_text:
                combined_page_parts.append(page_text)
            if image_texts:
                combined_page_parts.extend(image_texts)

            if combined_page_parts:
                extracted_pages.append("\n".join(combined_page_parts))

        full_text = "\n\n".join(extracted_pages).strip()
        confidence = 0.92 if (full_text and not has_scanned_pages) else (0.75 if full_text else 0.0)
        return full_text, confidence
    except Exception as e:
        raise DocumentValidationError(f"Failed to read PDF document: {str(e)}")


def extract_text_from_docx(content_bytes: bytes) -> Tuple[str, float]:
    """
    Extracts text from DOCX bytes including paragraphs and table cells.
    """
    if not docx:
        raise DocumentValidationError("python-docx library is not installed.")

    try:
        doc = docx.Document(io.BytesIO(content_bytes))
        text_parts: List[str] = []

        for para in doc.paragraphs:
            p_text = para.text.strip()
            if p_text:
                text_parts.append(p_text)

        for table in doc.tables:
            for row in table.rows:
                row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_cells:
                    text_parts.append(" | ".join(row_cells))

        full_text = "\n".join(text_parts).strip()
        confidence = 0.95 if full_text else 0.0
        return full_text, confidence
    except Exception as e:
        raise DocumentValidationError(f"Failed to read DOCX document: {str(e)}")


def parse_uploaded_document(
    filename: str, content_bytes: bytes, document_type: str = "offer_letter"
) -> Dict[str, Any]:
    """
    Validates and extracts raw text from an uploaded document or screenshot.
    Returns:
    {
        "filename": str,
        "raw_text": str,
        "confidence": float,
        "file_size": int,
        "file_type": str,
        "low_confidence": bool
    }
    """
    _, ext = os.path.splitext(filename.lower())

    if document_type == "offer_letter":
        validate_file_upload(filename, content_bytes, OFFER_LETTER_ALLOWED_EXTENSIONS)
    else:
        validate_file_upload(filename, content_bytes, SCREENSHOT_ALLOWED_EXTENSIONS)

    raw_text = ""
    confidence = 0.0

    if ext == ".pdf":
        raw_text, confidence = extract_text_from_pdf(content_bytes)
    elif ext == ".docx":
        raw_text, confidence = extract_text_from_docx(content_bytes)
    elif ext in {".png", ".jpg", ".jpeg", ".webp"}:
        raw_text, confidence = run_ocr_on_image(content_bytes)
    else:
        raise DocumentValidationError(f"Unsupported file type: {ext}")

    from app.services.extraction_service import normalize_document_text
    clean_text = normalize_document_text(raw_text)

    low_confidence = confidence < 0.60

    return {
        "filename": filename,
        "raw_text": clean_text or raw_text,
        "confidence": confidence,
        "file_size": len(content_bytes),
        "file_type": ext.lstrip(".").upper(),
        "low_confidence": low_confidence,
    }
