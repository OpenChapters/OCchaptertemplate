"""Bibliography extraction and BibTeX generation."""

from __future__ import annotations

import re
from pathlib import Path

from .model import BibEntry
from .utils import bib_key


# ---------------------------------------------------------------------------
# Word customXml extraction
# ---------------------------------------------------------------------------


def entries_from_docx_xml(custom_xml: str | bytes) -> list[BibEntry]:
    """Extract bibliography entries from Word's customXml bibliography store.

    Word stores its citation manager data in customXml/item*.xml.
    This function parses the Sources element.
    """
    from lxml import etree

    entries = []
    try:
        raw = custom_xml.encode() if isinstance(custom_xml, str) else custom_xml
        root = etree.fromstring(raw)
    except etree.XMLSyntaxError:
        return entries

    # Word bibliography namespace
    ns = {"b": "http://schemas.openxmlformats.org/officeDocument/2006/bibliography"}

    for source in root.findall(".//b:Source", ns):
        entry = BibEntry()
        entry.entry_type = _map_source_type(
            _get_text(source, "b:SourceType", ns)
        )

        # Extract author last name
        author_last = ""
        for last in source.findall(".//b:Author//b:Last", ns):
            if last.text:
                author_last = last.text
                break

        year = _get_text(source, "b:Year", ns) or "0000"
        entry.key = bib_key(author_last or "unknown", year)

        # Build fields
        title = _get_text(source, "b:Title", ns)
        if title:
            entry.fields["title"] = title

        # Collect all author names
        authors = []
        for name_elem in source.findall(".//b:Author//b:NameList//b:Person", ns):
            last = _get_text(name_elem, "b:Last", ns) or ""
            first = _get_text(name_elem, "b:First", ns) or ""
            if last:
                authors.append(f"{last}, {first}".rstrip(", "))
        if authors:
            entry.fields["author"] = " and ".join(authors)

        journal = _get_text(source, "b:JournalName", ns)
        if journal:
            entry.fields["journal"] = journal

        if year != "0000":
            entry.fields["year"] = year

        volume = _get_text(source, "b:Volume", ns)
        if volume:
            entry.fields["volume"] = volume

        pages = _get_text(source, "b:Pages", ns)
        if pages:
            entry.fields["pages"] = pages

        doi = _get_text(source, "b:DOI", ns)
        if doi:
            entry.fields["doi"] = doi

        entries.append(entry)

    return entries


# ---------------------------------------------------------------------------
# Markdown reference parsing
# ---------------------------------------------------------------------------

# Pattern for a reference line like:
#   [1] Smith, J. (2026). Title of paper. Journal Name, 10(2), 1-20.
#   Smith, J. (2026). Title of paper. Journal Name, 10(2), 1-20.
#   - Smith, J. (2026). Title of paper. ...
_REF_LINE_RE = re.compile(
    r"^(?:\[?\d+\]?\s*)?(?:[-*]\s+)?"  # optional [1] or bullet prefix
    r"(?P<authors>[A-Z][^(]+?)"          # author names (starts with capital)
    r"\s*\((?P<year>\d{4})\)"            # (year)
    r"[.,]?\s*"
    r"(?P<title>[^.]+)"                  # title (up to first period)
    r"\.?\s*"
    r"(?P<rest>.*)",                      # journal, volume, pages, DOI
    re.MULTILINE,
)

_DOI_RE = re.compile(r"(?:doi:\s*|https?://doi\.org/)?(10\.\d{4,}/\S+)", re.IGNORECASE)


