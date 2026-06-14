from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from claim_file_splitter import split_claim_file_azure

from backend.app.config import Settings


@dataclass(frozen=True)
class PdfSplitDocument:
    path: Path
    filename: str
    document_type: str
    sort_group: str
    title: str
    summary: str
    page_count: int


def split_pdf_for_ingestion(
    source_pdf: Path,
    *,
    output_dir: Path,
    settings: Settings,
) -> list[PdfSplitDocument]:
    mode = settings.pdf_splitter_mode.lower().strip()
    if mode != "required":
        raise ValueError("CLAIM_STRUCTURER_PDF_SPLITTER_MODE must be required; PDF ingestion is API-only.")

    project_endpoint = settings.pdf_splitter_project_endpoint
    deployment = settings.pdf_splitter_deployment
    if not project_endpoint or not deployment:
        raise ValueError(
            "PDF splitter requires an Azure project endpoint and model deployment. "
            "Set FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL_NAME, or AZURE_AI_PROJECT_ENDPOINT "
            "and AZURE_OPENAI_DEPLOYMENT."
        )

    split_output_dir = output_dir / f"{source_pdf.stem}-split"
    try:
        result = split_claim_file_azure(
            source_pdf,
            output_dir=split_output_dir,
            categories=settings.pdf_splitter_categories,
            default_document_type=settings.pdf_splitter_default_document_type,
            project_endpoint=project_endpoint,
            deployment=deployment,
        )
    except Exception as exc:
        raise RuntimeError(f"PDF splitter failed for {source_pdf.name}: {exc}") from exc

    documents = [
        _to_pdf_split_document(source_pdf, document, index, settings)
        for index, document in enumerate(result.documents, start=1)
    ]
    if not documents:
        raise RuntimeError(f"PDF splitter returned no documents for {source_pdf.name}.")
    return documents


def _to_pdf_split_document(
    source_pdf: Path,
    split_document: object,
    index: int,
    settings: Settings,
) -> PdfSplitDocument:
    splitter_type = str(getattr(split_document, "document_type", "other"))
    page_count = int(getattr(split_document, "page_count", 1) or 1)
    start_page = int(getattr(split_document, "start_page", index) or index)
    end_page = int(getattr(split_document, "end_page", start_page) or start_page)
    document_name = str(getattr(split_document, "name", "") or splitter_type.replace("_", " ").title())
    splitter_summary = str(getattr(split_document, "summary", "") or "")
    document_type, sort_group = map_splitter_document_type(splitter_type, settings)
    split_path = Path(getattr(split_document, "path"))
    return PdfSplitDocument(
        path=split_path,
        filename=split_path.name,
        document_type=document_type,
        sort_group=sort_group,
        title=document_name,
        summary=(
            f"Split from {source_pdf.name}, pages {start_page}-{end_page}. "
            f"Splitter category: {splitter_type}. {splitter_summary}"
        ),
        page_count=page_count,
    )


def map_splitter_document_type(splitter_type: str, settings: Settings) -> tuple[str, str]:
    normalized = splitter_type.strip().lower()
    category = settings.document_category_by_name.get(normalized)
    if not category:
        raise ValueError(f"PDF splitter returned unknown document category {splitter_type!r}.")
    return category.document_type, category.sort_group
