"""Edge case and regression tests."""

import json
from pathlib import Path

import pytest

from occonvert.converter import convert
from occonvert.formats.markdown import parse_markdown
from occonvert.model import (
    Author,
    Chapter,
    Equation,
    Figure,
    InlineRun,
    Paragraph,
    Section,
)
from occonvert.template import generate_bib, generate_chapter_json, generate_chapter_tex

FIXTURES = Path(__file__).parent / "fixtures"


class TestEmptyDocuments:
    def test_empty_markdown(self, tmp_path):
        md = tmp_path / "empty.md"
        md.write_text("")
        chapter = parse_markdown(md)
        assert chapter.sections == []
        # Should still generate valid template output
        tex = generate_chapter_tex(chapter)
        assert r"\chapter{" in tex

    def test_whitespace_only_markdown(self, tmp_path):
        md = tmp_path / "blank.md"
        md.write_text("   \n\n   \n")
        chapter = parse_markdown(md)
        tex = generate_chapter_tex(chapter)
        assert r"\chapter{" in tex

    def test_frontmatter_only(self, tmp_path):
        md = tmp_path / "fm.md"
        md.write_text('---\ntitle: "Just a Title"\nauthor: "Jane Doe"\n---\n')
        chapter = parse_markdown(md)
        assert chapter.title == "Just a Title"
        assert len(chapter.authors) == 1
        tex = generate_chapter_tex(chapter)
        assert "Just a Title" in tex


class TestEmptyChapter:
    def test_no_authors(self):
        ch = Chapter(title="Test")
        tex = generate_chapter_tex(ch)
        assert "REPLACE: Your Name" in tex

    def test_no_sections(self):
        ch = Chapter(title="Test")
        tex = generate_chapter_tex(ch)
        assert r"\chapter{Test}" in tex
        assert "CHAPTER CONTENT STARTS HERE" in tex

    def test_no_title(self):
        ch = Chapter()
        tex = generate_chapter_tex(ch)
        assert "REPLACE: Your Chapter Title" in tex

    def test_empty_json(self):
        ch = Chapter()
        result = generate_chapter_json(ch)
        data = json.loads(result)
        assert data["title"] == "REPLACE: Your Chapter Title"
        assert data["published"] is False

    def test_empty_bib(self):
        result = generate_bib([])
        assert "lastnameYEAR" in result  # has instructions


class TestSpecialCharacters:
    def test_latex_special_chars_in_title(self):
        ch = Chapter(title="50% Off & More")
        tex = generate_chapter_tex(ch)
        # Title appears in \chapter{} — should be as-is since LaTeX
        # handles it in the template context
        assert "50% Off & More" in tex

    def test_latex_special_chars_in_paragraph(self):
        ch = Chapter(
            title="Test",
            sections=[
                Section(
                    title="Intro",
                    level=1,
                    content=[
                        Paragraph(runs=[InlineRun(text="Cost is $5 & tax is 10%")])
                    ],
                )
            ],
        )
        tex = generate_chapter_tex(ch)
        assert r"\$5" in tex
        assert r"\&" in tex
        assert r"10\%" in tex

    def test_unicode_in_author(self):
        ch = Chapter(
            title="Test",
            authors=[Author(first="Marc", last="De Graef")],
        )
        tex = generate_chapter_tex(ch)
        assert "Marc De Graef" in tex


class TestDeepNesting:
    def test_three_levels(self):
        ch = Chapter(
            title="Test",
            sections=[
                Section(
                    title="Top",
                    level=1,
                    children=[
                        Section(
                            title="Mid",
                            level=2,
                            children=[
                                Section(
                                    title="Bottom",
                                    level=3,
                                    content=[
                                        Paragraph(
                                            runs=[InlineRun(text="Deep content.")]
                                        )
                                    ],
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        tex = generate_chapter_tex(ch)
        assert r"\section{Top}" in tex
        assert r"\subsection{Mid}" in tex
        assert r"\subsubsection{Bottom}" in tex
        assert "Deep content." in tex


class TestMultipleAuthors:
    def test_two_authors(self):
        ch = Chapter(
            title="Test",
            authors=[
                Author(first="Alice", last="Smith", institution="MIT"),
                Author(first="Bob", last="Jones", institution="CMU"),
            ],
        )
        tex = generate_chapter_tex(ch)
        # First author appears in \OCchapterauthor
        assert "Alice Smith" in tex
        # Both appear in \writeauthor
        assert "Smith" in tex
        assert "Jones" in tex

    def test_multiple_authors_in_json(self):
        ch = Chapter(
            title="Test",
            authors=[
                Author(first="Alice", last="Smith"),
                Author(first="Bob", last="Jones"),
            ],
        )
        result = generate_chapter_json(ch)
        data = json.loads(result)
        assert len(data["authors"]) == 2
        assert "Alice Smith" in data["authors"]
        assert "Bob Jones" in data["authors"]


class TestFoundationalChapter:
    def test_foundational_type(self):
        ch = Chapter(title="Basics", chapter_type="foundational")
        tex = generate_chapter_tex(ch)
        assert r"\corechapter{Yes}" in tex
        # Should NOT be commented out
        lines = tex.splitlines()
        corechapter_lines = [l for l in lines if "corechapter" in l]
        uncommented = [l for l in corechapter_lines if not l.strip().startswith("%")]
        assert len(uncommented) >= 1

    def test_foundational_in_json(self):
        ch = Chapter(title="Basics", chapter_type="foundational")
        result = generate_chapter_json(ch)
        data = json.loads(result)
        assert data["chapter_type"] == "foundational"


class TestRoundTrip:
    def test_markdown_structure_preserved(self):
        """Verify that parsing Markdown and generating LaTeX preserves structure."""
        chapter = parse_markdown(FIXTURES / "simple.md")
        tex = generate_chapter_tex(chapter, chabbr="FNTELM")

        # All original sections present
        assert r"\section{Introduction}" in tex
        assert r"\subsection{Background}" in tex
        assert r"\subsection{Literature Review}" in tex
        assert r"\section{Methods}" in tex
        assert r"\section{Results}" in tex
        assert r"\section{Conclusions}" in tex

        # Key content preserved
        assert "finite element method" in tex
        assert "engineering" in tex
        assert r"\begin{equation}" in tex
        assert r"\begin{itemize}" in tex
        assert r"\begin{table}" in tex
        assert r"\begin{figure}" in tex

        # Bibliography extracted
        assert len(chapter.bibliography) >= 1

        # JSON valid
        json_str = generate_chapter_json(chapter, chabbr="FNTELM")
        data = json.loads(json_str)
        assert data["chabbr"] == "FNTELM"
        assert len(data["toc"]) >= 4


class TestConverterOrchestrator:
    def test_output_directory_structure(self, tmp_path):
        convert(FIXTURES / "simple.md", tmp_path, chabbr="FNTELM")
        assert (tmp_path / "chapter" / "MyChapter.tex").exists()
        assert (tmp_path / "chapter" / "chapter.json").exists()
        assert (tmp_path / "chapter" / "chaptercitations.bib").exists()
        assert (tmp_path / "chapter" / "pdf").is_dir()

    def test_title_override(self, tmp_path):
        convert(FIXTURES / "simple.md", tmp_path, title="Override Title")
        tex = (tmp_path / "chapter" / "MyChapter.tex").read_text()
        assert "Override Title" in tex

    def test_unsupported_format_raises(self, tmp_path):
        txt = tmp_path / "bad.txt"
        txt.write_text("hello")
        with pytest.raises(ValueError, match="Unsupported"):
            convert(txt, tmp_path)
