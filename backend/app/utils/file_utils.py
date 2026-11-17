import io
import logging
import pdfplumber
import docx

logger = logging.getLogger(__name__)

# What the first bytes of each accepted upload type must look like
_MAGIC = {
    "pdf": (b"%PDF",),
    "docx": (b"PK\x03\x04",),
    # Real Word 97 files are OLE; .doc files that are really DOCX are common too
    "doc": (b"\xD0\xCF\x11\xE0", b"PK\x03\x04"),
}


def content_matches_type(ext: str, content: bytes) -> bool:
    """True if the bytes look like the file type its extension claims."""
    if ext == "txt":
        try:
            content.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False
    if ext == "pdf":
        # The PDF spec lets the header start anywhere in the first 1024 bytes
        return b"%PDF" in content[:1024]
    return content.startswith(_MAGIC.get(ext, ()))


def read_pdf_bytes(content: bytes) -> str:
    """Extract text from PDF bytes"""
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception:
        logger.warning("Could not read PDF", exc_info=True)
        return ""


def read_docx_bytes(content: bytes) -> str:
    """Extract text from DOCX bytes"""
    try:
        doc = docx.Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs).strip()
    except Exception:
        logger.warning("Could not read DOCX", exc_info=True)
        return ""


def read_file(filename: str, content: bytes) -> str:
    """Read file content and extract text based on extension"""
    ext = filename.lower().split(".")[-1]

    if ext == "pdf":
        return read_pdf_bytes(content)
    elif ext in ("docx", "doc"):
        return read_docx_bytes(content)
    elif ext == "txt":
        return content.decode("utf-8", errors="ignore")
    else:
        # Fallback: try PDF first, then text
        text = read_pdf_bytes(content)
        return text if text else content.decode("utf-8", errors="ignore")
