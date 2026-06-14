from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from backend.app.config import Settings
from backend.app.models import (
    ClaimKnowledgeGraph,
    DocumentListItem,
    JobStatus,
    Source,
    SourcePreview,
    StoredDocument,
    ValidationSummary,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Storage:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.settings.database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    error TEXT,
                    validation_json TEXT,
                    graph_json TEXT
                );

                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    document_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    document_date TEXT,
                    content_uri TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    pages INTEGER,
                    sort_group TEXT NOT NULL,
                    error TEXT,
                    stored_path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES jobs(job_id)
                );

                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    citation_text TEXT NOT NULL,
                    document_link TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES jobs(job_id),
                    FOREIGN KEY(document_id) REFERENCES documents(id)
                );
                """
            )

    def create_job(self, job_id: str, documents: list[StoredDocument]) -> None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO jobs (job_id, status, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (job_id, "queued", now, now),
            )
            for document in documents:
                connection.execute(
                    """
                    INSERT INTO documents (
                        id, job_id, summary, document_type, title, document_date, content_uri,
                        filename, file_type, status, pages, sort_group, error, stored_path, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        document.id,
                        job_id,
                        document.summary,
                        document.document_type,
                        document.title,
                        document.document_date,
                        document.content_uri,
                        document.filename,
                        document.file_type,
                        document.status,
                        document.pages,
                        document.sort_group,
                        document.error,
                        document.stored_path,
                        now,
                    ),
                )

    def update_job_status(self, job_id: str, status: str, error: str | None = None) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE jobs SET status = ?, error = ?, updated_at = ? WHERE job_id = ?",
                (status, error, utc_now(), job_id),
            )

    def update_document(self, document: StoredDocument) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE documents
                   SET summary = ?, document_type = ?, title = ?, document_date = ?, content_uri = ?,
                       filename = ?, file_type = ?, status = ?, pages = ?, sort_group = ?, error = ?,
                       stored_path = ?
                 WHERE id = ?
                """,
                (
                    document.summary,
                    document.document_type,
                    document.title,
                    document.document_date,
                    document.content_uri,
                    document.filename,
                    document.file_type,
                    document.status,
                    document.pages,
                    document.sort_group,
                    document.error,
                    document.stored_path,
                    document.id,
                ),
            )

    def list_documents(self, job_id: str) -> list[StoredDocument]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM documents WHERE job_id = ?",
                (job_id,),
            ).fetchall()

        documents = [self._row_to_stored_document(row) for row in rows]
        document_sort_order = self.settings.document_sort_order
        return sorted(
            documents,
            key=lambda item: (document_sort_order.get(item.document_type, 999), item.filename.lower()),
        )

    def get_document(self, document_id: str) -> StoredDocument | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        return self._row_to_stored_document(row) if row else None

    def get_job_status(self, job_id: str) -> JobStatus | None:
        with self.connect() as connection:
            job = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not job:
            return None

        validation = None
        if job["validation_json"]:
            validation = ValidationSummary.model_validate_json(job["validation_json"])

        return JobStatus(
            job_id=job_id,
            status=job["status"],
            files=[document.to_public() for document in self.list_documents(job_id)],
            validation=validation,
            error=job["error"],
        )

    def save_graph(self, job_id: str, graph: ClaimKnowledgeGraph, validation: ValidationSummary) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM sources WHERE job_id = ?", (job_id,))
            for source in graph.sources:
                connection.execute(
                    """
                    INSERT INTO sources (id, job_id, document_id, citation_text, document_link)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (source.id, job_id, source.document_id, source.citation_text, source.document_link),
                )
            connection.execute(
                """
                UPDATE jobs
                   SET graph_json = ?, validation_json = ?, status = ?, updated_at = ?, error = NULL
                 WHERE job_id = ?
                """,
                (
                    graph.model_dump_json(),
                    validation.model_dump_json(),
                    "complete",
                    utc_now(),
                    job_id,
                ),
            )

    def get_graph(self, job_id: str) -> ClaimKnowledgeGraph | None:
        with self.connect() as connection:
            row = connection.execute("SELECT graph_json FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not row or not row["graph_json"]:
            return None
        return ClaimKnowledgeGraph.model_validate_json(row["graph_json"])

    def get_validation(self, job_id: str) -> ValidationSummary | None:
        with self.connect() as connection:
            row = connection.execute("SELECT validation_json FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not row or not row["validation_json"]:
            return None
        return ValidationSummary.model_validate_json(row["validation_json"])

    def get_source_preview(self, document_id: str, source_id: str) -> SourcePreview | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT s.id AS source_id, s.document_id, s.citation_text, s.document_link,
                       d.title, d.content_uri
                  FROM sources s
                  JOIN documents d ON d.id = s.document_id
                 WHERE s.document_id = ? AND s.id = ?
                """,
                (document_id, source_id),
            ).fetchone()
        if not row:
            return None
        return SourcePreview(
            source_id=row["source_id"],
            document_id=row["document_id"],
            title=row["title"],
            citation_text=row["citation_text"],
            document_link=row["document_link"],
            document_preview_url=row["content_uri"],
        )

    @staticmethod
    def _row_to_stored_document(row: sqlite3.Row) -> StoredDocument:
        return StoredDocument(
            id=row["id"],
            summary=row["summary"],
            document_type=row["document_type"],
            title=row["title"],
            document_date=row["document_date"],
            content_uri=row["content_uri"],
            filename=row["filename"],
            file_type=row["file_type"],
            status=row["status"],
            pages=row["pages"],
            sort_group=row["sort_group"],
            error=row["error"],
            stored_path=row["stored_path"],
        )


def graph_response_payload(graph: ClaimKnowledgeGraph, validation: ValidationSummary) -> dict:
    payload = json.loads(graph.model_dump_json())
    payload["validation"] = json.loads(validation.model_dump_json())
    return payload
