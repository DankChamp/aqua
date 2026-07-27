from pathlib import Path


def parse_text(file_path: str) -> str:
    path = Path(file_path)
    return path.read_text(encoding="utf-8")


def parse_pdf(file_path: str) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        text = []
        for page in reader.pages:
            text.append(page.extract_text() or "")
        return "\n\n".join(text)
    except ImportError:
        raise ImportError("pypdf is required to parse PDF files. Install it with: pip install pypdf")


def ingest_file(file_path: str) -> tuple[str, str, str]:
    path = Path(file_path)
    suffix = path.suffix.lower()
    title = path.stem

    if suffix == ".pdf":
        content = parse_pdf(file_path)
        source = "pdf"
    elif suffix == ".txt":
        content = parse_text(file_path)
        source = "text"
    elif suffix in (".md", ".markdown"):
        content = parse_text(file_path)
        source = "markdown"
    else:
        raise ValueError(f"Unsupported file type: {suffix}")

    return title, content, source
