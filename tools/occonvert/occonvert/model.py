"""Internal document representation (IR).

All format-specific parsers produce a Chapter object from this module.
The template engine consumes it to emit OC-formatted LaTeX.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Author:
    first: str = ""
    last: str = ""
    department: str = ""
    institution: str = ""
    email: str = ""
    url: str = ""


@dataclass
class InlineRun:
    """A contiguous run of text with uniform formatting."""

    text: str = ""
    bold: bool = False
    italic: bool = False
    code: bool = False
    math: bool = False
    superscript: bool = False
    subscript: bool = False
    href: str = ""  # non-empty means this run is a hyperlink


@dataclass
class Paragraph:
    runs: list[InlineRun] = field(default_factory=list)


@dataclass
class Equation:
    latex: str = ""
    display: bool = True  # True = display equation, False = inline


@dataclass
class Figure:
    source_path: str = ""       # original path/name from the source document
    output_filename: str = ""   # filename written into chapter/pdf/
    caption: str = ""
    alt_text: str = ""


@dataclass
class TableCell:
    text: str = ""
    bold: bool = False


@dataclass
class Table:
    caption: str = ""
    headers: list[TableCell] = field(default_factory=list)
    rows: list[list[TableCell]] = field(default_factory=list)


@dataclass
class ListItem:
    runs: list[InlineRun] = field(default_factory=list)
    children: list[ListItem] = field(default_factory=list)


@dataclass
class ListBlock:
    ordered: bool = False
    items: list[ListItem] = field(default_factory=list)


@dataclass
class CodeBlock:
    code: str = ""
    language: str = ""


# A Block is any one of the content types that can appear in a section.
Block = Paragraph | Equation | Figure | Table | ListBlock | CodeBlock


@dataclass
class Section:
    title: str = ""
    level: int = 1  # 1=section, 2=subsection, 3=subsubsection
    content: list[Block] = field(default_factory=list)
    children: list[Section] = field(default_factory=list)


@dataclass
class BibEntry:
    key: str = ""          # e.g. "smith2026a"
    entry_type: str = "article"
    fields: dict[str, str] = field(default_factory=dict)


@dataclass
class Chapter:
    title: str = ""
    authors: list[Author] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)
    bibliography: list[BibEntry] = field(default_factory=list)
    images: list[Figure] = field(default_factory=list)
    chapter_type: str = "topical"  # "topical" or "foundational"
    speaker_notes: dict[str, str] = field(default_factory=dict)  # section_title -> notes (from pptx)
