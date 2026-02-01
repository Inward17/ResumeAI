import io
import pdfplumber
import docx


def read_pdf_bytes(content: bytes) -> str:
    """Extract text from PDF bytes"""
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except:
        return ""


def read_docx_bytes(content: bytes) -> str:
    """Extract text from DOCX bytes"""
    try:
        doc = docx.Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs).strip()
    except:
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