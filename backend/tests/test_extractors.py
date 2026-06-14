from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.document_extraction import DocumentBatchExtraction, ExtractedEvent, ExtractedParty
from backend.app.config import Settings
from backend.app.document_normalizer import NormalizedDocument
from backend.app.extractors import AzureFoundryExtractor, create_extractor
from backend.app.models import Claim, ClaimKnowledgeGraph, Document, Source, StoredDocument


class FakeResponses:
    def __init__(self, parse_outputs=None):
        self.calls = []
        self.parse_calls = []
        self.parse_outputs = list(parse_outputs or [])

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return type("Response", (), {"output_text": "normalized evidence"})()

    def parse(self, **kwargs):
        self.parse_calls.append(kwargs)
        parsed = self.parse_outputs.pop(0)
        return type("Response", (), {"output_parsed": parsed})()


class FakeCompletions:
    def __init__(self, graph):
        self.calls = []
        self.graph = graph

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        message = type("Message", (), {"parsed": self.graph})()
        choice = type("Choice", (), {"message": message})()
        return type("Completion", (), {"choices": [choice]})()


class FakeOpenAIClient:
    def __init__(self, graph=None, parse_outputs=None):
        self.responses = FakeResponses(parse_outputs=parse_outputs)
        self.beta = type(
            "Beta",
            (),
            {"chat": type("Chat", (), {"completions": FakeCompletions(graph)})()},
        )()


def test_pdf_document_extraction_uses_five_page_image_batches(tmp_path, monkeypatch):
    extractor = make_azure_extractor(tmp_path)
    path = tmp_path / "claim.pdf"
    path.write_bytes(b"%PDF-1.4")
    normalized = make_normalized_document(path, "pdf", pages=6)
    source = Source(id="src-1", citation_text="claim", document_link="/source", document_id=normalized.document.id)
    render_calls = []

    def fake_render(pdf_path, *, page_start, page_end, dpi, image_format, image_quality):
        render_calls.append((pdf_path, page_start, page_end, dpi, image_format, image_quality))
        return [
            SimpleNamespace(page_number=page_number, data_url=f"data:image/jpeg;base64,page-{page_number}")
            for page_number in range(page_start, page_end + 1)
        ]

    monkeypatch.setattr("backend.app.extractors.render_pdf_pages_as_images", fake_render)
    client = FakeOpenAIClient(
        parse_outputs=[
            DocumentBatchExtraction(
                page_start=1,
                page_end=5,
                document_summary="Loss and insured details.",
                events=[
                    ExtractedEvent(
                        event_type="Loss",
                        summary="Loss occurred.",
                        event_date="2024-04-12",
                        citation_text="Loss date 2024-04-12",
                    )
                ],
                citation_snippets=["Loss date 2024-04-12"],
            ),
            DocumentBatchExtraction(
                page_start=6,
                page_end=6,
                document_summary="Party details.",
                parties=[
                    ExtractedParty(
                        name="Metro Industrial",
                        party_type="Organization",
                        role="Insured",
                        citation_text="Insured: Metro Industrial",
                    )
                ],
            ),
        ]
    )

    extraction = extractor._extract_document_with_responses(client, normalized, source)

    assert [call[1:3] for call in render_calls] == [(1, 5), (6, 6)]
    assert client.responses.calls == []
    assert len(client.responses.parse_calls) == 2
    first_content = client.responses.parse_calls[0]["input"][0]["content"]
    assert first_content[0]["type"] == "input_text"
    assert normalized.document.id in first_content[0]["text"]
    assert source.id in first_content[0]["text"]
    assert '"start": 1' in first_content[0]["text"]
    assert '"end": 5' in first_content[0]["text"]
    assert [item["type"] for item in first_content].count("input_image") == 5
    assert not any(item.get("type") == "input_file" for item in first_content)
    assert len(extraction.batches) == 2
    assert len(extraction.events) == 1
    assert len(extraction.parties) == 1
    assert extraction.citation_text == "Loss date 2024-04-12"


def test_pdf_documents_do_not_use_whole_pdf_normalization(tmp_path):
    extractor = make_azure_extractor(tmp_path)
    path = tmp_path / "claim.pdf"
    path.write_bytes(b"%PDF-1.4")
    normalized = make_normalized_document(path, "pdf")
    source = Source(id="src-1", citation_text="claim", document_link="/source", document_id=normalized.document.id)

    with pytest.raises(ValueError, match="image batch extraction"):
        extractor._normalize_with_responses(FakeOpenAIClient(), normalized, source)


