"""Equation conversion utilities.

Handles OMML (Office Math Markup Language) to LaTeX conversion,
used by both the .docx and .pptx parsers.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

# OMML namespace
_OMML_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
_OMML_PREFIX = f"{{{_OMML_NS}}}"


def omml_to_latex(omml_element) -> str:
    """Convert an OMML XML element to a LaTeX math string.

    Tries multiple strategies in order:
    1. Pandoc subprocess (most reliable)
    2. Basic built-in converter (handles common cases)
    """
    from lxml import etree

    xml_str = etree.tostring(omml_element, encoding="unicode")

    # Strategy 1: try Pandoc if available
    latex = _try_pandoc(xml_str)
    if latex:
        return latex

    # Strategy 2: basic built-in conversion
    return _builtin_convert(omml_element)


def _try_pandoc(omml_xml: str) -> str | None:
    """Attempt conversion via Pandoc (docx math XML -> LaTeX)."""
    try:
        # Wrap in a minimal docx-like structure for Pandoc
        wrapped = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
            f' xmlns:m="{_OMML_NS}">'
            "<w:body><w:p><w:r>"
            f"{omml_xml}"
            "</w:r></w:p></w:body></w:document>"
        )
        result = subprocess.run(
            ["pandoc", "-f", "docx", "-t", "latex", "--mathml"],
            input=wrapped,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _builtin_convert(element) -> str:
    """Basic OMML-to-LaTeX converter for common constructs.

    Handles: fractions, superscripts, subscripts, radicals, simple text.
    Falls back to extracting plain text for unrecognized constructs.
    """
    tag = _local_tag(element)

    if tag == "f":  # fraction
        num = _find_child_text(element, "num")
        den = _find_child_text(element, "den")
        return f"\\frac{{{num}}}{{{den}}}"

    if tag == "sSup":  # superscript
        base = _find_child_text(element, "e")
        sup = _find_child_text(element, "sup")
        return f"{{{base}}}^{{{sup}}}"

    if tag == "sSub":  # subscript
        base = _find_child_text(element, "e")
        sub = _find_child_text(element, "sub")
        return f"{{{base}}}_{{{sub}}}"

    if tag == "rad":  # radical/root
        deg = _find_child_text(element, "deg")
        content = _find_child_text(element, "e")
        if deg and deg.strip():
            return f"\\sqrt[{deg}]{{{content}}}"
        return f"\\sqrt{{{content}}}"

    if tag == "r":  # run (text)
        return _extract_run_text(element)

    if tag in ("oMath", "oMathPara"):
        # Recurse into children
        parts = []
        for child in element:
            parts.append(_builtin_convert(child))
        return " ".join(parts)

    # Generic: recurse
    parts = []
    for child in element:
        parts.append(_builtin_convert(child))
    return " ".join(parts) if parts else ""


def _local_tag(element) -> str:
    """Strip the namespace from an element tag."""
    tag = element.tag
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _find_child_text(element, child_tag: str) -> str:
    """Find a child element by local tag and extract its text content."""
    for child in element:
        if _local_tag(child) == child_tag:
            return _builtin_convert(child)
    return ""


def _extract_run_text(element) -> str:
    """Extract text from an OMML run element."""
    parts = []
    for child in element:
        ltag = _local_tag(child)
        if ltag == "t":
            parts.append(child.text or "")
    return "".join(parts)
