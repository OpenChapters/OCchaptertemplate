"""Image extraction and conversion to PDF for OC chapter figures."""

from __future__ import annotations

import io
import re
import shutil
from pathlib import Path


def save_image_as_pdf(image_data: bytes, output_path: Path) -> None:
    """Convert raw image bytes (PNG/JPEG) to a single-page PDF."""
    import img2pdf

    pdf_bytes = img2pdf.convert(image_data)
    output_path.write_bytes(pdf_bytes)


def copy_or_convert_image(source: Path, dest_dir: Path) -> str:
    """Copy an image to dest_dir, converting to PDF if needed.

    Returns the output filename (always .pdf).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_filename(source.stem)
    out = _unique_path(dest_dir, stem, ".pdf")

    if source.suffix.lower() == ".pdf":
        shutil.copy2(source, out)
        return out.name

    save_image_as_pdf(source.read_bytes(), out)
    return out.name


def extract_image_bytes_to_pdf(
    data: bytes, name_hint: str, dest_dir: Path
) -> str:
    """Write raw image bytes as a PDF into dest_dir.

    Returns the output filename.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_filename(Path(name_hint).stem)
    out = _unique_path(dest_dir, stem, ".pdf")

    if data[:5] == b"%PDF-":
        out.write_bytes(data)
        return out.name

    save_image_as_pdf(data, out)
    return out.name


def _safe_filename(name: str) -> str:
    """Sanitize a filename stem to be safe and LaTeX-friendly."""
    name = re.sub(r"[^a-zA-Z0-9]", "", name)
    return name or "image"


def _unique_path(dest_dir: Path, stem: str, suffix: str) -> Path:
    """Return dest_dir/stem+suffix, with a numeric tail if that name is taken.

    Without this, parsers that hand us identical stems (e.g. pptx's
    ``slide_image``, or repeated docx media names) overwrite each other.
    """
    candidate = dest_dir / f"{stem}{suffix}"
    if not candidate.exists():
        return candidate
    i = 2
    while True:
        candidate = dest_dir / f"{stem}{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1
