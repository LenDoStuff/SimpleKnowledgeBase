from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app import pdf_splitter as pdf_splitter_module
from backend.app.config import Settings
from backend.app.pdf_splitter import map_splitter_document_type, split_pdf_for_ingestion


def test_pdf_splitter_requires_azure_config(tmp_path: Path):
    source = tmp_path / "claim.pdf"
    source.write_bytes(b"%PDF-1.4")
    settings = Settings(data_dir=tmp_path, pdf_splitter_mode="required")

    with pytest.raises(ValueError, match="PDF splitter requires"):
        split_pdf_for_ingestion(source, output_dir=tmp_path / "out", settings=settings)


def test_pdf_splitter_rejects_non_required_mode(tmp_path: Path):
    source = tmp_path / "claim.pdf"
    source.write_bytes(b"%PDF-1.4")
    settings = Settings(data_dir=tmp_path, pdf_splitter_mode="auto")

    with pytest.raises(ValueError, match="must be required"):
        split_pdf_for_ingestion(source, output_dir=tmp_path / "out", settings=settings)


def test_pdf_splitter_api_failure_fails_upload_path(tmp_path: Path, monkeypatch):
    source = tmp_path / "claim.pdf"
    source.write_bytes(b"%PDF-1.4")
    settings = Settings(
        data_dir=tmp_path,
        pdf_splitter_mode="required",
        foundry_project_endpoint="https://example.services.ai.azure.com/api/projects/test",
        foundry_model_name="gpt-4.1-mini",
    )

    def failing_splitter(*args, **kwargs):
        raise RuntimeError("service unavailable")

    monkeypatch.setattr(pdf_splitter_module, "split_claim_file_azure", failing_splitter)

    with pytest.raises(RuntimeError, match="PDF splitter failed"):
        split_pdf_for_ingestion(
            source,
            output_dir=tmp_path / "splitter-output",
            settings=settings,
        )


def test_pdf_splitter_empty_api_result_fails_upload_path(tmp_path: Path, monkeypatch):
    source = tmp_path / "claim.pdf"
    source.write_bytes(b"%PDF-1.4")
    settings = Settings(
        data_dir=tmp_path,
        pdf_splitter_mode="required",
        foundry_project_endpoint="https://example.services.ai.azure.com/api/projects/test",
        foundry_model_name="gpt-4.1-mini",
    )

    def empty_splitter(*args, **kwargs):
        return SimpleNamespace(documents=[])

    monkeypatch.setattr(pdf_splitter_module, "split_claim_file_azure", empty_splitter)

    with pytest.raises(RuntimeError, match="returned no documents"):
        split_pdf_for_ingestion(
            source,
            output_dir=tmp_path / "splitter-output",
            settings=settings,
        )


def test_pdf_splitter_maps_splitter_documents(tmp_path: Path, monkeypatch):
    source = tmp_path / "claim.pdf"
    source.write_bytes(b"%PDF-1.4")
    split_path = tmp_path / "out" / "invoices" / "invoice_001.pdf"
    split_path.parent.mkdir(parents=True)
    split_path.write_bytes(b"%PDF-1.4")
    settings = Settings(
        data_dir=tmp_path,
        pdf_splitter_mode="required",
        foundry_project_endpoint="https://example.services.ai.azure.com/api/projects/test",
        foundry_model_name="gpt-4.1-mini",
    )
    calls = []

    def fake_splitter(*args, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            documents=[
                SimpleNamespace(
                    path=split_path,
                    document_type="invoices",
                    name="Mitigation Invoice",
                    summary="Invoice for emergency mitigation.",
                    start_page=1,
                    end_page=3,
                    page_count=3,
                )
            ]
        )

    monkeypatch.setattr(pdf_splitter_module, "split_claim_file_azure", fake_splitter)

    documents = split_pdf_for_ingestion(
        source,
        output_dir=tmp_path / "splitter-output",
        settings=settings,
    )

    assert set(calls[0]) == {
        "categories",
        "default_document_type",
        "deployment",
        "output_dir",
        "project_endpoint",
    }
    category_names = [category["name"] for category in calls[0]["categories"]]
    assert "invoices" in category_names
    assert calls[0]["default_document_type"] == "other"
    assert len(documents) == 1
    document = documents[0]
    assert document.path == split_path
    assert document.filename == "invoice_001.pdf"
    assert document.document_type == "invoice"
    assert document.sort_group == "Invoices"
    assert document.page_count == 3
    assert "pages 1-3" in document.summary
    assert "Invoice for emergency mitigation." in document.summary


def test_splitter_document_type_mapping(tmp_path: Path):
    settings = Settings(data_dir=tmp_path)

    assert map_splitter_document_type("invoices", settings) == ("invoice", "Invoices")
    assert map_splitter_document_type("reports", settings) == ("report", "Reports")
    assert map_splitter_document_type("photos", settings) == ("photo", "Photos / Images")
    assert map_splitter_document_type("claim_forms", settings) == ("claim_form", "Claim Forms")


def test_unknown_splitter_document_type_fails(tmp_path: Path):
    settings = Settings(data_dir=tmp_path)

    with pytest.raises(ValueError, match="unknown document category"):
        map_splitter_document_type("repair_invoices", settings)
