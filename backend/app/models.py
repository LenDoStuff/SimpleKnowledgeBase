from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Document(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    summary: str
    document_type: str
    title: str
    document_date: str | None = None
    content_uri: str


class DocumentListItem(Document):
    filename: str
    file_type: str
    status: str
    pages: int | None = None
    sort_group: str
    error: str | None = None


class StoredDocument(DocumentListItem):
    stored_path: str

    def to_document(self) -> Document:
        return Document(
            id=self.id,
            summary=self.summary,
            document_type=self.document_type,
            title=self.title,
            document_date=self.document_date,
            content_uri=self.content_uri,
        )

    def to_public(self) -> DocumentListItem:
        return DocumentListItem(
            id=self.id,
            summary=self.summary,
            document_type=self.document_type,
            title=self.title,
            document_date=self.document_date,
            content_uri=self.content_uri,
            filename=self.filename,
            file_type=self.file_type,
            status=self.status,
            pages=self.pages,
            sort_group=self.sort_group,
            error=self.error,
        )


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    citation_text: str
    document_link: str
    document_id: str


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    summary: str
    status: str
    line_of_business: str
    loss_date: str | None = None
    source_ids: list[str] = Field(min_length=1)


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    summary: str
    event_type: str
    event_date: str | None = None
    previous_event_id: str | None = None
    next_event_id: str | None = None
    source_ids: list[str] = Field(min_length=1)


class Party(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    summary: str
    name: str
    party_type: str
    role: str
    source_ids: list[str] = Field(min_length=1)


class FinancialItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    summary: str
    financial_type: Literal["Reserve", "Payment", "Recovery", "Invoice"]
    amount: float
    currency: str
    booking_date: str | None = None
    source_ids: list[str] = Field(min_length=1)


class ValidationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    missing_source_entities: list[str] = Field(default_factory=list)
    invalid_references: list[str] = Field(default_factory=list)
    document_count: int = 0
    source_count: int = 0


class ClaimKnowledgeGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: Claim
    events: list[Event] = Field(default_factory=list)
    parties: list[Party] = Field(default_factory=list)
    financial_items: list[FinancialItem] = Field(default_factory=list)
    documents: list[Document] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_graph_references(self) -> "ClaimKnowledgeGraph":
        errors = []
        document_ids = {document.id for document in self.documents}
        source_ids = {source.id for source in self.sources}
        event_ids = {event.id for event in self.events}

        if len(document_ids) != len(self.documents):
            errors.append("Document IDs must be unique.")
        if len(source_ids) != len(self.sources):
            errors.append("Source IDs must be unique.")

        for source in self.sources:
            if source.document_id not in document_ids:
                errors.append(f"Source {source.id} references missing document {source.document_id}.")

        source_ref_entities: list[tuple[str, list[str]]] = [
            (f"Claim:{self.claim.id}", self.claim.source_ids),
        ]
        source_ref_entities.extend((f"Event:{event.id}", event.source_ids) for event in self.events)
        source_ref_entities.extend((f"Party:{party.id}", party.source_ids) for party in self.parties)
        source_ref_entities.extend(
            (f"FinancialItem:{item.id}", item.source_ids) for item in self.financial_items
        )

        for label, refs in source_ref_entities:
            if not refs:
                errors.append(f"{label} must reference at least one source.")
            for source_id in refs:
                if source_id not in source_ids:
                    errors.append(f"{label} references missing source {source_id}.")

        for event in self.events:
            if event.previous_event_id and event.previous_event_id not in event_ids:
                errors.append(f"Event:{event.id} references missing previous event {event.previous_event_id}.")
            if event.next_event_id and event.next_event_id not in event_ids:
                errors.append(f"Event:{event.id} references missing next event {event.next_event_id}.")

        if errors:
            raise ValueError("; ".join(errors))
        return self


class GraphResponse(ClaimKnowledgeGraph):
    validation: ValidationSummary


class JobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "processing", "complete", "failed"]
    files: list[DocumentListItem]
    validation: ValidationSummary | None = None
    error: str | None = None


class JobCreated(BaseModel):
    job_id: str
    status: Literal["queued", "processing", "complete", "failed"]


class SourcePreview(BaseModel):
    source_id: str
    document_id: str
    title: str
    citation_text: str
    document_link: str
    document_preview_url: str


def build_validation_summary(graph: ClaimKnowledgeGraph) -> ValidationSummary:
    missing_source_entities: list[str] = []
    invalid_references: list[str] = []
    source_ids = {source.id for source in graph.sources}
    document_ids = {document.id for document in graph.documents}

    entities: list[tuple[str, list[str]]] = [
        (f"Claim:{graph.claim.id}", graph.claim.source_ids),
    ]
    entities.extend((f"Event:{event.id}", event.source_ids) for event in graph.events)
    entities.extend((f"Party:{party.id}", party.source_ids) for party in graph.parties)
    entities.extend((f"FinancialItem:{item.id}", item.source_ids) for item in graph.financial_items)

    for label, refs in entities:
        if not refs:
            missing_source_entities.append(label)
        for source_id in refs:
            if source_id not in source_ids:
                invalid_references.append(f"{label}->{source_id}")

    for source in graph.sources:
        if source.document_id not in document_ids:
            invalid_references.append(f"Source:{source.id}->Document:{source.document_id}")

    return ValidationSummary(
        valid=not missing_source_entities and not invalid_references,
        missing_source_entities=missing_source_entities,
        invalid_references=invalid_references,
        document_count=len(graph.documents),
        source_count=len(graph.sources),
    )

