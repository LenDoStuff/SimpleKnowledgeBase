from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExtractedClaimFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    value: str
    summary: str = ""
    citation_text: str = ""
    page_start: int | None = None
    page_end: int | None = None


class ExtractedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: str
    summary: str
    event_date: str | None = None
    citation_text: str = ""
    page_start: int | None = None
    page_end: int | None = None


class ExtractedParty(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    party_type: str
    role: str
    summary: str = ""
    citation_text: str = ""
    page_start: int | None = None
    page_end: int | None = None


class ExtractedFinancialItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    financial_type: Literal["Reserve", "Payment", "Recovery", "Invoice"]
    summary: str
    amount: float | None = None
    currency: str | None = None
    booking_date: str | None = None
    citation_text: str = ""
    page_start: int | None = None
    page_end: int | None = None


class DocumentBatchExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    document_summary: str = ""
    claim_facts: list[ExtractedClaimFact] = Field(default_factory=list)
    events: list[ExtractedEvent] = Field(default_factory=list)
    parties: list[ExtractedParty] = Field(default_factory=list)
    financial_items: list[ExtractedFinancialItem] = Field(default_factory=list)
    citation_snippets: list[str] = Field(default_factory=list)


class DocumentExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    source_id: str
    document_summary: str
    citation_text: str
    batches: list[DocumentBatchExtraction] = Field(default_factory=list)
    claim_facts: list[ExtractedClaimFact] = Field(default_factory=list)
    events: list[ExtractedEvent] = Field(default_factory=list)
    parties: list[ExtractedParty] = Field(default_factory=list)
    financial_items: list[ExtractedFinancialItem] = Field(default_factory=list)


def consolidate_document_batches(
    *,
    document_id: str,
    source_id: str,
    batches: list[DocumentBatchExtraction],
) -> DocumentExtraction:
    if not batches:
        raise RuntimeError(f"Document extraction returned no batches for document {document_id}.")

    claim_facts = [fact for batch in batches for fact in batch.claim_facts]
    events = [event for batch in batches for event in batch.events]
    parties = [party for batch in batches for party in batch.parties]
    financial_items = [item for batch in batches for item in batch.financial_items]
    summaries = [batch.document_summary.strip() for batch in batches if batch.document_summary.strip()]
    if not any([summaries, claim_facts, events, parties, financial_items]):
        raise RuntimeError(f"Document extraction returned no structured content for document {document_id}.")
    citation_text = _first_citation_text(batches, summaries)

    return DocumentExtraction(
        document_id=document_id,
        source_id=source_id,
        document_summary=" ".join(summaries),
        citation_text=citation_text,
        batches=batches,
        claim_facts=claim_facts,
        events=events,
        parties=parties,
        financial_items=financial_items,
    )


def non_pdf_document_extraction(
    *,
    document_id: str,
    source_id: str,
    evidence: str,
) -> DocumentExtraction:
    citation = _clip_citation(evidence.strip() or f"Evidence from document {document_id}")
    return DocumentExtraction(
        document_id=document_id,
        source_id=source_id,
        document_summary=evidence,
        citation_text=citation,
    )


def _first_citation_text(batches: list[DocumentBatchExtraction], summaries: list[str]) -> str:
    for batch in batches:
        for snippet in batch.citation_snippets:
            if snippet.strip():
                return _clip_citation(snippet)
        for item in [*batch.claim_facts, *batch.events, *batch.parties, *batch.financial_items]:
            if item.citation_text.strip():
                return _clip_citation(item.citation_text)
    if summaries:
        return _clip_citation(summaries[0])
    return "Document-level extraction completed without a citation snippet."


def _clip_citation(text: str) -> str:
    text = text.strip()
    if len(text) > 220:
        return f"{text[:217]}..."
    return text
