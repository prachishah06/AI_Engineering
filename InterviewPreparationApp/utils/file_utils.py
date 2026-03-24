import docx
import pdfplumber
import tempfile
import os

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_SUFFIXES = {".pdf", ".docx"}


def validate_uploaded_file(uploaded_file) -> tuple[bool, str]:
    """
    Validate Streamlit uploaded file for size + type.
    Returns (ok, error_message).
    """
    if uploaded_file is None:
        return False, "No file provided."
    suffix = os.path.splitext(uploaded_file.name)[-1].lower()
    if suffix not in ALLOWED_SUFFIXES:
        return False, "Unsupported file type. Please upload PDF or DOCX only."
    size = getattr(uploaded_file, "size", None)
    if isinstance(size, int) and size > MAX_FILE_BYTES:
        return False, "File too large. Limit is 10 MB."
    return True, ""

def extract_text_from_file(uploaded_file) -> str:
    """
    Extract text from an uploaded PDF or DOCX file.
    """
    ok, msg = validate_uploaded_file(uploaded_file)
    if not ok:
        raise ValueError(msg)

    suffix = os.path.splitext(uploaded_file.name)[-1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_file.write(uploaded_file.read())
        tmp_file.flush()
        tmp_path = tmp_file.name
    text = ""
    try:
        if suffix == ".pdf":
            with pdfplumber.open(tmp_path) as pdf:
                for page in pdf.pages:
                    text += page.extract_text() or ""
        elif suffix == ".docx":
            doc = docx.Document(tmp_path)
            for para in doc.paragraphs:
                text += para.text + "\n"
        else:
            raise ValueError("Unsupported file type.")
    finally:
        os.remove(tmp_path)
    return text.strip()