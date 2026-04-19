"""Tests for bibliography extraction and generation."""

from pathlib import Path

import pytest

from occonvert.bibtex import (
    entries_from_bib_file,
    entries_from_markdown_refs,
)
from occonvert.model import BibEntry
from occonvert.template import generate_bib

FIXTURES = Path(__file__).parent / "fixtures"


class TestMarkdownRefs:
    def test_parses_standard_refs(self):
        text = (
            "Smith, J. (2024). Finite element methods. "
            "Journal of Mechanics, 15(3), 100-120.\n"
            "Jones, A. and Brown, B. (2023). Mesh generation. "
            "Engineering Analysis, 42, 55-78.\n"
        )
        entries = entries_from_markdown_refs(text)
        assert len(entries) == 2

    def test_extracts_author(self):
        text = "Smith, J. (2024). A great paper. Nature, 1, 1-2.\n"
        entries = entries_from_markdown_refs(text)
        assert len(entries) == 1
        assert "Smith" in entries[0].fields["author"]

    def test_extracts_year(self):
        text = "Smith, J. (2024). A great paper. Nature, 1, 1-2.\n"
        entries = entries_from_markdown_refs(text)
        assert entries[0].fields["year"] == "2024"

    def test_extracts_title(self):
        text = "Smith, J. (2024). A great paper. Nature, 1, 1-2.\n"
        entries = entries_from_markdown_refs(text)
        assert "great paper" in entries[0].fields["title"]

    def test_extracts_journal(self):
        text = "Smith, J. (2024). A paper. Journal of Things, 1, 1-2.\n"
        entries = entries_from_markdown_refs(text)
        assert "Journal of Things" in entries[0].fields.get("journal", "")

    def test_extracts_doi(self):
        text = "Smith, J. (2024). A paper. Nature, 1, 1-2. doi:10.1000/test.123\n"
        entries = entries_from_markdown_refs(text)
        assert entries[0].fields.get("doi") == "10.1000/test.123"

    def test_extracts_doi_url(self):
        text = "Smith, J. (2024). A paper. Nature, 1, 1-2. https://doi.org/10.1000/test.456\n"
        entries = entries_from_markdown_refs(text)
        assert "10.1000/test.456" in entries[0].fields.get("doi", "")

    def test_key_format(self):
        text = "Smith, J. (2024). A paper. Nature, 1, 1-2.\n"
        entries = entries_from_markdown_refs(text)
        assert entries[0].key == "smith2024a"

    def test_unique_keys(self):
        text = (
            "Smith, J. (2024). First paper. Nature, 1, 1-2.\n"
            "Smith, A. (2024). Second paper. Science, 2, 3-4.\n"
        )
        entries = entries_from_markdown_refs(text)
        keys = [e.key for e in entries]
        assert len(set(keys)) == 2  # all unique

    def test_numbered_refs(self):
        text = (
            "[1] Smith, J. (2024). Paper one. Nature, 1, 1-2.\n"
            "[2] Jones, A. (2023). Paper two. Science, 3, 5-6.\n"
        )
        entries = entries_from_markdown_refs(text)
        assert len(entries) == 2

    def test_bulleted_refs(self):
        text = (
            "- Smith, J. (2024). Paper one. Nature, 1, 1-2.\n"
            "- Jones, A. (2023). Paper two. Science, 3, 5-6.\n"
        )
        entries = entries_from_markdown_refs(text)
        assert len(entries) == 2

    def test_empty_text(self):
        assert entries_from_markdown_refs("") == []

    def test_ignores_headings(self):
        text = "# References\nSmith, J. (2024). A paper. Nature, 1, 1-2.\n"
        entries = entries_from_markdown_refs(text)
        assert len(entries) == 1  # heading line skipped


