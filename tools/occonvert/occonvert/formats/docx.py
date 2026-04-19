"""Word (.docx) parser — converts Word documents to the Chapter IR."""

from __future__ import annotations

import tempfile
from pathlib import Path

from lxml import etree

from ..model import (
    Author,
    Chapter,
    CodeBlock,
    Equation,
    Figure,
    InlineRun,
    ListBlock,
    ListItem,
    Paragraph,
    Section,
    Table,
    TableCell,
)

# XML namespaces used in .docx
_WP = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_M = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def parse_docx(path: Path) -> Chapter:
    """Parse a .docx file into a Chapter IR."""
    from docx import Document as DocxDocument

    doc = DocxDocument(str(path))
    chapter = Chapter()

    # We need to walk body children in document order to interleave
    # paragraphs and tables correctly.
    body = doc.element.body
    flat_items = _walk_body(body, doc, chapter)

    # Organize into sections
    chapter.sections = _nest_sections(flat_items)

    # Extract bibliography from Word's citation manager if present
    _extract_bibliography(path, chapter)

    return chapter


# ---------------------------------------------------------------------------
# Body walker — produces a flat list of (heading|block) items
# ---------------------------------------------------------------------------

# Sentinel to mark section boundaries
class _Heading:
    def __init__(self, title: str, level: int):
        self.title = title
        self.level = level


def _walk_body(body, doc, chapter: Chapter) -> list:
    """Walk XML body children and produce headings + blocks in order."""
    items: list = []
    pending_list_items: list[tuple[str, bool]] = []  # (style, ordered) groups

    for child in body:
        tag = _local_tag(child)

        if tag == "p":
            style = _para_style(child)

            # Flush pending list if style changed away from list
            is_list = style in (
                "ListBullet", "ListBullet1", "ListBullet2", "ListBullet3",
                "ListNumber", "ListNumber1", "ListNumber2", "ListNumber3",
                "List Bullet", "List Bullet 2", "List Bullet 3",
                "List Number", "List Number 2", "List Number 3",
            )
            # Flush pending list if style changed away from list,
            # or if the list type (ordered vs unordered) changed
            if pending_list_items:
                if not is_list:
                    items.append(_flush_list(pending_list_items, child, doc))
                    pending_list_items = []
                elif is_list:
                    new_ordered = "Number" in style
                    prev_ordered = pending_list_items[-1][1]
                    if new_ordered != prev_ordered:
                        items.append(_flush_list(pending_list_items, child, doc))
                        pending_list_items = []

            # Title paragraph
            if style == "Title":
                chapter.title = _all_text(child)
                continue

            # Subtitle — treat as author info
            if style == "Subtitle":
                _parse_subtitle_author(chapter, _all_text(child))
                continue

            # Headings
            if style.startswith("Heading") or style.startswith("heading"):
                level = _heading_level(style)
                title = _all_text(child)
                if title.strip():
                    if pending_list_items:
                        items.append(_flush_list(pending_list_items, child, doc))
                        pending_list_items = []
                    items.append(_Heading(title=title, level=level))
                continue

            # List items — accumulate
            if is_list:
                ordered = "Number" in style
                text_runs = _parse_runs(child, doc)
                pending_list_items.append((text_runs, ordered))
                continue

            # Check for OMML equations
            omaths = child.findall(f".//{{{_M}}}oMath")
            if omaths and not _has_text_besides_math(child):
                # Display equation (entire paragraph is math)
                from ..equations import omml_to_latex
                latex_parts = [omml_to_latex(om) for om in omaths]
                items.append(Equation(latex=" ".join(latex_parts), display=True))
                continue

            # Check for inline images
            blips = child.findall(f".//{{{_A}}}blip")
            if blips and not _all_text(child).strip():
                # Image-only paragraph
                for blip in blips:
                    fig = _extract_image(blip, doc, chapter)
                    if fig:
                        items.append(fig)
                continue

            # Normal paragraph — parse runs
            runs = _parse_runs(child, doc)
            if runs:
                # Merge inline math from OMML
                if omaths:
                    runs = _merge_omml_inline(child, doc)
                items.append(Paragraph(runs=runs))

        elif tag == "tbl":
            if pending_list_items:
                items.append(_flush_list(pending_list_items, child, doc))
                pending_list_items = []
            table = _parse_table(child)
            if table:
                items.append(table)

    # Flush trailing list
    if pending_list_items:
        items.append(_flush_list(pending_list_items, body, doc))

    return items


# ---------------------------------------------------------------------------
# Run parsing
# ---------------------------------------------------------------------------


