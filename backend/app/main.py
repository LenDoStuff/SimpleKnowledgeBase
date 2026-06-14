from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.app.config import Settings, get_settings
from backend.app.extractors import ClaimExtractor, create_extractor
from backend.app.file_types import classify_document, inspect_filename, unique_storage_name
from backend.app.models import DocumentListItem, GraphResponse, JobCreated, JobStatus, SourcePreview, StoredDocument
from backend.app.pdf_splitter import split_pdf_for_ingestion
from backend.app.processing import process_job
from backend.app.storage import Storage, graph_response_payload


def create_app(settings: Settings | None = None, extractor: ClaimExtractor | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    storage = Storage(active_settings)
    active_extractor = extractor or create_extractor(active_settings)

    app = FastAPI(title="Claim Structurer API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_storage() -> Storage:
        return storage

    def get_extractor() -> ClaimExtractor:
        return active_extractor

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "extraction_mode": active_settings.extraction_mode}

    @app.post("/api/jobs", response_model=JobCreated)
    async def create_job_endpoint(
        background_tasks: BackgroundTasks,
        files: list[UploadFile] = File(...),
        storage_dep: Storage = Depends(get_storage),
        extractor_dep: ClaimExtractor = Depends(get_extractor),
    ) -> JobCreated:
        if not files:
            raise HTTPException(status_code=400, detail="Upload at least one claim file.")

        staged_files = []
        used_storage_names: set[str] = set()
        for upload in files:
            try:
                inspection = inspect_filename(upload.filename or "")
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            content = await upload.read()
            if not content:
                raise HTTPException(status_code=400, detail=f"{upload.filename} is empty.")
            if len(content) > active_settings.max_upload_bytes:
                raise HTTPException(status_code=413, detail=f"{upload.filename} exceeds the v1 200 MB limit.")
            storage_name = unique_storage_name(upload.filename or "claim-file", used_storage_names)
            staged_files.append((upload.filename or storage_name, inspection.file_type, content, storage_name))

        job_id = uuid4().hex
        job_dir = active_settings.uploads_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        documents = []

        for original_name, file_type, content, storage_name in staged_files:
            stored_path = job_dir / storage_name
            stored_path.write_bytes(content)
            split_documents = []
            if file_type == "pdf":
                try:
                    split_documents = split_pdf_for_ingestion(
                        stored_path,
                        output_dir=job_dir / "splitter-output",
                        settings=active_settings,
                    )
                except Exception as exc:
                    raise HTTPException(status_code=502, detail=str(exc)) from exc

            if file_type == "pdf":
                for split_document in split_documents:
                    document_id = f"doc-{uuid4().hex[:12]}"
                    documents.append(
                        StoredDocument(
                            id=document_id,
                            summary=split_document.summary,
                            document_type=split_document.document_type,
                            title=split_document.title,
                            document_date=None,
                            content_uri=f"/api/documents/{document_id}/file",
                            filename=split_document.filename,
                            file_type="pdf",
                            status="queued",
                            pages=split_document.page_count,
                            sort_group=split_document.sort_group,
                            error=None,
                            stored_path=str(split_document.path),
                        )
                    )
            else:
                try:
                    classified_category = classify_document(original_name, file_type)
                    document_type = active_settings.require_document_category(classified_category)
                    sort_group = active_settings.document_sort_group(document_type)
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc
                document_id = f"doc-{uuid4().hex[:12]}"
                summary = f"Uploaded {original_name}"
                document = StoredDocument(
                    id=document_id,
                    summary=summary,
                    document_type=document_type,
                    title=Path(original_name).stem,
                    document_date=None,
                    content_uri=f"/api/documents/{document_id}/file",
                    filename=original_name,
                    file_type=file_type,
                    status="queued",
                    pages=1 if file_type == "image" else None,
                    sort_group=sort_group,
                    error=None,
                    stored_path=str(stored_path),
                )
                documents.append(document)

        storage_dep.create_job(job_id, documents)
        background_tasks.add_task(process_job, job_id, storage_dep, extractor_dep)
        return JobCreated(job_id=job_id, status="queued")

    @app.get("/api/jobs/{job_id}", response_model=JobStatus)
    def get_job(job_id: str, storage_dep: Storage = Depends(get_storage)) -> JobStatus:
        job = storage_dep.get_job_status(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found.")
        return job

    @app.get("/api/jobs/{job_id}/documents", response_model=list[DocumentListItem])
    def get_documents(job_id: str, storage_dep: Storage = Depends(get_storage)) -> list[DocumentListItem]:
        if not storage_dep.get_job_status(job_id):
            raise HTTPException(status_code=404, detail="Job not found.")
        return [document.to_public() for document in storage_dep.list_documents(job_id)]

    @app.get("/api/jobs/{job_id}/graph")
    def get_graph(job_id: str, storage_dep: Storage = Depends(get_storage)) -> dict:
        graph = storage_dep.get_graph(job_id)
        validation = storage_dep.get_validation(job_id)
        if not graph or not validation:
            raise HTTPException(status_code=404, detail="Graph not ready.")
        GraphResponse(**graph_response_payload(graph, validation))
        return graph_response_payload(graph, validation)

    @app.get("/api/documents/{document_id}/source/{source_id}", response_model=SourcePreview)
    def get_source(
        document_id: str,
        source_id: str,
        storage_dep: Storage = Depends(get_storage),
    ) -> SourcePreview:
        preview = storage_dep.get_source_preview(document_id, source_id)
        if not preview:
            raise HTTPException(status_code=404, detail="Source not found.")
        return preview

    @app.get("/api/documents/{document_id}/file")
    def get_document_file(document_id: str, storage_dep: Storage = Depends(get_storage)) -> FileResponse:
        document = storage_dep.get_document(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found.")
        path = Path(document.stored_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Stored document not found.")
        return FileResponse(path, filename=document.filename)

    @app.delete("/api/jobs/{job_id}")
    def delete_job(job_id: str, storage_dep: Storage = Depends(get_storage)) -> dict[str, str]:
        job = storage_dep.get_job_status(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found.")
        job_dir = active_settings.uploads_dir / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir)
        return {"status": "deleted"}

    return app


app = create_app()
