"""Tests for the Markdown parser."""

from pathlib import Path

import pytest

from occonvert.formats.markdown import parse_markdown
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
    return parse_markdown(FIXTURES / "simple.md")


class TestFrontMatter:
    def test_title(self, chapter):
        assert chapter.title == "Finite Element Methods"

    def test_author(self, chapter):
        assert len(chapter.authors) == 1
        assert chapter.authors[0].first == "Jane"
        assert chapter.authors[0].last == "Smith"


class TestSections:
    def test_top_level_count(self, chapter):
        titles = [s.title for s in chapter.sections]
        assert "Introduction" in titles
        assert "Methods" in titles
        assert "Results" in titles
        assert "Conclusions" in titles

    def test_subsections(self, chapter):
        intro = chapter.sections[0]
        child_titles = [c.title for c in intro.children]
        assert "Background" in child_titles
        assert "Literature Review" in child_titles

    def test_section_levels(self, chapter):
        for s in chapter.sections:
            assert s.level == 1
            for c in s.children:
                assert c.level == 2


class TestInlineFormatting:
    def test_bold(self, chapter):
        intro = chapter.sections[0]
        para = intro.content[0]
        assert isinstance(para, Paragraph)
        bold_runs = [r for r in para.runs if r.bold]
        assert any("finite element method" in r.text for r in bold_runs)

    def test_italic(self, chapter):
        intro = chapter.sections[0]
        para = intro.content[0]
        italic_runs = [r for r in para.runs if r.italic]
        assert any("engineering" in r.text for r in italic_runs)

    def test_code(self, chapter):
        intro = chapter.sections[0]
        para = intro.content[0]
        code_runs = [r for r in para.runs if r.code]
        assert any("computational mechanics" in r.text for r in code_runs)

    def test_inline_math(self, chapter):
        intro = chapter.sections[0]
        # Second paragraph has inline math
        para = intro.content[1]
        assert isinstance(para, Paragraph)
        math_runs = [r for r in para.runs if r.math]
        assert any("E = mc^2" in r.text for r in math_runs)

    def test_href(self, chapter):
        intro = chapter.sections[0]
        para = intro.content[1]
        assert isinstance(para, Paragraph)
        link_runs = [r for r in para.runs if r.href]
        assert any("example.com" in r.href for r in link_runs)


class TestDisplayMath:
    def test_display_equation(self, chapter):
        intro = chapter.sections[0]
        background = intro.children[0]
        eqs = [b for b in background.content if isinstance(b, Equation)]
        assert len(eqs) == 1
        assert r"\mathbf{F}" in eqs[0].latex
        assert eqs[0].display is True


class TestLists:
    def test_unordered_list(self, chapter):
        methods = chapter.sections[1]
        lists = [b for b in methods.content if isinstance(b, ListBlock)]
        unordered = [lb for lb in lists if not lb.ordered]
        assert len(unordered) >= 1
        assert len(unordered[0].items) == 3

    def test_ordered_list(self, chapter):
        methods = chapter.sections[1]
        lists = [b for b in methods.content if isinstance(b, ListBlock)]
        ordered = [lb for lb in lists if lb.ordered]
        assert len(ordered) >= 1
        assert len(ordered[0].items) == 2


class TestTable:
    def test_table_parsed(self, chapter):
        methods = chapter.sections[1]
        tables = [b for b in methods.content if isinstance(b, Table)]
        assert len(tables) == 1
        t = tables[0]
        assert len(t.headers) == 3
        assert t.headers[0].text == "Property"
        assert len(t.rows) == 2
        assert t.rows[0][0].text == "Force"


class TestFigure:
    def test_figure_parsed(self, chapter):
        results = chapter.sections[2]
        figs = [b for b in results.content if isinstance(b, Figure)]
        assert len(figs) == 1
        assert figs[0].alt_text == "Complex plane diagram"
        assert "figcomplex" in figs[0].source_path

    def test_figure_in_images_list(self, chapter):
        assert len(chapter.images) >= 1
        assert any("figcomplex" in f.source_path for f in chapter.images)


class TestCodeBlock:
    def test_code_block(self, chapter):
        results = chapter.sections[2]
        codes = [b for b in results.content if isinstance(b, CodeBlock)]
        assert len(codes) == 1
        assert "numpy" in codes[0].code
        assert codes[0].language == "python"


class TestBlockquote:
    def test_blockquote_as_paragraph(self, chapter):
        results = chapter.sections[2]
        paras = [b for b in results.content if isinstance(b, Paragraph)]
        texts = []
        for p in paras:
            texts.append("".join(r.text for r in p.runs))
        assert any("blockquote" in t for t in texts)


class TestEndToEnd:
    def test_generates_valid_tex(self, chapter):
        tex = generate_chapter_tex(chapter, chabbr="FNTELM")
        # Structural checks
        assert r"\chapter{Finite Element Methods}" in tex
        assert r"\renewcommand{\chabbr}{FNTELM}" in tex
        assert r"\section{Introduction}" in tex
        assert r"\subsection{Background}" in tex
        assert r"\section{Methods}" in tex
        assert r"\section{Results}" in tex
        assert r"\section{Conclusions}" in tex
        assert r"\begin{equation}" in tex
        assert r"\begin{itemize}" in tex
        assert r"\begin{enumerate}" in tex
        assert r"\begin{table}" in tex
        assert r"\begin{verbatim}" in tex
        assert r"\textbf{finite element method}" in tex
        assert r"\OCchapterauthor{Jane Smith" in tex
        assert r"\writeauthor" in tex
        assert "learningobjectives" in tex

    def test_generates_valid_json(self, chapter):
        import json
        result = generate_chapter_json(chapter, chabbr="FNTELM")
        data = json.loads(result)
        assert data["title"] == "Finite Element Methods"
        assert data["chabbr"] == "FNTELM"
        assert "Introduction" in data["toc"]
        assert "Methods" in data["toc"]
        assert "Jane Smith" in data["authors"]


class TestNoFrontMatter:
    def test_title_from_first_heading(self):
        md_file = FIXTURES / "no_frontmatter.md"
        md_file.write_text("# My Title\n\nSome text.\n\n## Subsection\n\nMore text.\n")
        try:
            ch = parse_markdown(md_file)
            assert ch.title == "My Title"
            assert len(ch.sections) == 1
            assert ch.sections[0].title == "My Title"
            assert len(ch.sections[0].children) == 1
        finally:
            md_file.unlink()


class TestNoHeadings:
    def test_content_without_headings(self):
        md_file = FIXTURES / "no_headings.md"
        md_file.write_text("Just some text.\n\nAnd another paragraph.\n")
        try:
            ch = parse_markdown(md_file)
            assert len(ch.sections) == 1
            assert ch.sections[0].title == "Introduction"
            assert len(ch.sections[0].content) == 2
        finally:
            md_file.unlink()
