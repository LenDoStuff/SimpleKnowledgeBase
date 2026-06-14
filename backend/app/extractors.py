from __future__ import annotations

import base64
import json
import mimetypes
from abc import ABC, abstractmethod
from pathlib import Path

from backend.app.config import Settings
from backend.app.document_extraction import (
    DocumentBatchExtraction,
    DocumentExtraction,
    consolidate_document_batches,
    non_pdf_document_extraction,
)
from backend.app.document_normalizer import NormalizedDocument
from backend.app.models import ClaimKnowledgeGraph, Source
from backend.app.pdf_images import page_batches, render_pdf_pages_as_images


class ClaimExtractor(ABC):
    @abstractmethod
    def extract(self, job_id: str, documents: list[NormalizedDocument]) -> ClaimKnowledgeGraph:
        raise NotImplementedError


class MissingAzureConfigurationExtractor(ClaimExtractor):
    def __init__(self, message: str):
        self.message = message

    def extract(self, job_id: str, documents: list[NormalizedDocument]) -> ClaimKnowledgeGraph:
        raise RuntimeError(self.message)


class AzureFoundryExtractor(ClaimExtractor):
    def __init__(self, settings: Settings):
        if not settings.azure_configured:
            raise ValueError("FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL_NAME are required for Azure mode.")
        self.settings = settings

    def extract(self, job_id: str, documents: list[NormalizedDocument]) -> ClaimKnowledgeGraph:
        from azure.ai.projects import AIProjectClient
        from azure.identity import DefaultAzureCredential

        sources = build_sources(job_id, documents)
        extraction_bundle = []

        with DefaultAzureCredential() as credential:
            with AIProjectClient(endpoint=self.settings.foundry_project_endpoint, credential=credential) as project:
                with project.get_openai_client() as openai_client:
                    for normalized, source in zip(documents, sources, strict=True):
                        document_extraction = self._extract_document_with_responses(
                            openai_client,
                            normalized,
                            source,
                        )
                        source = source.model_copy(update={"citation_text": document_extraction.citation_text})
                        extraction_bundle.append(
                            {
                                "document": normalized.document.to_document().model_dump(),
                                "source": source.model_dump(),
                                "document_extraction": document_extraction.model_dump(),
                            }
                        )
                    graph = self._extract_graph_with_structured_outputs(openai_client, extraction_bundle)

        return graph

    def _extract_document_with_responses(
        self,
        openai_client,
        normalized: NormalizedDocument,
        source: Source,
    ) -> DocumentExtraction:
        if normalized.document.file_type == "pdf":
            return self._extract_pdf_document(openai_client, normalized, source)

        evidence = self._normalize_with_responses(openai_client, normalized, source)
        return non_pdf_document_extraction(
            document_id=normalized.document.id,
            source_id=source.id,
            evidence=evidence,
        )

    def _extract_pdf_document(
        self,
        openai_client,
        normalized: NormalizedDocument,
        source: Source,
    ) -> DocumentExtraction:
        document = normalized.document
        pdf_path = Path(document.stored_path)
        page_count = normalized.page_count or document.pages or 1
        batches = []

        for page_start, page_end in page_batches(page_count, self.settings.document_extraction_page_batch_size):
            images = render_pdf_pages_as_images(
                pdf_path,
                page_start=page_start,
                page_end=page_end,
                dpi=self.settings.document_extraction_render_dpi,
                image_format=self.settings.document_extraction_image_format,
                image_quality=self.settings.document_extraction_image_quality,
            )
            batches.append(
                self._extract_pdf_page_batch(
                    openai_client,
                    normalized,
                    source,
                    page_start,
                    page_end,
                    images,
                )
            )

        return consolidate_document_batches(
            document_id=document.id,
            source_id=source.id,
            batches=batches,
        )

    def _extract_pdf_page_batch(
        self,
        openai_client,
        normalized: NormalizedDocument,
        source: Source,
        page_start: int,
        page_end: int,
        images: list,
    ) -> DocumentBatchExtraction:
        if not images:
            raise RuntimeError(f"No rendered page images for {normalized.document.filename} pages {page_start}-{page_end}.")

        content = [
            {
                "type": "input_text",
                "text": self._pdf_batch_prompt(normalized, source, page_start, page_end),
            }
        ]
        for image in images:
            content.append({"type": "input_text", "text": f"Page {image.page_number}"})
            content.append({"type": "input_image", "image_url": image.data_url})

        response = openai_client.responses.parse(
            model=self.settings.foundry_model_name,
            input=[{"role": "user", "content": content}],
            text_format=DocumentBatchExtraction,
        )
        return response.output_parsed

    def _pdf_batch_prompt(
        self,
        normalized: NormalizedDocument,
        source: Source,
        page_start: int,
        page_end: int,
    ) -> str:
        return json.dumps(
            {
                "task": "Extract document-level industrial claim facts from this page-image batch.",
                "document": normalized.document.to_document().model_dump(),
                "source": source.model_dump(),
                "page_range": {"start": page_start, "end": page_end},
                "instructions": [
                    "Extract only facts visible in these page images.",
                    "Capture claim facts, events, parties, financial items, and citation snippets.",
                    "Use concise citation_text values that can support the final source citation.",
                    "Do not invent facts that are not supported by the page images.",
                ],
            },
            indent=2,
        )

    def _normalize_with_responses(self, openai_client, normalized: NormalizedDocument, source: Source) -> str:
        document = normalized.document
        prompt = (
            "Normalize this claim document for downstream industrial claim knowledge graph extraction. "
            "Return concise markdown evidence only. Preserve dates, names, amounts, policy numbers, "
            f"and quoteable citation text for source id {source.id}."
        )
        content = [{"type": "input_text", "text": prompt}]
        path = Path(document.stored_path)

        if document.file_type == "image":
            mime_type = _mime_type(document.filename, "image/png")
            content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:{mime_type};base64,{_base64_file(path)}",
                }
            )
        elif document.file_type in {"docx", "xlsx"}:
            mime_type = _mime_type(document.filename, "application/octet-stream")
            content.append(
                {
                    "type": "input_file",
                    "filename": document.filename,
                    "file_data": f"data:{mime_type};base64,{_base64_file(path)}",
                }
            )
        elif document.file_type == "pdf":
            raise ValueError("PDF documents must use document-level image batch extraction.")
        else:
            raise ValueError(f"No API-backed ingestion path configured for file type {document.file_type}.")

        response = openai_client.responses.create(
            model=self.settings.foundry_model_name,
            input=[{"role": "user", "content": content}],
        )
        return response.output_text

    def _extract_graph_with_structured_outputs(self, openai_client, extraction_bundle: list[dict]) -> ClaimKnowledgeGraph:
        system = (
            "You extract an industrial claim knowledge graph. Return only schema-valid data. "
            "Consume only the provided document-level structured extractions. "
            "Every Claim, Event, Party, and FinancialItem must reference at least one provided Source id. "
            "Return the provided Documents and Sources in the final graph. "
            "Do not invent source ids. Document has no confidence field."
        )
        user = json.dumps(
            {
                "task": "Create the claim knowledge graph from these document-level extractions.",
                "document_level_extractions": extraction_bundle,
            },
            indent=2,
        )
        completion = openai_client.beta.chat.completions.parse(
            model=self.settings.foundry_model_name,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format=ClaimKnowledgeGraph,
        )
        return completion.choices[0].message.parsed