def _parse_runs(para_el, doc) -> list[InlineRun]:
    """Extract InlineRun objects from a paragraph element's w:r children."""
    runs: list[InlineRun] = []

    for child in para_el:
        ctag = _local_tag(child)

        if ctag == "hyperlink":
            href = _hyperlink_url(child, doc)
            for r_el in child.findall(f"{{{_WP}}}r"):
                run = _make_run(r_el)
                if run:
                    run.href = href
                    runs.append(run)
            continue

        if ctag == "r":
            run = _make_run(child)
            if run:
                runs.append(run)
            continue

        # Inline OMML math within a mixed paragraph
        if ctag == "oMath":
            from ..equations import omml_to_latex
            latex = omml_to_latex(child)
            if latex.strip():
                runs.append(InlineRun(text=latex.strip(), math=True))

    return runs


def _make_run(r_el) -> InlineRun | None:
    """Create an InlineRun from a w:r element."""
    texts = []
    for t in r_el.iter(f"{{{_WP}}}t"):
        texts.append(t.text or "")

    text = "".join(texts)
    if not text:
        return None

    # Read run properties
    rpr = r_el.find(f"{{{_WP}}}rPr")
    bold = False
    italic = False
    superscript = False
    subscript = False
    code = False

    if rpr is not None:
        bold = rpr.find(f"{{{_WP}}}b") is not None
        italic = rpr.find(f"{{{_WP}}}i") is not None

        vert_align = rpr.find(f"{{{_WP}}}vertAlign")
        if vert_align is not None:
            val = vert_align.get(f"{{{_WP}}}val", "")
            superscript = val == "superscript"
            subscript = val == "subscript"

        # Detect monospace fonts as code
        rfonts = rpr.find(f"{{{_WP}}}rFonts")
        if rfonts is not None:
            for attr in (f"{{{_WP}}}ascii", f"{{{_WP}}}hAnsi", f"{{{_WP}}}cs"):
                font_name = rfonts.get(attr, "")
                if font_name.lower() in ("courier new", "consolas", "menlo", "monaco", "monospace"):
                    code = True
                    break

    return InlineRun(
        text=text,
        bold=bold,
        italic=italic,
        superscript=superscript,
        subscript=subscript,
        code=code,
    )


def _merge_omml_inline(para_el, doc) -> list[InlineRun]:
    """Parse a paragraph that mixes regular text and inline OMML math."""
    from ..equations import omml_to_latex

    runs: list[InlineRun] = []
    for child in para_el:
        ctag = _local_tag(child)
        if ctag == "r":
            run = _make_run(child)
            if run:
                runs.append(run)
        elif ctag == "oMath":
            latex = omml_to_latex(child)
            if latex.strip():
                runs.append(InlineRun(text=latex.strip(), math=True))
        elif ctag == "hyperlink":
            href = _hyperlink_url(child, doc)
            for r_el in child.findall(f"{{{_WP}}}r"):
                run = _make_run(r_el)
                if run:
                    run.href = href
                    runs.append(run)
    return runs


# ---------------------------------------------------------------------------
# List handling
# ---------------------------------------------------------------------------


def _flush_list(pending: list[tuple[list[InlineRun], bool]], context_el, doc) -> ListBlock:
    """Convert accumulated list-item runs into a ListBlock."""
    if not pending:
        return ListBlock()

    # Determine if ordered from the first item
    ordered = pending[0][1]
    items = [ListItem(runs=runs) for runs, _ in pending]
    pending.clear()
    return ListBlock(ordered=ordered, items=items)


# ---------------------------------------------------------------------------
# Table handling
# ---------------------------------------------------------------------------


def _parse_table(tbl_el) -> Table | None:
    """Parse a w:tbl element into a Table IR object."""
    rows_data: list[list[str]] = []

    for tr in tbl_el.findall(f"{{{_WP}}}tr"):
        row: list[str] = []
        for tc in tr.findall(f"{{{_WP}}}tc"):
            cell_text = _all_text(tc)
            row.append(cell_text)
        rows_data.append(row)

    if not rows_data:
        return None

    # First row is headers
    headers = [TableCell(text=c) for c in rows_data[0]]
    body_rows = [[TableCell(text=c) for c in r] for r in rows_data[1:]]

    return Table(headers=headers, rows=body_rows)


# ---------------------------------------------------------------------------
# Image handling
# ---------------------------------------------------------------------------


def _extract_image(blip_el, doc, chapter: Chapter) -> Figure | None:
    """Extract an image from a blip element and register it."""
    embed_id = blip_el.get(f"{{{_R}}}embed")
    if not embed_id:
        return None

    try:
        rel = doc.part.rels[embed_id]
    except KeyError:
        return None

    target = rel.target_ref  # e.g. "media/image1.png"
    blob = rel.target_part.blob
    name = Path(target).name

    # Write to a temp file so the converter can relocate it later
    tmp_dir = Path(tempfile.mkdtemp(prefix="occonvert_"))
    tmp_path = tmp_dir / name
    tmp_path.write_bytes(blob)

    fig = Figure(
        source_path=str(tmp_path),
        output_filename="",
        caption="",
        alt_text=name,
    )
    chapter.images.append(fig)
    return fig


