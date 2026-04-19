"""Main orchestrator: detects input format, runs the parser, emits output."""

from __future__ import annotations

from pathlib import Path

from .model import Chapter, Section
from .template import generate_bib, generate_chapter_json, generate_chapter_tex
from .utils import clean_text

SUPPORTED_EXTENSIONS = {".md", ".docx", ".pptx"}


def _sanitize(chapter: Chapter) -> None:
    """Strip control chars from title, author names, and section titles."""
    chapter.title = clean_text(chapter.title)
    for a in chapter.authors:
        a.first = clean_text(a.first)
        a.last = clean_text(a.last)
    _sanitize_sections(chapter.sections)


def _sanitize_sections(sections: list[Section]) -> None:
    for s in sections:
        s.title = clean_text(s.title)
        _sanitize_sections(s.children)


def convert(
    input_path: Path,
    output_dir: Path,
    chabbr: str | None = None,
    title: str | None = None,
    metadata: dict | None = None,
    chapter: Chapter | None = None,
) -> Path:
    """Convert a source document to OC LaTeX format.

    ``metadata`` (if given) overrides fields in chapter.json. ``chapter`` lets
    callers pass a pre-parsed Chapter IR (e.g. the GUI parses once to populate
    the form, then reuses it on Convert). Returns the path to MyChapter.tex.
    """
    ext = input_path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported format '{ext}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if chapter is None:
        chapter = _parse(input_path, ext)
        _sanitize(chapter)

    # Override title if provided on the command line
    if title:
        chapter.title = title

    # Build the output directory tree
    chapter_dir = output_dir / "chapter"
    pdf_dir = chapter_dir / "pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    # Move extracted images into chapter/pdf/
    _relocate_images(chapter, pdf_dir)

    # Generate output files
    tex_path = chapter_dir / "MyChapter.tex"
    tex_path.write_text(generate_chapter_tex(chapter, chabbr), encoding="utf-8")

    json_path = chapter_dir / "chapter.json"
    json_path.write_text(
        generate_chapter_json(chapter, chabbr, metadata=metadata),
        encoding="utf-8",
    )

    bib_path = chapter_dir / "chaptercitations.bib"
    bib_path.write_text(generate_bib(chapter.bibliography), encoding="utf-8")

    return tex_path


def parse_only(input_path: Path) -> Chapter:
    """Parse an input file without writing output. Used by the GUI for pre-population."""
    ext = input_path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported format '{ext}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    chapter = _parse(input_path, ext)
    _sanitize(chapter)
    return chapter


def _parse(input_path: Path, ext: str) -> Chapter:
    """Dispatch to the correct format-specific parser."""
    if ext == ".md":
        from .formats.markdown import parse_markdown

        return parse_markdown(input_path)
    elif ext == ".docx":
        from .formats.docx import parse_docx

        return parse_docx(input_path)
    elif ext == ".pptx":
        from .formats.pptx import parse_pptx

        return parse_pptx(input_path)
    else:
        raise ValueError(f"No parser for '{ext}'")


def _relocate_images(chapter: Chapter, pdf_dir: Path) -> None:
    """Move/convert images referenced by the chapter into pdf_dir."""
    from .images import copy_or_convert_image

    for fig in chapter.images:
        if fig.source_path and Path(fig.source_path).exists():
            out_name = copy_or_convert_image(Path(fig.source_path), pdf_dir)
            fig.output_filename = out_name
