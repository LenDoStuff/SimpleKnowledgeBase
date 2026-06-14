import pytest
from pydantic import ValidationError

from backend.app.models import Claim, ClaimKnowledgeGraph, Document, Event, Source, build_validation_summary


def valid_graph() -> ClaimKnowledgeGraph:
    return ClaimKnowledgeGraph(
        claim=Claim(
            id="claim-1",
            summary="Claim summary",
            status="Review",
            line_of_business="Property",
            loss_date="2024-04-12",
            source_ids=["src-1"],
        ),
        events=[
            Event(
                id="event-1",
                summary="Loss occurred",
                event_type="Loss",
                event_date="2024-04-12",
                source_ids=["src-1"],
            )
        ],
        parties=[],
        financial_items=[],
        documents=[
            Document(
                id="doc-1",
                summary="Document",
                document_type="claim_forms",
                title="FNOL",
                document_date=None,
                content_uri="/api/documents/doc-1/file",
            )
        ],
        sources=[
            Source(
                id="src-1",
                citation_text="Date of loss: 2024-04-12",
                document_link="/api/documents/doc-1/source/src-1",
                document_id="doc-1",
            )
        ],
    )


def test_document_has_no_confidence_field():
    assert "confidence" not in Document.model_fields


def test_graph_accepts_valid_source_references():
    graph = valid_graph()
    validation = build_validation_summary(graph)
    assert validation.valid is True
    assert validation.source_count == 1


def test_claim_requires_at_least_one_source():
    with pytest.raises(ValidationError):
        Claim(
            id="claim-1",
            summary="Claim summary",
            status="Review",
            line_of_business="Property",
            loss_date=None,
            source_ids=[],
        )


def test_invalid_source_reference_is_rejected():
    payload = valid_graph().model_dump()
    payload["claim"]["source_ids"] = ["missing"]
    with pytest.raises(ValidationError):
        ClaimKnowledgeGraph(**payload)


def test_invalid_event_link_is_rejected():
    payload = valid_graph().model_dump()
    payload["events"][0]["next_event_id"] = "missing-event"
    with pytest.raises(ValidationError):
        ClaimKnowledgeGraph(**payload)