# ---------------------------------------------------------------------------
# Bibliography
# ---------------------------------------------------------------------------


def _extract_bibliography(docx_path: Path, chapter: Chapter) -> None:
    """Try to extract bibliography entries from Word's customXml."""
    import zipfile

    try:
        with zipfile.ZipFile(docx_path) as z:
            for name in z.namelist():
                if name.startswith("customXml/item") and name.endswith(".xml"):
                    xml_data = z.read(name)
                    if b"bibliography" in xml_data.lower() or b"Sources" in xml_data:
                        from ..bibtex import entries_from_docx_xml
                        entries = entries_from_docx_xml(xml_data)
                        chapter.bibliography.extend(entries)
    except (zipfile.BadZipFile, KeyError):
        pass


# ---------------------------------------------------------------------------
# Author parsing
# ---------------------------------------------------------------------------


def _parse_subtitle_author(chapter: Chapter, text: str) -> None:
    """Parse a subtitle line like 'Jane Smith, University' into an Author."""
    if not text.strip():
        return
    parts = [p.strip() for p in text.split(",", 1)]
    name = parts[0]
    institution = parts[1] if len(parts) > 1 else ""

    name_parts = name.rsplit(" ", 1)
    first = name_parts[0] if len(name_parts) > 1 else name
    last = name_parts[1] if len(name_parts) > 1 else ""

    chapter.authors.append(Author(first=first, last=last, institution=institution))


# ---------------------------------------------------------------------------
# Section nesting (reused logic from markdown parser)
# ---------------------------------------------------------------------------


def _nest_sections(items: list) -> list[Section]:
    """Organize a flat list of headings and blocks into nested sections."""
    flat_sections: list[Section] = []
    current_blocks: list = []

    for item in items:
        if isinstance(item, _Heading):
            if current_blocks:
                if flat_sections:
                    flat_sections[-1].content.extend(current_blocks)
                else:
                    flat_sections.append(Section(title="", level=0, content=current_blocks))
                current_blocks = []
            flat_sections.append(Section(title=item.title, level=item.level))
        else:
            current_blocks.append(item)

    if current_blocks:
        if flat_sections:
            flat_sections[-1].content.extend(current_blocks)
        else:
            flat_sections.append(Section(title="Introduction", level=1, content=current_blocks))

    if not flat_sections:
        return []

    # Handle preamble (level 0)
    preamble_content = []
    real = []
    for s in flat_sections:
        if s.level <= 0:
            preamble_content.extend(s.content)
        else:
            real.append(s)

    if preamble_content and real:
        real[0].content = preamble_content + real[0].content
    elif preamble_content and not real:
        real.append(Section(title="Introduction", level=1, content=preamble_content))

    if not real:
        return []

    # Normalize levels
    min_level = min(s.level for s in real)
    result: list[Section] = []
    stack: list[Section] = []

    for s in real:
        s.level = s.level - min_level + 1
        if s.level > 3:
            s.level = 3

        while stack and stack[-1].level >= s.level:
            stack.pop()

        if stack:
            stack[-1].children.append(s)
        else:
            result.append(s)

        stack.append(s)

    return result


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------


def _local_tag(el) -> str:
    """Strip namespace from element tag."""
    tag = el.tag
    return tag.split("}", 1)[1] if "}" in tag else tag


def _para_style(para_el) -> str:
    """Get the style name from a w:p element."""
    ppr = para_el.find(f"{{{_WP}}}pPr")
    if ppr is not None:
        pstyle = ppr.find(f"{{{_WP}}}pStyle")
        if pstyle is not None:
            return pstyle.get(f"{{{_WP}}}val", "Normal")
    return "Normal"


def _all_text(el) -> str:
    """Get all w:t text content from an element."""
    texts = [t.text or "" for t in el.iter(f"{{{_WP}}}t")]
    return "".join(texts)


def _heading_level(style: str) -> int:
    """Extract heading level from style name like 'Heading1' or 'Heading 2'."""
    for ch in reversed(style):
        if ch.isdigit():
            return int(ch)
    return 1


def _has_text_besides_math(para_el) -> bool:
    """Check if a paragraph has regular text content besides OMML math."""
    for child in para_el:
        ctag = _local_tag(child)
        if ctag == "r":
            texts = [t.text or "" for t in child.iter(f"{{{_WP}}}t")]
            text = "".join(texts).strip()
            if text:
                return True
    return False


def _hyperlink_url(hyperlink_el, doc) -> str:
    """Get the URL from a w:hyperlink element."""
    r_id = hyperlink_el.get(f"{{{_R}}}id")
    if r_id:
        try:
            rel = doc.part.rels[r_id]
            return rel.target_ref
        except KeyError:
            pass
    return ""
