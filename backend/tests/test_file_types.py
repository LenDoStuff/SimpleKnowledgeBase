import pytest

from backend.app.file_types import classify_document, inspect_filename, unique_storage_name


def test_supported_formats_are_classified():
    assert inspect_filename("notice.pdf").file_type == "pdf"
    assert inspect_filename("image.PNG").file_type == "image"
    assert inspect_filename("proof.docx").file_type == "docx"
    assert inspect_filename("values.xlsx").file_type == "xlsx"


def test_legacy_formats_are_rejected():
    with pytest.raises(ValueError, match="Legacy"):
        inspect_filename("legacy.doc")
    with pytest.raises(ValueError, match="Legacy"):
        inspect_filename("legacy.xls")


def test_unsupported_formats_are_rejected():
    with pytest.raises(ValueError, match="Unsupported"):
        inspect_filename("notes.txt")


def test_duplicate_filenames_get_unique_storage_names():
    used = set()
    first = unique_storage_name("Proof of Loss.pdf", used)
    second = unique_storage_name("Proof of Loss.pdf", used)
    assert first != second
    assert first.endswith(".pdf")
    assert second.endswith(".pdf")


def test_document_sorting_groups():
    assert classify_document("First Notice of Loss.pdf", "pdf") == ("claim_form", "Claim Forms")
    assert classify_document("Engineer Report.pdf", "pdf") == ("report", "Reports")
    assert classify_document("IMG_001.png", "image") == ("photo", "Photos / Images")
    assert classify_document("Mitigation Invoice.xlsx", "xlsx") == ("invoice", "Invoices")

