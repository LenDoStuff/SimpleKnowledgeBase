from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from claim_file_splitter.customization import CategoryConfig


REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / ".env"
DEFAULT_DOCUMENT_CATEGORIES_PATH = REPO_ROOT / "config" / "document_categories.json"
DOCUMENT_CATEGORY_FIELDS = {"name", "filename_prefix", "description"}


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file(ENV_FILE)


def _env_path(name: str, default: Path) -> Path:
    raw = os.getenv(name)
    path = Path(raw).expanduser() if raw else default
    return path if path.is_absolute() else REPO_ROOT / path


def load_document_categories(path: Path) -> tuple[CategoryConfig, ...]:
    if not path.exists():
        raise ValueError(f"Document category config not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("categories") if isinstance(payload, dict) else payload
    if not isinstance(rows, list) or not rows:
        raise ValueError("Document category config must contain a non-empty categories list.")

    categories = tuple(_category_from_row(row, index) for index, row in enumerate(rows, start=1))
    names = [category.name for category in categories]
    if len(set(names)) != len(names):
        raise ValueError("Document category names must be unique.")
    if "other" not in names:
        raise ValueError("Document category config must include the 'other' category.")
    return categories


def _category_from_row(row: Any, index: int) -> CategoryConfig:
    if not isinstance(row, dict):
        raise ValueError(f"Document category #{index} must be an object.")
    keys = set(row)
    missing = sorted(DOCUMENT_CATEGORY_FIELDS - keys)
    if missing:
        raise ValueError(f"Document category #{index} is missing: {', '.join(missing)}.")
    extra = sorted(keys - DOCUMENT_CATEGORY_FIELDS)
    if extra:
        raise ValueError(f"Document category #{index} has unsupported fields: {', '.join(extra)}.")
    try:
        return CategoryConfig.model_validate(row)
    except ValueError as exc:
        raise ValueError(f"Document category #{index} is invalid: {exc}") from exc


def category_label(category_name: str) -> str:
    return category_name.replace("_", " ").title()


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path(os.getenv("CLAIM_STRUCTURER_DATA_DIR", REPO_ROOT / ".claim_structurer_data"))
    max_upload_bytes: int = int(os.getenv("CLAIM_STRUCTURER_MAX_UPLOAD_BYTES", str(200 * 1024 * 1024)))
    extraction_mode: str = os.getenv("CLAIM_STRUCTURER_EXTRACTION_MODE", "azure")
    foundry_project_endpoint: str | None = os.getenv("FOUNDRY_PROJECT_ENDPOINT")
    foundry_model_name: str | None = os.getenv("FOUNDRY_MODEL_NAME")
    pdf_splitter_mode: str = os.getenv("CLAIM_STRUCTURER_PDF_SPLITTER_MODE", "required")
    pdf_splitter_default_category: str = os.getenv("CLAIM_STRUCTURER_PDF_SPLITTER_DEFAULT_CATEGORY", "other")
    document_extraction_page_batch_size: int = int(
        os.getenv("CLAIM_STRUCTURER_DOCUMENT_EXTRACTION_PAGE_BATCH_SIZE", "5")
    )
    document_extraction_render_dpi: int = int(os.getenv("CLAIM_STRUCTURER_DOCUMENT_EXTRACTION_RENDER_DPI", "160"))
    document_extraction_image_format: str = os.getenv("CLAIM_STRUCTURER_DOCUMENT_EXTRACTION_IMAGE_FORMAT", "jpeg")
    document_extraction_image_quality: int = int(
        os.getenv("CLAIM_STRUCTURER_DOCUMENT_EXTRACTION_IMAGE_QUALITY", "85")
    )
    document_categories_path: Path = _env_path(
        "CLAIM_STRUCTURER_DOCUMENT_CATEGORIES_PATH",
        DEFAULT_DOCUMENT_CATEGORIES_PATH,
    )
    document_categories: tuple[CategoryConfig, ...] = field(default_factory=tuple)
    azure_ai_project_endpoint: str | None = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
    azure_openai_deployment: str | None = os.getenv("AZURE_OPENAI_DEPLOYMENT")

    def __post_init__(self) -> None:
        if not self.document_categories:
            object.__setattr__(
                self,
                "document_categories",
                load_document_categories(self.document_categories_path),
            )

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "claim_structurer.sqlite3"

    @property
    def azure_configured(self) -> bool:
        return bool(self.foundry_project_endpoint and self.foundry_model_name)

    @property
    def pdf_splitter_project_endpoint(self) -> str | None:
        return self.foundry_project_endpoint or self.azure_ai_project_endpoint

    @property
    def pdf_splitter_deployment(self) -> str | None:
        return self.foundry_model_name or self.azure_openai_deployment

    @property
    def pdf_splitter_configured(self) -> bool:
        return bool(self.pdf_splitter_project_endpoint and self.pdf_splitter_deployment)

    @property
    def pdf_splitter_default_document_type(self) -> str:
        category_names = {category.name for category in self.document_categories}
        if self.pdf_splitter_default_category not in category_names:
            raise ValueError(
                "CLAIM_STRUCTURER_PDF_SPLITTER_DEFAULT_CATEGORY must match a configured document category."
            )
        return self.pdf_splitter_default_category

    @property
    def document_category_by_name(self) -> dict[str, CategoryConfig]:
        return {category.name: category for category in self.document_categories}

    @property
    def document_sort_order(self) -> dict[str, int]:
        return {category.name: index for index, category in enumerate(self.document_categories)}

    def require_document_category(self, category_name: str) -> str:
        normalized = category_name.strip().lower()
        if normalized not in self.document_category_by_name:
            raise ValueError(f"Unknown configured document category {category_name!r}.")
        return normalized

    def document_sort_group(self, category_name: str) -> str:
        return category_label(self.require_document_category(category_name))


def get_settings() -> Settings:
    return Settings()