def create_extractor(settings: Settings) -> ClaimExtractor:
    mode = settings.extraction_mode.lower()
    if mode == "mock":
        from backend.app.dev.mock_extractor import MockClaimExtractor

        return MockClaimExtractor()
    if mode == "azure":
        if not settings.azure_configured:
            return MissingAzureConfigurationExtractor(
                "Azure extraction is not configured. Set FOUNDRY_PROJECT_ENDPOINT "
                "and FOUNDRY_MODEL_NAME, or run with CLAIM_STRUCTURER_EXTRACTION_MODE=mock "
                "for explicit local development only."
            )
        return AzureFoundryExtractor(settings)
    raise ValueError("CLAIM_STRUCTURER_EXTRACTION_MODE must be azure or mock.")


def build_sources(job_id: str, documents: list[NormalizedDocument]) -> list[Source]:
    sources = []
    for index, normalized in enumerate(documents, start=1):
        document = normalized.document
        source_id = f"src-{job_id[:8]}-{index}"
        citation = _citation_text(normalized)
        sources.append(
            Source(
                id=source_id,
                citation_text=citation,
                document_link=f"/api/documents/{document.id}/source/{source_id}",
                document_id=document.id,
            )
        )
    return sources


def _citation_text(normalized: NormalizedDocument) -> str:
    text = normalized.extracted_text.strip()
    if len(text) > 220:
        text = f"{text[:217]}..."
    return text or f"Evidence from {normalized.document.filename}"


def _base64_file(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def _mime_type(filename: str, default: str) -> str:
    known_types = {
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".pdf": "application/pdf",
    }
    return known_types.get(Path(filename).suffix.lower()) or mimetypes.guess_type(filename)[0] or default
