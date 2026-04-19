"""Tests for image extraction and PDF conversion."""

from pathlib import Path

import pytest
from PIL import Image

from occonvert.images import (
    _safe_filename,
    copy_or_convert_image,
    extract_image_bytes_to_pdf,
    save_image_as_pdf,
)


@pytest.fixture
def png_file(tmp_path):
    """Create a small test PNG file."""
    img = Image.new("RGB", (10, 10), color="red")
    path = tmp_path / "test.png"
    img.save(str(path))
    return path


@pytest.fixture
def jpeg_file(tmp_path):
    """Create a small test JPEG file."""
    img = Image.new("RGB", (10, 10), color="blue")
    path = tmp_path / "test.jpg"
    img.save(str(path))
    return path


@pytest.fixture
def pdf_file(tmp_path):
    """Create a minimal PDF file."""
    path = tmp_path / "test.pdf"
    path.write_bytes(b"%PDF-1.4 minimal test content")
    return path


class TestSaveImageAsPdf:
    def test_png_to_pdf(self, png_file, tmp_path):
        out = tmp_path / "output.pdf"
        save_image_as_pdf(png_file.read_bytes(), out)
        assert out.exists()
        assert out.stat().st_size > 0
        assert out.read_bytes()[:5] == b"%PDF-"

    def test_jpeg_to_pdf(self, jpeg_file, tmp_path):
        out = tmp_path / "output.pdf"
        save_image_as_pdf(jpeg_file.read_bytes(), out)
        assert out.exists()
        assert out.read_bytes()[:5] == b"%PDF-"


class TestCopyOrConvertImage:
    def test_png_converted_to_pdf(self, png_file, tmp_path):
        dest = tmp_path / "dest"
        name = copy_or_convert_image(png_file, dest)
        assert name.endswith(".pdf")
        assert (dest / name).exists()

    def test_jpeg_converted_to_pdf(self, jpeg_file, tmp_path):
        dest = tmp_path / "dest"
        name = copy_or_convert_image(jpeg_file, dest)
        assert name.endswith(".pdf")
        assert (dest / name).exists()

    def test_pdf_copied_directly(self, pdf_file, tmp_path):
        dest = tmp_path / "dest"
        name = copy_or_convert_image(pdf_file, dest)
        assert name == "test.pdf"
        assert (dest / name).exists()
        assert (dest / name).read_bytes() == pdf_file.read_bytes()

    def test_creates_dest_dir(self, png_file, tmp_path):
        dest = tmp_path / "new" / "subdir"
        assert not dest.exists()
        copy_or_convert_image(png_file, dest)
        assert dest.exists()

    def test_same_stem_does_not_collide(self, tmp_path):
        """Multiple images sharing a stem must not overwrite each other.

        Mirrors the pptx parser, which hands every slide image the same hint
        ``slide_image.png`` from separate temp dirs.
        """
        dest = tmp_path / "dest"
        names = []
        for color in ("red", "green", "blue"):
            sub = tmp_path / f"src_{color}"
            sub.mkdir()
            img = Image.new("RGB", (4, 4), color=color)
            path = sub / "slide_image.png"
            img.save(str(path))
            names.append(copy_or_convert_image(path, dest))
        assert len(set(names)) == 3  # no collisions
        for name in names:
            assert (dest / name).exists()


class TestExtractImageBytesToPdf:
    def test_png_bytes(self, png_file, tmp_path):
        dest = tmp_path / "dest"
        name = extract_image_bytes_to_pdf(png_file.read_bytes(), "myimage.png", dest)
        assert name.endswith(".pdf")
        assert (dest / name).exists()

    def test_pdf_bytes_passthrough(self, tmp_path):
        dest = tmp_path / "dest"
        pdf_data = b"%PDF-1.4 some content here"
        name = extract_image_bytes_to_pdf(pdf_data, "doc.pdf", dest)
        assert name == "doc.pdf"
        assert (dest / name).read_bytes() == pdf_data

    def test_name_sanitization(self, png_file, tmp_path):
        dest = tmp_path / "dest"
        name = extract_image_bytes_to_pdf(
            png_file.read_bytes(), "my image (1).png", dest
        )
        # Should have no spaces or parens
        assert " " not in name
        assert "(" not in name


class TestSafeFilename:
    def test_alphanumeric_unchanged(self):
        assert _safe_filename("hello123") == "hello123"

    def test_removes_spaces(self):
        assert _safe_filename("hello world") == "helloworld"

    def test_removes_special_chars(self):
        assert _safe_filename("img (1)-copy") == "img1copy"

    def test_empty_fallback(self):
        assert _safe_filename("!!!") == "image"

    def test_empty_string(self):
        assert _safe_filename("") == "image"
