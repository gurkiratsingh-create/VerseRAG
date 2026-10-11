
import re
from io import BytesIO

from pypdf import PdfReader


MAX_FILE_SIZE = 10 * 1024 * 1024


def extract_text(filename: str, content: bytes) -> str:
    if len(content) > MAX_FILE_SIZE:
        raise ValueError("File size must not exceed 10 MB")

    if not content:
        raise ValueError("The uploaded file is empty")

    extension = filename.lower().rsplit(".", 1)[-1]

    if extension == "txt":
        text = content.decode("utf-8-sig")
    elif extension == "pdf":
        reader = PdfReader(BytesIO(content))

        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported")

        text = "\n".join(
            page.extract_text() or "" for page in reader.pages
        )
    else:
        raise ValueError("Only PDF and TXT files are supported")

    text = text.replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    if not text:
        raise ValueError(
            "No extractable text found. Scanned PDFs need OCR."
        )

    return text


def chunk_text(
    text: str,
    chunk_size: int = 180,
    overlap: int = 30,
) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be between 0 and chunk_size")

    words = text.split()
    chunks = []
    step = chunk_size - overlap

    for start in range(0, len(words), step):
        chunk = " ".join(words[start:start + chunk_size])

        if chunk:
            chunks.append(chunk)

        if start + chunk_size >= len(words):
            break

    return chunks
