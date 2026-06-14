from pathlib import Path
from time import sleep

from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app.config import Settings
from backend.app.dev.mock_extractor import MockClaimExtractor
from backend.app.pdf_splitter import PdfSplitDocument


def make_client(tmp_path: Path, settings: Settings | None = None) -> TestClient:
    settings = settings or Settings(data_dir=tmp_path, extraction_mode="mock")
    app = main_module.create_app(settings=settings, extractor=MockClaimExtractor())
    return TestClient(app)


def test_upload_processes_claim_files_and_returns_graph(tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "split_pdf_for_ingestion", fake_split_pdf_for_ingestion)
    client = make_client(tmp_path)
    response = client.post(
        "/api/jobs",
        files=[
            ("files", ("First Notice of Loss.pdf", b"%PDF-1.4\nClaim loss date 2024-04-12\n%%EOF", "application/pdf")),
            ("files", ("Engineer Report.pdf", b"%PDF-1.4\nMetro Industrial, LLC report\n%%EOF", "application/pdf")),
            ("files", ("Mitigation Invoice.xlsx", b"not-a-real-xlsx-but-non-empty", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")),
        ],
    )
    assert response.status_code == 200, response.text
    job_id = response.json()["job_id"]

    for _ in range(10):
        status = client.get(f"/api/jobs/{job_id}").json()
        if status["status"] in {"complete", "failed"}:
            break
        sleep(0.1)

    assert status["status"] == "complete", status
    assert status["validation"]["valid"] is True
    assert len(status["files"]) == 3

    documents = client.get(f"/api/jobs/{job_id}/documents").json()
    assert documents[0]["sort_group"] == "Claim Forms"
    assert any(document["sort_group"] == "Invoices" for document in documents)

    graph = client.get(f"/api/jobs/{job_id}/graph").json()
    assert graph["claim"]["source_ids"]
    assert graph["validation"]["source_count"] == 3

    first_source = graph["sources"][0]
    preview = client.get(f"/api/documents/{first_source['document_id']}/source/{first_source['id']}").json()
    assert preview["source_id"] == first_source["id"]
    assert preview["citation_text"]


def test_empty_upload_is_rejected(tmp_path):
    client = make_client(tmp_path)
    response = client.post(
        "/api/jobs",
        files=[("files", ("empty.pdf", b"", "application/pdf"))],
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"]


def test_legacy_upload_is_rejected(tmp_path):
    client = make_client(tmp_path)
    response = client.post(
        "/api/jobs",
        files=[("files", ("old-claim.doc", b"legacy", "application/msword"))],
    )
    assert response.status_code == 400
    assert "Legacy" in response.json()["detail"]


def test_production_missing_azure_config_fails_job(tmp_path):
    settings = Settings(data_dir=tmp_path)
    app = main_module.create_app(settings=settings)
    client = TestClient(app)

    response = client.post(
        "/api/jobs",
        files=[("files", ("claim-photo.png", b"png", "image/png"))],
    )
    assert response.status_code == 200, response.text
    job_id = response.json()["job_id"]

    status = client.get(f"/api/jobs/{job_id}").json()

    assert status["status"] == "failed"
    assert "Azure extraction is not configured" in status["error"]


def test_pdf_upload_requires_splitter_config(tmp_path):
    client = make_client(tmp_path)

    response = client.post(
        "/api/jobs",
        files=[("files", ("combined-claim.pdf", b"%PDF-1.4 combined", "application/pdf"))],
    )

    assert response.status_code == 502
    assert "PDF splitter requires" in response.json()["detail"]


def test_pdf_splitter_api_failure_rejects_upload(tmp_path, monkeypatch):
    def fail_splitter(source_pdf, *, output_dir, settings):
        raise RuntimeError("splitter API unavailable")

    monkeypatch.setattr(main_module, "split_pdf_for_ingestion", fail_splitter)
    client = make_client(tmp_path)

    response = client.post(
        "/api/jobs",
        files=[("files", ("combined-claim.pdf", b"%PDF-1.4 combined", "application/pdf"))],
    )

    assert response.status_code == 502
    assert "splitter API unavailable" in response.json()["detail"]


def test_pdf_upload_uses_splitter_documents(tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "split_pdf_for_ingestion", fake_split_pdf_for_ingestion)
    settings = Settings(
        data_dir=tmp_path,
        extraction_mode="mock",
        foundry_project_endpoint="https://example.services.ai.azure.com/api/projects/test",
        foundry_model_name="gpt-4.1-mini",
    )
    app = main_module.create_app(settings=settings, extractor=MockClaimExtractor())
    client = TestClient(app)

    response = client.post(
        "/api/jobs",
        files=[("files", ("combined-claim.pdf", b"%PDF-1.4 combined", "application/pdf"))],
    )
    assert response.status_code == 200, response.text
    job_id = response.json()["job_id"]
    status = client.get(f"/api/jobs/{job_id}").json()

    assert status["files"][0]["filename"] == "claim - 01 - First Notice.pdf"
    assert status["files"][0]["pages"] == 2
    assert status["files"][0]["sort_group"] == "Claim Forms"


def fake_split_pdf_for_ingestion(source_pdf, *, output_dir, settings):
    split_path = output_dir / "claim_forms" / f"{source_pdf.stem}_001.pdf"
    split_path.parent.mkdir(parents=True, exist_ok=True)
    split_path.write_bytes(b"%PDF-1.4 split")
    return [
        PdfSplitDocument(
            path=split_path,
            filename="claim - 01 - First Notice.pdf",
            document_type="claim_form",
            sort_group="Claim Forms",
            title="First Notice",
            summary="Split from claim.pdf, pages 1-2.",
            page_count=2,
        )
    ]
