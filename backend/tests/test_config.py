import json

import pytest

from backend.app.config import DocumentCategory, Settings, load_document_categories


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
                        "document_type": "claim_form",
                        "sort_group": "Custom Claim Forms",
                        "sort_order": 5,
                    },
                    {
                        "name": "other",
                        "filename_prefix": "document",
                        "description": "Other documents.",
                        "document_type": "other",
                        "sort_group": "Other Documents",
                        "sort_order": 90,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    categories = load_document_categories(path)

    assert categories[0].name == "custom_claim_forms"
    assert categories[0].to_splitter_category() == {
        "name": "custom_claim_forms",
        "filename_prefix": "custom_claim_form",
        "description": "Custom claim form category.",
    }


def test_settings_rejects_default_category_missing_from_config(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        document_categories=(
            DocumentCategory(
                name="other",
                filename_prefix="document",
                description="Other documents.",
                document_type="other",
                sort_group="Other Documents",
                sort_order=90,
            ),
        ),
        pdf_splitter_default_category="missing",
    )

    with pytest.raises(ValueError, match="DEFAULT_CATEGORY"):
        _ = settings.pdf_splitter_default_document_type
