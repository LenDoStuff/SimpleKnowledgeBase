import json

import pytest
from claim_file_splitter.customization import CategoryConfig

from backend.app.config import Settings, category_label, load_document_categories


def test_load_document_categories_from_config_file(tmp_path):
    path = tmp_path / "categories.json"
    path.write_text(
        json.dumps(
            {
                "categories": [
                    {
                        "name": "custom_claim_forms",
                        "filename_prefix": "custom_claim_form",
                        "description": "Custom claim form category.",
                    },
                    {
                        "name": "other",
                        "filename_prefix": "document",
                        "description": "Other documents.",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    categories = load_document_categories(path)

    assert categories[0].name == "custom_claim_forms"
    assert categories[0] == CategoryConfig(
        name="custom_claim_forms",
        filename_prefix="custom_claim_form",
        description="Custom claim form category.",
    )


def test_document_categories_reject_extra_fields(tmp_path):
    path = tmp_path / "categories.json"
    path.write_text(
        json.dumps(
            {
                "categories": [
                    {
                        "name": "other",
                        "filename_prefix": "document",
                        "description": "Other documents.",
                        "sort_order": 90,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported fields"):
        load_document_categories(path)


def test_document_categories_reject_duplicate_names(tmp_path):
    path = tmp_path / "categories.json"
    path.write_text(
        json.dumps(
            {
                "categories": [
                    {"name": "other", "filename_prefix": "document", "description": "Other documents."},
                    {"name": "other", "filename_prefix": "other_document", "description": "Duplicate."},
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unique"):
        load_document_categories(path)


def test_category_label_is_derived_from_name():
    assert category_label("claim_forms") == "Claim Forms"
    assert category_label("policy_documents") == "Policy Documents"


def test_settings_rejects_default_category_missing_from_config(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        document_categories=(
            CategoryConfig(
                name="other",
                filename_prefix="document",
                description="Other documents.",
            ),
        ),
        pdf_splitter_default_category="missing",
    )

    with pytest.raises(ValueError, match="DEFAULT_CATEGORY"):
        _ = settings.pdf_splitter_default_document_type


def test_settings_uses_config_order_for_document_sorting(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        document_categories=(
            CategoryConfig(name="reports", filename_prefix="report", description="Reports."),
            CategoryConfig(name="other", filename_prefix="document", description="Other documents."),
        ),
    )

    assert settings.document_sort_order == {"reports": 0, "other": 1}
    assert settings.document_sort_group("reports") == "Reports"
