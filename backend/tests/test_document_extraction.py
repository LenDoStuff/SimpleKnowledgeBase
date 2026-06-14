import pytest

from backend.app.document_extraction import DocumentBatchExtraction, consolidate_document_batches
from backend.app.pdf_images import page_batches


@pytest.mark.parametrize(
    ("page_count", "expected"),
    [
        (1, [(1, 1)]),
        (5, [(1, 5)]),
        (6, [(1, 5), (6, 6)]),
        (10, [(1, 5), (6, 10)]),
        (11, [(1, 5), (6, 10), (11, 11)]),
    ],
)
def test_pdf_page_batches_use_five_page_ranges(page_count, expected):
    assert page_batches(page_count, 5) == expected


def test_empty_document_extraction_fails_clearly():
    with pytest.raises(RuntimeError, match="no structured content"):
        consolidate_document_batches(
            document_id="doc-1",
            source_id="src-1",
            batches=[DocumentBatchExtraction(page_start=1, page_end=1)],
        )
