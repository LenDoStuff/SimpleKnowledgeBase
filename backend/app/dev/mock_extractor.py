from __future__ import annotations

import re

from backend.app.document_normalizer import NormalizedDocument
from backend.app.extractors import ClaimExtractor, build_sources
from backend.app.models import Claim, ClaimKnowledgeGraph, Event, FinancialItem, Party


class MockClaimExtractor(ClaimExtractor):
    """Explicit dev/test extractor. Never selected unless mock mode is configured."""

    def extract(self, job_id: str, documents: list[NormalizedDocument]) -> ClaimKnowledgeGraph:
        sources = build_sources(job_id, documents)
        source_ids = [source.id for source in sources]
        first_source = source_ids[:1]
        all_documents = [document.document.to_document() for document in documents]
        loss_date = _infer_date(documents) or "2024-04-12"
        amount = _infer_amount(documents) or 48500.0

        events = [
            Event(
                id=f"event-{job_id[:8]}-loss",
                summary="Loss occurred and was reported in the claim file.",
                event_type="Loss",
                event_date=loss_date,
                next_event_id=f"event-{job_id[:8]}-review",
                source_ids=first_source or source_ids,
            ),
            Event(
                id=f"event-{job_id[:8]}-review",
                summary="Claim documents were collected and sorted for review.",
                event_type="Review",
                previous_event_id=f"event-{job_id[:8]}-loss",
                next_event_id=f"event-{job_id[:8]}-extraction",
                source_ids=source_ids[1:2] or source_ids,
            ),
            Event(
                id=f"event-{job_id[:8]}-extraction",
                summary="Structured claim graph was generated from uploaded evidence.",
                event_type="Extraction",
                previous_event_id=f"event-{job_id[:8]}-review",
                source_ids=source_ids,
            ),
        ]

        parties = [
            Party(
                id=f"party-{job_id[:8]}-insured",
                summary="Insured party identified from uploaded claim materials.",
                name=_infer_party_name(documents) or "Uploaded Claim Insured",
                party_type="Organization",
                role="Insured",
                source_ids=first_source or source_ids,
            ),
            Party(
                id=f"party-{job_id[:8]}-handler",
                summary="Internal claim handling team.",
                name="Claims Operations",
                party_type="Organization",
                role="Adjuster",
                source_ids=source_ids[1:2] or source_ids,
            ),
        ]

        financial_items = [
            FinancialItem(
                id=f"fin-{job_id[:8]}-invoice",
                summary="Estimated mitigation or repair invoice amount.",
                financial_type="Invoice",
                amount=amount,
                currency="USD",
                booking_date=loss_date,
                source_ids=source_ids[-1:] or source_ids,
            )
        ]

        graph = ClaimKnowledgeGraph(
            claim=Claim(
                id=f"claim-{job_id[:8]}",
                summary=f"Industrial property claim assembled from {len(documents)} uploaded document(s).",
                status="Review",
                line_of_business="Property",
                loss_date=loss_date,
                source_ids=source_ids,
            ),
            events=events,
            parties=parties,
            financial_items=financial_items,
            documents=all_documents,
            sources=sources,
        )
        return graph


def _infer_date(documents: list[NormalizedDocument]) -> str | None:
    for document in documents:
        match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", document.extracted_text)
        if match:
            return match.group(1)
    return None


def _infer_party_name(documents: list[NormalizedDocument]) -> str | None:
    for document in documents:
        title = document.document.title.strip()
        if title:
            return title
    return None


def _infer_amount(documents: list[NormalizedDocument]) -> float | None:
    for document in documents:
        match = re.search(r"\$?\b(\d{2,3}(?:,\d{3})+(?:\.\d{2})?)\b", document.extracted_text)
        if match:
            return float(match.group(1).replace(",", ""))
    return None
