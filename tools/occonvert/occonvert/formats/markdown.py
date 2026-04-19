"""Markdown (.md) parser — converts Markdown to the Chapter IR."""

from __future__ import annotations

import re
from pathlib import Path

from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode

from ..model import (
    Author,
    BibEntry,
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

# Regex patterns for math delimiters
_DISPLAY_MATH_RE = re.compile(r"^\$\$(.*?)\$\$$", re.DOTALL)
_INLINE_MATH_RE = re.compile(r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)")

# YAML front matter
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_markdown(path: Path) -> Chapter:
    """Parse a Markdown file into a Chapter IR."""
    text = path.read_text(encoding="utf-8")
    chapter = Chapter()

    # Extract YAML front matter if present
    text = _extract_frontmatter(text, chapter)

    # Parse with markdown-it-py (tables enabled)
    md = MarkdownIt().enable("table")
    tokens = md.parse(text)

    # Build a flat list of top-level token groups, then organize into sections
    _build_chapter(tokens, chapter, path.parent)

    # If no title was found in front matter, try the first heading
    if not chapter.title and chapter.sections:
        chapter.title = chapter.sections[0].title

    # Extract bibliography from a References/Bibliography section if present
    _extract_bibliography_section(chapter, path.parent)

    return chapter


# ---------------------------------------------------------------------------
# Front matter
# ---------------------------------------------------------------------------


def _extract_frontmatter(text: str, chapter: Chapter) -> str:
    """Parse YAML-like front matter and strip it from the text."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return text

    block = m.group(1)
    for line in block.splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip().strip("\"'")
        if key == "title":
            chapter.title = value
        elif key == "author":
            parts = value.rsplit(" ", 1)
            if len(parts) == 2:
                chapter.authors.append(Author(first=parts[0], last=parts[1]))
            else:
                chapter.authors.append(Author(first=value))
        elif key == "date":
            pass  # not used in OC template

    return text[m.end() :]


# ---------------------------------------------------------------------------
# Main token walker
# ---------------------------------------------------------------------------


def _build_chapter(tokens: list, chapter: Chapter, base_dir: Path) -> None:
    """Walk the flat token list and build sections with content blocks."""
    # We'll collect blocks and organize them into a section hierarchy.
    # Strategy: scan for heading_open tokens to start new sections.
    # Everything before the first heading becomes content of a preamble section
    # (only if non-empty).

    i = 0
    n = len(tokens)
    flat_sections: list[Section] = []
    current_blocks: list = []

    while i < n:
        tok = tokens[i]

        if tok.type == "heading_open":
            level = int(tok.tag[1])  # h1->1, h2->2, etc.
            # Get heading text from the next inline token
            title = ""
            if i + 1 < n and tokens[i + 1].type == "inline":
                title = tokens[i + 1].content
            # Close the previous implicit section
            if current_blocks or flat_sections:
                if not flat_sections:
                    # Preamble content before any heading — attach to a placeholder
                    flat_sections.append(Section(title="", level=0, content=current_blocks))
                else:
                    flat_sections[-1].content.extend(current_blocks)
                current_blocks = []
            flat_sections.append(Section(title=title, level=level))
            i += 3  # skip heading_open, inline, heading_close
            continue

        block = _parse_block(tokens, i, base_dir, chapter)
        if block is not None:
            blk, advance = block
            current_blocks.append(blk)
            i += advance
            continue

        i += 1

    # Attach trailing blocks
    if current_blocks:
        if flat_sections:
            flat_sections[-1].content.extend(current_blocks)
        else:
            flat_sections.append(Section(title="", level=0, content=current_blocks))

    # Nest sections by level
    chapter.sections = _nest_sections(flat_sections)


def _parse_block(tokens: list, i: int, base_dir: Path, chapter: Chapter):
    """Try to parse a block starting at index i.

    Returns (Block, advance) or None.
    """
    tok = tokens[i]

    # Paragraph (may contain math or images)
    if tok.type == "paragraph_open":
        return _parse_paragraph(tokens, i, base_dir, chapter)

    # Fenced code block
    if tok.type == "fence":
        lang = tok.info.strip() if tok.info else ""
        return CodeBlock(code=tok.content.rstrip("\n"), language=lang), 1

    # Bullet list
    if tok.type == "bullet_list_open":
        return _parse_list(tokens, i, ordered=False)

    # Ordered list
    if tok.type == "ordered_list_open":
        return _parse_list(tokens, i, ordered=True)

    # Blockquote — treated as a paragraph with a note
    if tok.type == "blockquote_open":
        return _parse_blockquote(tokens, i, base_dir, chapter)

    # Table
    if tok.type == "table_open":
        return _parse_table(tokens, i)

    return None


# ---------------------------------------------------------------------------
# Paragraph parsing (with math and image detection)
# ---------------------------------------------------------------------------


def _parse_paragraph(tokens: list, i: int, base_dir: Path, chapter: Chapter):
    """Parse a paragraph_open...paragraph_close group."""
    # Find the inline token
    inline_tok = tokens[i + 1] if i + 1 < len(tokens) else None
    if not inline_tok or inline_tok.type != "inline":
        return None

    # Find closing token to compute advance
    advance = 1
    for j in range(i + 1, len(tokens)):
        advance += 1
        if tokens[j].type == "paragraph_close":
            break

    # Check if the entire paragraph is a display math block
    content = inline_tok.content.strip()
    dm = _DISPLAY_MATH_RE.match(content)
    if dm:
        return Equation(latex=dm.group(1).strip(), display=True), advance

    # Check if it's an image-only paragraph
    children = inline_tok.children or []
    if len(children) == 1 and children[0].type == "image":
        img = children[0]
        src = img.attrs.get("src", "") if img.attrs else ""
        alt = img.content or ""
        fig = Figure(source_path=str(base_dir / src) if src else "", alt_text=alt, caption=alt)
        chapter.images.append(fig)
        return fig, advance

    # Regular paragraph — convert inline tokens to runs
    runs = _inline_children_to_runs(children)
    if runs:
        return Paragraph(runs=runs), advance

    return None


def _inline_children_to_runs(children: list) -> list[InlineRun]:
    """Convert markdown-it inline children to InlineRun objects."""
    runs: list[InlineRun] = []
    bold = False
    italic = False
    href = ""

    for tok in children:
        if tok.type == "strong_open":
            bold = True
            continue
        if tok.type == "strong_close":
            bold = False
            continue
        if tok.type == "em_open":
            italic = True
            continue
        if tok.type == "em_close":
            italic = False
            continue
        if tok.type == "link_open":
            href = (tok.attrs or {}).get("href", "")
            continue
        if tok.type == "link_close":
            href = ""
            continue

        if tok.type == "code_inline":
            runs.append(InlineRun(text=tok.content, code=True))
            continue

        if tok.type == "softbreak":
            runs.append(InlineRun(text="\n"))
            continue

        if tok.type == "hardbreak":
            runs.append(InlineRun(text="\n"))
            continue

        if tok.type == "image":
            # Inline image — emit alt text as placeholder
            runs.append(InlineRun(text=f"[image: {tok.content}]", italic=True))
            continue

        if tok.type == "text":
            # Check for inline math within the text
            text = tok.content
            math_runs = _split_inline_math(text, bold=bold, italic=italic, href=href)
            runs.extend(math_runs)
            continue

        # Fallback: emit raw content
        if tok.content:
            runs.append(InlineRun(text=tok.content, bold=bold, italic=italic, href=href))

    return runs


def _split_inline_math(text: str, bold: bool, italic: bool, href: str) -> list[InlineRun]:
    """Split text on inline $...$ math delimiters."""
    runs: list[InlineRun] = []
    last = 0
    for m in _INLINE_MATH_RE.finditer(text):
        # Text before the math
        before = text[last : m.start()]
        if before:
            runs.append(InlineRun(text=before, bold=bold, italic=italic, href=href))
        # The math itself
        runs.append(InlineRun(text=m.group(1), math=True))
        last = m.end()
    # Remaining text after last match
    rest = text[last:]
    if rest:
        runs.append(InlineRun(text=rest, bold=bold, italic=italic, href=href))
    return runs


# ---------------------------------------------------------------------------
# List parsing
# ---------------------------------------------------------------------------


def _parse_list(tokens: list, i: int, ordered: bool):
    """Parse a bullet_list_open or ordered_list_open group."""
    close_type = "ordered_list_close" if ordered else "bullet_list_close"
    items: list[ListItem] = []
    j = i + 1

    while j < len(tokens) and tokens[j].type != close_type:
        if tokens[j].type == "list_item_open":
            item, advance = _parse_list_item(tokens, j)
            items.append(item)
            j += advance
        else:
            j += 1

    # +1 for the close token
    advance = j - i + 1
    return ListBlock(ordered=ordered, items=items), advance


def _parse_list_item(tokens: list, i: int):
    """Parse a single list_item_open...list_item_close group."""
    j = i + 1
    runs: list[InlineRun] = []
    children: list[ListItem] = []
    depth = 1

    while j < len(tokens) and depth > 0:
        tok = tokens[j]
        if tok.type == "list_item_open":
            depth += 1
        elif tok.type == "list_item_close":
            depth -= 1
            if depth == 0:
                j += 1
                break

        # Grab inline content for this item
        if tok.type == "inline" and depth == 1:
            runs = _inline_children_to_runs(tok.children or [])

        # Nested list
        if tok.type in ("bullet_list_open", "ordered_list_open") and depth == 1:
            nested, adv = _parse_list(tokens, j, ordered=(tok.type == "ordered_list_open"))
            for ni in nested.items:
                children.append(ni)
            j += adv
            continue

        j += 1

    return ListItem(runs=runs, children=children), j - i


# ---------------------------------------------------------------------------
# Blockquote parsing
# ---------------------------------------------------------------------------


def _parse_blockquote(tokens: list, i: int, base_dir: Path, chapter: Chapter):
    """Parse blockquote_open...blockquote_close as a regular paragraph."""
    j = i + 1
    runs: list[InlineRun] = []

    while j < len(tokens) and tokens[j].type != "blockquote_close":
        if tokens[j].type == "inline":
            runs.extend(_inline_children_to_runs(tokens[j].children or []))
        j += 1

    advance = j - i + 1
    if runs:
        return Paragraph(runs=runs), advance
    return None


# ---------------------------------------------------------------------------
# Table parsing
# ---------------------------------------------------------------------------


def _parse_table(tokens: list, i: int):
    """Parse table_open...table_close tokens."""
    headers: list[TableCell] = []
    rows: list[list[TableCell]] = []
    j = i + 1
    in_thead = False
    in_tbody = False
    current_row: list[TableCell] = []

    while j < len(tokens) and tokens[j].type != "table_close":
        tok = tokens[j]

        if tok.type == "thead_open":
            in_thead = True
        elif tok.type == "thead_close":
            in_thead = False
        elif tok.type == "tbody_open":
            in_tbody = True
        elif tok.type == "tbody_close":
            in_tbody = False
        elif tok.type == "tr_open":
            current_row = []
        elif tok.type == "tr_close":
            if in_thead:
                headers = current_row
            else:
                rows.append(current_row)
        elif tok.type in ("th_open", "td_open"):
            # Next token should be inline with cell content
            if j + 1 < len(tokens) and tokens[j + 1].type == "inline":
                current_row.append(TableCell(text=tokens[j + 1].content))
                j += 1  # skip the inline token

        j += 1

    advance = j - i + 1
    return Table(headers=headers, rows=rows), advance


# ---------------------------------------------------------------------------
# Section nesting
# ---------------------------------------------------------------------------


def _nest_sections(flat: list[Section]) -> list[Section]:
    """Organize a flat list of sections into a hierarchy by heading level.

    Sections with level <= 0 (preamble) are dropped if empty, otherwise
    their content is prepended to the first real section.
    """
    # Filter out empty preamble sections, merge non-empty preamble content
    preamble_content = []
    real_sections = []
    for s in flat:
        if s.level <= 0:
            preamble_content.extend(s.content)
        else:
            real_sections.append(s)

    if preamble_content and real_sections:
        real_sections[0].content = preamble_content + real_sections[0].content
    elif preamble_content and not real_sections:
        real_sections.append(Section(title="Introduction", level=1, content=preamble_content))

    if not real_sections:
        return []

    # Normalize levels: treat h1 as section (level=1), h2 as subsection, etc.
    # The OC template uses section/subsection/subsubsection (max 3 levels).
    min_level = min(s.level for s in real_sections)

    result: list[Section] = []
    stack: list[Section] = []

    for s in real_sections:
        s.level = s.level - min_level + 1
        if s.level > 3:
            s.level = 3

        # Find parent: pop stack until we find a section with a lower level
        while stack and stack[-1].level >= s.level:
            stack.pop()

        if stack:
            stack[-1].children.append(s)
        else:
            result.append(s)

        stack.append(s)

    return result


# ---------------------------------------------------------------------------
# Bibliography extraction
# ---------------------------------------------------------------------------

_BIB_SECTION_TITLES = {"references", "bibliography", "works cited", "citations"}


def _extract_bibliography_section(chapter: Chapter, base_dir: Path) -> None:
    """Find a References/Bibliography section and convert it to BibEntry objects.

    Also checks for .bib file references in the front matter or content.
    """
    from ..bibtex import entries_from_bib_file, entries_from_markdown_refs

    # Check for a .bib file alongside the markdown
    for bib_path in base_dir.glob("*.bib"):
        entries = entries_from_bib_file(bib_path)
        if entries:
            chapter.bibliography.extend(entries)
            return  # .bib file takes precedence

    # Look for a References/Bibliography section and extract its text
    remaining: list[Section] = []
    for section in chapter.sections:
        if section.title.lower().strip() in _BIB_SECTION_TITLES:
            ref_text = _section_to_plain_text(section)
            entries = entries_from_markdown_refs(ref_text)
            chapter.bibliography.extend(entries)
        else:
            # Also check children
            kept_children = []
            for child in section.children:
                if child.title.lower().strip() in _BIB_SECTION_TITLES:
                    ref_text = _section_to_plain_text(child)
                    entries = entries_from_markdown_refs(ref_text)
                    chapter.bibliography.extend(entries)
                else:
                    kept_children.append(child)
            section.children = kept_children
            remaining.append(section)

    chapter.sections = remaining


def _section_to_plain_text(section: Section) -> str:
    """Extract plain text from a section's content blocks.

    Preserves line breaks within paragraphs (important for reference lists
    where multiple entries may appear in a single Markdown paragraph).
    """
    lines: list[str] = []
    for block in section.content:
        if isinstance(block, Paragraph):
            # Reconstruct text preserving newlines from softbreaks
            parts = []
            for r in block.runs:
                if r.text == "\n":
                    parts.append("\n")
                else:
                    parts.append(r.text)
            text = "".join(parts)
            if text.strip():
                lines.append(text.strip())
        elif isinstance(block, ListBlock):
            for item in block.items:
                text = "".join(r.text for r in item.runs)
                if text.strip():
                    lines.append(text.strip())
    return "\n".join(lines)
