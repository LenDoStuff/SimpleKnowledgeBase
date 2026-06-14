from __future__ import annotations

from pydantic import BaseModel

from backend.app.models import StoredDocument


class NormalizedDocument(BaseModel):
    document: StoredDocument
    extracted_text: str
    page_count: int | None


def normalize_document(document: StoredDocument) -> NormalizedDocument:
    metadata = (
        f"API input prepared for {document.filename}. "
        f"Document type: {document.document_type}. "
        f"Title: {document.title}."
    )
    return NormalizedDocument(
        document=document,
        extracted_text=metadata,
        page_count=document.pages or 1,
    )
