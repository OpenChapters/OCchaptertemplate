"""Tests for the Word (.docx) parser."""

from pathlib import Path

import pytest

from occonvert.formats.docx import parse_docx
from occonvert.model import (
    CodeBlock,
    Equation,
    Figure,
    ListBlock,
    Paragraph,
    Table,
)
from occonvert.template import generate_chapter_tex, generate_chapter_json

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def chapter():
    return parse_docx(FIXTURES / "simple.docx")


class TestTitleAndAuthor:
    def test_title(self, chapter):
        assert chapter.title == "Finite Element Methods"

    def test_author(self, chapter):
        assert len(chapter.authors) >= 1
        a = chapter.authors[0]
        assert a.first == "Jane"
        assert a.last == "Smith"
        assert "Carnegie Mellon" in a.institution


class TestSections:
    def test_top_level_sections(self, chapter):
        titles = [s.title for s in chapter.sections]
        assert "Introduction" in titles
        assert "Methods" in titles
        assert "Results" in titles
        assert "Conclusions" in titles

    def test_subsection(self, chapter):
        intro = next(s for s in chapter.sections if s.title == "Introduction")
        child_titles = [c.title for c in intro.children]
        assert "Background" in child_titles

    def test_section_levels(self, chapter):
        for s in chapter.sections:
            assert s.level == 1
            for c in s.children:
                assert c.level == 2


class TestInlineFormatting:
    def test_bold(self, chapter):
        intro = next(s for s in chapter.sections if s.title == "Introduction")
        paras = [b for b in intro.content if isinstance(b, Paragraph)]
        assert len(paras) >= 1
        bold_runs = [r for p in paras for r in p.runs if r.bold]
        assert any("finite element method" in r.text for r in bold_runs)

    def test_italic(self, chapter):
        intro = next(s for s in chapter.sections if s.title == "Introduction")
        paras = [b for b in intro.content if isinstance(b, Paragraph)]
        italic_runs = [r for p in paras for r in p.runs if r.italic]
        assert any("engineering" in r.text for r in italic_runs)

    def test_subscript(self, chapter):
        concl = next(s for s in chapter.sections if s.title == "Conclusions")
        paras = [b for b in concl.content if isinstance(b, Paragraph)]
        all_runs = [r for p in paras for r in p.runs]
        sub_runs = [r for r in all_runs if r.subscript]
        assert any("2" in r.text for r in sub_runs)

    def test_superscript(self, chapter):
        concl = next(s for s in chapter.sections if s.title == "Conclusions")
        paras = [b for b in concl.content if isinstance(b, Paragraph)]
        all_runs = [r for p in paras for r in p.runs]
        sup_runs = [r for r in all_runs if r.superscript]
        assert any("2" in r.text for r in sup_runs)


class TestLists:
    def test_unordered_list(self, chapter):
        methods = next(s for s in chapter.sections if s.title == "Methods")
        lists = [b for b in methods.content if isinstance(b, ListBlock)]
        unordered = [lb for lb in lists if not lb.ordered]
        assert len(unordered) >= 1
        assert len(unordered[0].items) == 3
        # Check content of first item
        first_text = "".join(r.text for r in unordered[0].items[0].runs)
        assert "Discretize" in first_text

    def test_ordered_list(self, chapter):
        methods = next(s for s in chapter.sections if s.title == "Methods")
        lists = [b for b in methods.content if isinstance(b, ListBlock)]
        ordered = [lb for lb in lists if lb.ordered]
        assert len(ordered) >= 1
        assert len(ordered[0].items) == 2


class TestTable:
    def test_table_parsed(self, chapter):
        methods = next(s for s in chapter.sections if s.title == "Methods")
        tables = [b for b in methods.content if isinstance(b, Table)]
        assert len(tables) == 1
        t = tables[0]
        assert len(t.headers) == 3
        assert t.headers[0].text == "Property"
        assert len(t.rows) == 2
        assert t.rows[0][0].text == "Force"


class TestImage:
    def test_image_extracted(self, chapter):
        assert len(chapter.images) >= 1
        fig = chapter.images[0]
        assert Path(fig.source_path).exists()
        assert fig.alt_text  # has some name

    def test_figure_in_section(self, chapter):
        results = next(s for s in chapter.sections if s.title == "Results")
        figs = [b for b in results.content if isinstance(b, Figure)]
        assert len(figs) >= 1


class TestEndToEnd:
    def test_generates_valid_tex(self, chapter):
        tex = generate_chapter_tex(chapter, chabbr="FNTELM")
        assert r"\chapter{Finite Element Methods}" in tex
        assert r"\renewcommand{\chabbr}{FNTELM}" in tex
        assert r"\section{Introduction}" in tex
        assert r"\subsection{Background}" in tex
        assert r"\section{Methods}" in tex
        assert r"\section{Results}" in tex
        assert r"\section{Conclusions}" in tex
        assert r"\begin{itemize}" in tex
        assert r"\begin{enumerate}" in tex
        assert r"\begin{table}" in tex
        assert r"\toprule" in tex
        assert r"\textbf{finite element method}" in tex
        assert r"\OCchapterauthor{Jane Smith" in tex
        assert "learningobjectives" in tex

    def test_generates_valid_json(self, chapter):
        import json
        result = generate_chapter_json(chapter, chabbr="FNTELM")
        data = json.loads(result)
        assert data["title"] == "Finite Element Methods"
        assert data["chabbr"] == "FNTELM"
        assert "Introduction" in data["toc"]
        assert "Jane Smith" in data["authors"]

    def test_cli_smoke(self, tmp_path):
        """Test the full CLI pipeline with the .docx fixture."""
        from occonvert.converter import convert
        tex_path = convert(
            FIXTURES / "simple.docx",
            tmp_path,
            chabbr="FNTELM",
        )
        assert tex_path.exists()
        tex = tex_path.read_text()
        assert r"\chapter{Finite Element Methods}" in tex
        assert (tmp_path / "chapter" / "chapter.json").exists()
        assert (tmp_path / "chapter" / "chaptercitations.bib").exists()
