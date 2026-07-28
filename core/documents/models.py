import datetime
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Document:
    id: Optional[int] = None
    title: str = ""
    content: str = ""
    authors: str = ""
    source: str = "manual"
    source_url: str = ""
    file_path: str = ""
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Note:
    id: Optional[int] = None
    title: str = ""
    content: str = ""
    document_id: Optional[int] = None
    class_std: str = ""
    subject: str = ""
    chapter: str = ""
    created_at: str = ""
    updated_at: str = ""
