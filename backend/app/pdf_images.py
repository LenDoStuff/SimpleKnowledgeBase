from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path


@dataclass(frozen=True)
class RenderedPageImage:
    page_number: int
    mime_type: str
    data_url: str


def page_batches(page_count: int, batch_size: int) -> list[tuple[int, int]]:
    if page_count < 1:
        raise ValueError("page_count must be at least 1.")
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1.")
    return [
        (start, min(start + batch_size - 1, page_count))
        for start in range(1, page_count + 1, batch_size)
    ]


def render_pdf_pages_as_images(
    pdf_path: Path,
    *,
    page_start: int,
    page_end: int,
    dpi: int,
    image_format: str,
    image_quality: int,
) -> list[RenderedPageImage]:
    import pypdfium2 as pdfium

    normalized_format = _image_format(image_format)
    mime_type = f"image/{normalized_format}"
    scale = dpi / 72
    images = []

    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        page_count = len(pdf)
        if page_start < 1 or page_end < page_start or page_end > page_count:
            raise ValueError(f"Invalid PDF page range {page_start}-{page_end} for {pdf_path.name}.")

        for page_number in range(page_start, page_end + 1):
            page = pdf[page_number - 1]
            try:
                bitmap = page.render(scale=scale)
                try:
                    pil_image = bitmap.to_pil()
                    if normalized_format == "jpeg" and pil_image.mode != "RGB":
                        pil_image = pil_image.convert("RGB")
                    buffer = BytesIO()
                    save_kwargs = {"format": "JPEG" if normalized_format == "jpeg" else "PNG"}
                    if normalized_format == "jpeg":
                        save_kwargs["quality"] = image_quality
                    pil_image.save(buffer, **save_kwargs)
                    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
                    images.append(
                        RenderedPageImage(
                            page_number=page_number,
                            mime_type=mime_type,
                            data_url=f"data:{mime_type};base64,{encoded}",
                        )
                    )
                finally:
                    _close_if_possible(bitmap)
            finally:
                _close_if_possible(page)
    finally:
        _close_if_possible(pdf)

    return images


def _image_format(value: str) -> str:
    normalized = value.strip().lower()
    if normalized == "jpg":
        return "jpeg"
    if normalized not in {"jpeg", "png"}:
        raise ValueError("PDF image render format must be jpeg or png.")
    return normalized


def _close_if_possible(value: object) -> None:
    close = getattr(value, "close", None)
    if callable(close):
        close()