def test_azure_normalization_uses_image_input(tmp_path):
    extractor = make_azure_extractor(tmp_path)
    path = tmp_path / "photo.png"
    path.write_bytes(b"png")
    normalized = make_normalized_document(path, "image")
    source = Source(id="src-1", citation_text="photo", document_link="/source", document_id=normalized.document.id)
    client = FakeOpenAIClient()

    extractor._normalize_with_responses(client, normalized, source)

    content = client.responses.calls[0]["input"][0]["content"]
    assert content[1]["type"] == "input_image"
    assert content[1]["image_url"].startswith("data:image/png;base64,")


def test_azure_normalization_uses_docx_file_input(tmp_path):
    extractor = make_azure_extractor(tmp_path)
    path = tmp_path / "proof.docx"
    path.write_bytes(b"docx")
    normalized = make_normalized_document(path, "docx")
    source = Source(id="src-1", citation_text="proof", document_link="/source", document_id=normalized.document.id)
    client = FakeOpenAIClient()

    extractor._normalize_with_responses(client, normalized, source)

    content = client.responses.calls[0]["input"][0]["content"]
    assert content[1]["type"] == "input_file"
    assert content[1]["file_data"].startswith(
        "data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,"
    )


def test_azure_normalization_uses_xlsx_file_input(tmp_path):
    extractor = make_azure_extractor(tmp_path)
    path = tmp_path / "invoice.xlsx"
    path.write_bytes(b"xlsx")
    normalized = make_normalized_document(path, "xlsx")
    source = Source(id="src-1", citation_text="invoice", document_link="/source", document_id=normalized.document.id)
    client = FakeOpenAIClient()

    extractor._normalize_with_responses(client, normalized, source)

    content = client.responses.calls[0]["input"][0]["content"]
    assert content[1]["type"] == "input_file"
    assert content[1]["file_data"].startswith(
        "data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,"
    )


def test_default_extractor_fails_clearly_without_azure_config(tmp_path):
    settings = Settings(data_dir=tmp_path, extraction_mode="azure")
    extractor = create_extractor(settings)

    path = tmp_path / "claim.png"
    path.write_bytes(b"png")
    normalized = make_normalized_document(path, "image")

    try:
        extractor.extract("job-1", [normalized])
    except RuntimeError as exc:
        assert "Azure extraction is not configured" in str(exc)
    else:
        raise AssertionError("Expected missing Azure configuration to fail.")


def test_azure_structured_extraction_uses_claim_graph_response_format(tmp_path):
    extractor = make_azure_extractor(tmp_path)
    graph = ClaimKnowledgeGraph(
        claim=Claim(
            id="claim-1",
            summary="Claim",
            status="Review",
            line_of_business="Property",
            loss_date="2024-04-12",
            source_ids=["src-1"],
        ),
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
            Source(id="src-1", citation_text="Loss date", document_link="/source", document_id="doc-1")
        ],
    )
    client = FakeOpenAIClient(graph)

    parsed = extractor._extract_graph_with_structured_outputs(
        client,
        [{"document_extraction": {"events": [{"summary": "Loss date"}]}}],
    )

    call = client.beta.chat.completions.calls[0]
    assert parsed == graph
    assert call["response_format"] is ClaimKnowledgeGraph
    assert call["model"] == "test-model"
    assert "document_level_extractions" in call["messages"][1]["content"]


def make_azure_extractor(tmp_path: Path) -> AzureFoundryExtractor:
    settings = Settings(
        data_dir=tmp_path,
        extraction_mode="azure",
        foundry_project_endpoint="https://example.services.ai.azure.com/api/projects/test",
        foundry_model_name="test-model",
    )
    return AzureFoundryExtractor(settings)


def make_normalized_document(path: Path, file_type: str, pages: int = 1) -> NormalizedDocument:
    document = StoredDocument(
        id="doc-1",
        summary="Uploaded file",
        document_type="claim_forms",
        title=path.stem,
        document_date=None,
        content_uri="/api/documents/doc-1/file",
        filename=path.name,
        file_type=file_type,
        status="processed",
        pages=pages,
        sort_group="Claim Forms",
        error=None,
        stored_path=str(path),
    )
    return NormalizedDocument(document=document, extracted_text="extracted text", page_count=pages)
