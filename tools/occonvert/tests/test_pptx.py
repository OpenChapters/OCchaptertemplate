"""Tests for the PowerPoint (.pptx) parser."""

from pathlib import Path

import pytest

from occonvert.formats.pptx import parse_pptx
from occonvert.model import (
    Figure,
    ListBlock,
    Paragraph,
    Table,
)
from occonvert.template import generate_chapter_tex, generate_chapter_json

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def chapter():
    return parse_pptx(FIXTURES / "simple.pptx")


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
    def test_section_count(self, chapter):
        # Slides 2-6 become sections (slide 1 is title slide)
        assert len(chapter.sections) >= 4

    def test_section_titles(self, chapter):
        titles = [s.title for s in chapter.sections]
        assert "Introduction" in titles
        assert "Methods" in titles
        assert "Conclusions" in titles

    def test_all_level_one(self, chapter):
        for s in chapter.sections:
            assert s.level == 1


class TestBulletList:
    def test_bullets_from_slide(self, chapter):
        methods = next((s for s in chapter.sections if s.title == "Methods"), None)
        assert methods is not None
        lists = [b for b in methods.content if isinstance(b, ListBlock)]
        assert len(lists) >= 1
        items = lists[0].items
        assert len(items) == 3
        first_text = "".join(r.text for r in items[0].runs)
        assert "Discretize" in first_text


class TestTable:
    def test_table_from_slide(self, chapter):
        results = next((s for s in chapter.sections if s.title == "Results"), None)
        assert results is not None
        tables = [b for b in results.content if isinstance(b, Table)]
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

    def test_figure_in_section(self, chapter):
        figs_sec = next((s for s in chapter.sections if s.title == "Figures"), None)
        assert figs_sec is not None
        figs = [b for b in figs_sec.content if isinstance(b, Figure)]
        assert len(figs) >= 1


class TestInlineFormatting:
    def test_bold_runs(self, chapter):
        concl = next((s for s in chapter.sections if s.title == "Conclusions"), None)
        assert concl is not None
        all_runs = []
        for b in concl.content:
            if isinstance(b, (Paragraph, ListBlock)):
                if isinstance(b, Paragraph):
                    all_runs.extend(b.runs)
                else:
                    for item in b.items:
                        all_runs.extend(item.runs)
        bold_runs = [r for r in all_runs if r.bold]
        assert any("Bold conclusion" in r.text for r in bold_runs)

    def test_italic_runs(self, chapter):
        concl = next((s for s in chapter.sections if s.title == "Conclusions"), None)
        assert concl is not None
        all_runs = []
        for b in concl.content:
            if isinstance(b, (Paragraph, ListBlock)):
                if isinstance(b, Paragraph):
                    all_runs.extend(b.runs)
                else:
                    for item in b.items:
                        all_runs.extend(item.runs)
        italic_runs = [r for r in all_runs if r.italic]
        assert any("Italic note" in r.text for r in italic_runs)


class TestSpeakerNotes:
    def test_notes_included(self, chapter):
        methods = next((s for s in chapter.sections if s.title == "Methods"), None)
        assert methods is not None
        all_text = ""
        for b in methods.content:
            if isinstance(b, Paragraph):
                all_text += "".join(r.text for r in b.runs)
        assert "NOTE:" in all_text
        assert "Explain each step" in all_text


class TestTodoComments:
    def test_expand_todo(self, chapter):
        for s in chapter.sections:
            all_text = ""
            for b in s.content:
                if isinstance(b, Paragraph):
                    all_text += "".join(r.text for r in b.runs)
            assert "TODO: Expand slide content" in all_text


class TestEndToEnd:
    def test_generates_valid_tex(self, chapter):
        tex = generate_chapter_tex(chapter, chabbr="FNTELM")
        assert r"\chapter{Finite Element Methods}" in tex
        assert r"\renewcommand{\chabbr}{FNTELM}" in tex
        assert r"\section{Introduction}" in tex
        assert r"\section{Methods}" in tex
        assert r"\section{Conclusions}" in tex
        assert r"\begin{itemize}" in tex
        assert r"\begin{table}" in tex
        assert r"\toprule" in tex
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
        from occonvert.converter import convert
        tex_path = convert(
            FIXTURES / "simple.pptx",
            tmp_path,
            chabbr="FNTELM",
        )
        assert tex_path.exists()
        tex = tex_path.read_text()
        assert r"\chapter{Finite Element Methods}" in tex
        assert (tmp_path / "chapter" / "chapter.json").exists()
        assert (tmp_path / "chapter" / "chaptercitations.bib").exists()