def entries_from_markdown_refs(text: str) -> list[BibEntry]:
    """Parse plain-text reference lines into BibEntry objects.

    Expects text from a References/Bibliography section of a Markdown document.
    Handles common academic citation formats.
    """
    entries: list[BibEntry] = []
    seen_keys: set[str] = set()

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        m = _REF_LINE_RE.match(line)
        if not m:
            continue

        authors_str = m.group("authors").strip().rstrip(",")
        year = m.group("year")
        title = m.group("title").strip()
        rest = m.group("rest").strip()

        # Extract first author last name for key
        first_author = authors_str.split(",")[0].split(" and ")[0].strip()
        # Handle "Last, First" or "First Last"
        if "," in first_author:
            last_name = first_author.split(",")[0].strip()
        else:
            parts = first_author.split()
            last_name = parts[-1] if parts else "unknown"

        # Generate unique key
        key = bib_key(last_name, year)
        suffix_ord = ord("a")
        while key in seen_keys:
            suffix_ord += 1
            key = bib_key(last_name, year, chr(suffix_ord))
        seen_keys.add(key)

        entry = BibEntry(key=key, entry_type="article")
        entry.fields["author"] = authors_str
        entry.fields["title"] = title
        entry.fields["year"] = year

        # Try to extract journal, volume, pages from rest
        if rest:
            _parse_rest(rest, entry)

        # Check for DOI anywhere in the line
        doi_m = _DOI_RE.search(line)
        if doi_m:
            entry.fields["doi"] = doi_m.group(1)

        entries.append(entry)

    return entries


def _parse_rest(rest: str, entry: BibEntry) -> None:
    """Try to extract journal, volume, pages from the text after the title."""
    # Remove trailing DOI if present
    rest = _DOI_RE.sub("", rest).strip().rstrip(".")

    if not rest:
        return

    # Common pattern: "Journal Name, vol(issue), pages"
    # or "Journal Name, vol, pages"
    parts = [p.strip() for p in rest.split(",")]

    if parts:
        # First part is usually the journal name
        journal = parts[0].rstrip(".")
        if journal and not journal[0].isdigit():
            entry.fields["journal"] = journal

        # Look for volume and pages in remaining parts
        for part in parts[1:]:
            part = part.strip().rstrip(".")
            # Volume: a number possibly with (issue)
            vol_m = re.match(r"^(\d+)\s*(?:\((\d+)\))?$", part)
            if vol_m:
                entry.fields["volume"] = vol_m.group(1)
                continue
            # Pages: number-number or number--number
            pages_m = re.match(r"^(\d+)\s*[-–]+\s*(\d+)$", part)
            if pages_m:
                entry.fields["pages"] = f"{pages_m.group(1)}--{pages_m.group(2)}"
                continue


# ---------------------------------------------------------------------------
# .bib file import
# ---------------------------------------------------------------------------


def entries_from_bib_file(path: Path) -> list[BibEntry]:
    """Parse an existing .bib file into BibEntry objects.

    Uses a simple regex-based parser — not a full BibTeX parser,
    but sufficient for well-formed entries.
    """
    text = path.read_text(encoding="utf-8")
    entries: list[BibEntry] = []

    # Match @type{key, ... }
    entry_re = re.compile(
        r"@(\w+)\s*\{\s*([^,]+)\s*,(.*?)\n\s*\}",
        re.DOTALL,
    )

    for m in entry_re.finditer(text):
        entry_type = m.group(1).lower()
        key = m.group(2).strip()
        body = m.group(3)

        if entry_type in ("comment", "string", "preamble"):
            continue

        entry = BibEntry(key=key, entry_type=entry_type)

        # Parse field = {value} or field = "value"
        field_re = re.compile(
            r"(\w+)\s*=\s*(?:\{((?:[^{}]|\{[^{}]*\})*)\}|\"([^\"]*)\")",
        )
        for fm in field_re.finditer(body):
            field_name = fm.group(1).lower()
            value = fm.group(2) if fm.group(2) is not None else fm.group(3)
            entry.fields[field_name] = value.strip()

        entries.append(entry)

    return entries


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_text(element, path: str, ns: dict) -> str:
    """Get text content of a child element by path."""
    child = element.find(path, ns)
    if child is not None and child.text:
        return child.text.strip()
    return ""


def _map_source_type(word_type: str) -> str:
    """Map Word source type to BibTeX entry type."""
    mapping = {
        "JournalArticle": "article",
        "Book": "book",
        "BookSection": "incollection",
        "ConferenceProceedings": "inproceedings",
        "Report": "techreport",
        "InternetSite": "misc",
        "DocumentFromInternetSite": "misc",
    }
    return mapping.get(word_type, "misc")
