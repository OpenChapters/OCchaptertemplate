"""Utility functions for label generation, text cleaning, etc."""

from __future__ import annotations

import re
import unicodedata

# Characters that Word uses internally (soft line break \u000b, form feed, etc.)
# that we never want to carry into titles or JSON metadata.
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_text(text: str) -> str:
    """Strip control characters and collapse whitespace.

    Docx paragraphs and cells can contain vertical tabs (``\\u000b``) and other
    control chars used as soft line breaks. These pollute titles and JSON
    metadata, so we scrub them and collapse runs of whitespace to single spaces.
    """
    if not text:
        return ""
    text = _CTRL_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def slugify(text: str) -> str:
    """Convert text to a label-safe slug per OC guidelines.

    Rules from the Author Guidelines:
    - No numerals
    - No spaces or underscores
    - Lowercase
    """
    # Normalize unicode (e.g. accented characters)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    # Remove anything that isn't a letter
    text = re.sub(r"[^a-z]", "", text)
    # Truncate to keep labels reasonable
    if len(text) > 30:
        text = text[:30]
    return text


def make_label(chabbr: str, label_type: str, name: str) -> str:
    """Build an OC label string like \\chabbr:sec:introduction."""
    slug = slugify(name)
    if not slug:
        slug = "unnamed"
    return f"\\chabbr:{label_type}:{slug}"


def derive_chabbr(title: str) -> str:
    """Derive a 6-character chapter abbreviation from a title.

    Takes the uppercase consonants from significant words,
    padded or truncated to exactly 6 characters.
    """
    # Remove common short words
    stopwords = {"the", "a", "an", "of", "in", "on", "to", "for", "and", "or", "with"}
    words = [w for w in title.split() if w.lower() not in stopwords]
    if not words:
        words = title.split()

    # Collect uppercase consonants from each word
    consonants = ""
    for w in words:
        for ch in w.upper():
            if ch.isalpha() and ch not in "AEIOU":
                consonants += ch
            if len(consonants) >= 6:
                break
        if len(consonants) >= 6:
            break

    # If we don't have 6 characters yet, add vowels
    if len(consonants) < 6:
        for w in words:
            for ch in w.upper():
                if ch.isalpha() and ch not in consonants:
                    consonants += ch
                if len(consonants) >= 6:
                    break
            if len(consonants) >= 6:
                break

    # Pad with X if still short
    consonants = consonants.ljust(6, "X")
    return consonants[:6]


def escape_latex(text: str) -> str:
    """Escape special LaTeX characters in plain text."""
    # Order matters: & must come before others that might contain &
    replacements = [
        ("\\", r"\textbackslash{}"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def bib_key(last_name: str, year: str, suffix: str = "a") -> str:
    """Generate a citation key in the OC format: lastnameYEARa."""
    clean = re.sub(r"[^a-z]", "", last_name.lower())
    return f"{clean}{year}{suffix}"


def runs_to_latex(runs: list) -> str:
    """Convert a list of InlineRun objects to LaTeX markup."""
    parts = []
    for r in runs:
        if r.math:
            parts.append(f"${r.text}$")
            continue

        text = r.text if r.math or r.code else escape_latex(r.text)

        if r.code:
            # Use \verb for short inline code
            # Pick a delimiter not in the text
            delim = "|"
            if delim in text:
                delim = "!"
            parts.append(f"\\verb{delim}{text}{delim}")
            continue

        if r.superscript:
            text = f"\\textsuperscript{{{text}}}"
        if r.subscript:
            text = f"\\textsubscript{{{text}}}"
        if r.bold and r.italic:
            text = f"\\textbf{{\\textit{{{text}}}}}"
        elif r.bold:
            text = f"\\textbf{{{text}}}"
        elif r.italic:
            text = f"\\textit{{{text}}}"

        if r.href:
            text = f"\\href{{{escape_latex(r.href)}}}{{{text}}}"

        parts.append(text)
    return "".join(parts)