class TestBibFile:
    def test_parses_bib_file(self, tmp_path):
        bib = tmp_path / "refs.bib"
        bib.write_text(
            "@article{smith2024a,\n"
            "  author = {Smith, John},\n"
            "  title = {A Great Paper},\n"
            "  journal = {Nature},\n"
            "  year = {2024},\n"
            "  doi = {10.1000/test},\n"
            "}\n"
            "\n"
            "@book{jones2023a,\n"
            '  author = "Jones, Alice",\n'
            '  title = "A Book",\n'
            '  year = "2023",\n'
            "}\n"
        )
        entries = entries_from_bib_file(bib)
        assert len(entries) == 2
        assert entries[0].key == "smith2024a"
        assert entries[0].entry_type == "article"
        assert entries[0].fields["author"] == "Smith, John"
        assert entries[0].fields["doi"] == "10.1000/test"
        assert entries[1].key == "jones2023a"
        assert entries[1].entry_type == "book"

    def test_handles_nested_braces(self, tmp_path):
        bib = tmp_path / "refs.bib"
        bib.write_text(
            "@article{test2024a,\n"
            "  author = {De {Graef}, Marc},\n"
            "  title = {Something},\n"
            "  year = {2024},\n"
            "}\n"
        )
        entries = entries_from_bib_file(bib)
        assert len(entries) == 1
        assert "Graef" in entries[0].fields["author"]

    def test_empty_file(self, tmp_path):
        bib = tmp_path / "empty.bib"
        bib.write_text("")
        assert entries_from_bib_file(bib) == []


class TestGenerateBib:
    def test_doi_warning_when_missing(self):
        entries = [
            BibEntry(
                key="smith2024a",
                entry_type="article",
                fields={"author": "Smith", "title": "Paper", "year": "2024"},
            )
        ]
        result = generate_bib(entries)
        assert "%% TODO: add DOI for smith2024a" in result

    def test_no_doi_warning_when_present(self):
        entries = [
            BibEntry(
                key="smith2024a",
                entry_type="article",
                fields={
                    "author": "Smith",
                    "title": "Paper",
                    "year": "2024",
                    "doi": "10.1000/test",
                },
            )
        ]
        result = generate_bib(entries)
        assert "TODO: add DOI" not in result

    def test_mixed_entries(self):
        entries = [
            BibEntry(
                key="smith2024a",
                entry_type="article",
                fields={"author": "Smith", "title": "No DOI", "year": "2024"},
            ),
            BibEntry(
                key="jones2023a",
                entry_type="article",
                fields={
                    "author": "Jones",
                    "title": "Has DOI",
                    "year": "2023",
                    "doi": "10.1000/x",
                },
            ),
        ]
        result = generate_bib(entries)
        assert "%% TODO: add DOI for smith2024a" in result
        assert "TODO: add DOI for jones2023a" not in result


class TestMarkdownBibIntegration:
    def test_refs_extracted_from_md(self):
        from occonvert.formats.markdown import parse_markdown

        chapter = parse_markdown(FIXTURES / "simple.md")
        assert len(chapter.bibliography) >= 2

        # References section should be removed from chapter content
        section_titles = [s.title for s in chapter.sections]
        assert "References" not in section_titles

    def test_ref_keys_format(self):
        from occonvert.formats.markdown import parse_markdown

        chapter = parse_markdown(FIXTURES / "simple.md")
        for entry in chapter.bibliography:
            # Keys should be lowercase + year + letter
            assert entry.key[0].islower()
            assert any(c.isdigit() for c in entry.key)

    def test_doi_extracted(self):
        from occonvert.formats.markdown import parse_markdown

        chapter = parse_markdown(FIXTURES / "simple.md")
        doi_entries = [e for e in chapter.bibliography if "doi" in e.fields]
        assert len(doi_entries) >= 1

    def test_bib_file_takes_precedence(self, tmp_path):
        """If a .bib file exists alongside the .md, use it instead."""
        from occonvert.formats.markdown import parse_markdown

        md = tmp_path / "test.md"
        md.write_text(
            "# Intro\n\nSome text.\n\n"
            "# References\n\n"
            "Smith, J. (2024). Should be ignored. Nature, 1, 1-2.\n"
        )
        bib = tmp_path / "refs.bib"
        bib.write_text(
            "@article{fromfile2024a,\n"
            "  author = {From File},\n"
            "  title = {From the bib file},\n"
            "  year = {2024},\n"
            "}\n"
        )
        chapter = parse_markdown(md)
        # Should use the .bib file entries, not parse the References section
        assert any(e.key == "fromfile2024a" for e in chapter.bibliography)

    def test_end_to_end_bib_output(self):
        from occonvert.formats.markdown import parse_markdown

        chapter = parse_markdown(FIXTURES / "simple.md")
        bib_output = generate_bib(chapter.bibliography)
        assert "@article{" in bib_output
        assert "smith2024a" in bib_output.lower() or "smith" in bib_output.lower()
