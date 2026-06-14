from __future__ import annotations

from backend.app.document_normalizer import normalize_document
from backend.app.extractors import ClaimExtractor
from backend.app.models import build_validation_summary
from backend.app.storage import Storage


def process_job(job_id: str, storage: Storage, extractor: ClaimExtractor) -> None:
    try:
        storage.update_job_status(job_id, "processing")
        normalized_documents = []
        for document in storage.list_documents(job_id):
            try:
                normalized = normalize_document(document)
                updated = document.model_copy(update={"status": "processed", "pages": normalized.page_count, "error": None})
                storage.update_document(updated)
                normalized_documents.append(normalized.model_copy(update={"document": updated}))
            except Exception as exc:  # pragma: no cover - defensive status update
                failed = document.model_copy(update={"status": "failed", "error": str(exc)})
                storage.update_document(failed)
                raise

        graph = extractor.extract(job_id, normalized_documents)
        validation = build_validation_summary(graph)
        storage.save_graph(job_id, graph, validation)
    except Exception as exc:
        storage.update_job_status(job_id, "failed", str(exc))
