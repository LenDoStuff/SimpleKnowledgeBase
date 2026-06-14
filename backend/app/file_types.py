from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".docx": "docx",
    ".xlsx": "xlsx",
}

LEGACY_EXTENSIONS = {".doc", ".xls"}


@dataclass(frozen=True)
class FileInspection:
    extension: str
    file_type: str


def inspect_filename(filename: str) -> FileInspection:
    extension = Path(filename).suffix.lower()
    if extension in LEGACY_EXTENSIONS:
        raise ValueError(f"Legacy {extension} files are not supported in v1. Convert to DOCX/XLSX first.")
    if extension not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(f"Unsupported file type {extension or '<none>'}. Supported types: {supported}.")
    return FileInspection(extension=extension, file_type=SUPPORTED_EXTENSIONS[extension])


def safe_filename(filename: str) -> str:
    stem = Path(filename).stem.strip() or "claim-file"
    extension = Path(filename).suffix.lower()
    cleaned = []
    for char in stem:
        if char.isalnum() or char in {"-", "_", ".", " "}:
            cleaned.append(char)
        else:
            cleaned.append("_")
    return f"{''.join(cleaned).strip() or 'claim-file'}{extension}"


def unique_storage_name(filename: str, used_names: set[str]) -> str:
    candidate = safe_filename(filename)
    if candidate not in used_names:
        used_names.add(candidate)
        return candidate

    path = Path(candidate)
    while True:
        candidate = f"{path.stem}-{uuid4().hex[:8]}{path.suffix}"
        if candidate not in used_names:
            used_names.add(candidate)
            return candidate


def classify_document(filename: str, file_type: str) -> tuple[str, str]:
    name = filename.lower()
    if file_type == "image":
        return "photo", "Photos / Images"
    if "invoice" in name or "bill" in name:
        return "invoice", "Invoices"
    if "report" in name or "inspection" in name or "engineer" in name or "fire" in name:
        return "report", "Reports"
    if file_type == "xlsx":
        return "spreadsheet", "Spreadsheets"
    if "proof" in name or "loss" in name or "claim" in name or "fnol" in name or "notice" in name:
        return "claim_form", "Claim Forms"
    return "other", "Other Documents"

