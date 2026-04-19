"""Tests for occonvert.template — the LaTeX template generator."""

import json

from occonvert.model import (
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
from occonvert.template import generate_bib, generate_chapter_json, generate_chapter_tex


def _simple_chapter() -> Chapter:
    """Build a minimal Chapter IR for testing."""
    return Chapter(
        title="Basic Crystallography",
        authors=[
            Author(
                first="Marc",
                last="De Graef",
                department="Materials Science",
                institution="Carnegie Mellon University",
                email="degraef@cmu.edu",
                url="https://www.cmu.edu/degraef",
            )
        ],
        sections=[
            Section(
                title="Introduction",
                level=1,
                content=[
                    Paragraph(runs=[InlineRun(text="This is the introduction.")])
                ],
                children=[
                    Section(
                        title="Background",
                        level=2,
                        content=[
                            Paragraph(
                                runs=[InlineRun(text="Some background material.")]
                            )
                        ],
                    )
                ],
            ),
            Section(
                title="Methods",
                level=1,
                content=[
                    Paragraph(
                        runs=[
                            InlineRun(text="We use the "),
                            InlineRun(text="finite element", italic=True),
                            InlineRun(text=" method."),
                        ]
                    ),
                    Equation(latex=r"\mathbf{F} = m\mathbf{a}"),
                ],
            ),
        ],
    )


class TestGenerateChapterTex:
    def test_contains_copyright(self):
        tex = generate_chapter_tex(_simple_chapter())
        assert "Copyright" in tex
        assert "CC BY-NC-SA 4.0" in tex

    def test_contains_chapter_command(self):
        tex = generate_chapter_tex(_simple_chapter())
        assert r"\chapter{Basic Crystallography}" in tex

    def test_contains_chabbr(self):
        tex = generate_chapter_tex(_simple_chapter(), chabbr="BASCRY")
        assert r"\renewcommand{\chabbr}{BASCRY}" in tex

    def test_auto_derives_chabbr(self):
        tex = generate_chapter_tex(_simple_chapter())
        assert r"\renewcommand{\chabbr}" in tex

    def test_contains_author_info(self):
        tex = generate_chapter_tex(_simple_chapter())
        assert r"\OCchapterauthor{Marc De Graef, Carnegie Mellon University}" in tex
        assert r"\writeauthor" in tex
        assert "De Graef" in tex
        assert "degraef@cmu.edu" in tex

    def test_contains_learning_objectives(self):
        tex = generate_chapter_tex(_simple_chapter())
        assert r"\begin{learningobjectives}" in tex
        assert r"\end{learningobjectives}" in tex
        assert "OCBurntOrange" in tex

    def test_contains_sections(self):
        tex = generate_chapter_tex(_simple_chapter())
        assert r"\section{Introduction}" in tex
        assert r"\subsection{Background}" in tex
        assert r"\section{Methods}" in tex

    def test_contains_labels(self):
        tex = generate_chapter_tex(_simple_chapter())
        assert r"\chabbr:sec:introduction" in tex
        assert r"\chabbr:ssec:background" in tex
        assert r"\chabbr:sec:methods" in tex

    def test_contains_equation(self):
        tex = generate_chapter_tex(_simple_chapter())
        assert r"\begin{equation}" in tex
        assert r"\mathbf{F} = m\mathbf{a}" in tex

    def test_contains_paragraph_text(self):
        tex = generate_chapter_tex(_simple_chapter())
        assert "This is the introduction." in tex
        assert r"\textit{finite element}" in tex

    def test_contains_todo_summary(self):
        tex = generate_chapter_tex(_simple_chapter())
        assert "TODO SUMMARY" in tex

    def test_noheaderimage(self):
        tex = generate_chapter_tex(_simple_chapter())
        assert r"\chapterimage{\noheaderimage}" in tex

    def test_foundational_chapter(self):
        ch = _simple_chapter()
        ch.chapter_type = "foundational"
        tex = generate_chapter_tex(ch)
        assert r"\corechapter{Yes}" in tex

    def test_topical_chapter_comments_out_corechapter(self):
        tex = generate_chapter_tex(_simple_chapter())
        assert r"%\corechapter{Yes}" in tex


class TestGenerateChapterTexBlocks:
    def test_figure(self):
        ch = Chapter(
            title="Test",
            sections=[
                Section(
                    title="Figures",
                    level=1,
                    content=[
                        Figure(
                            output_filename="diagram.pdf",
                            caption="A test diagram",
                        )
                    ],
                )
            ],
        )
        tex = generate_chapter_tex(ch)
        assert r"\includegraphics" in tex
        assert "diagram.pdf" in tex
        assert r"\caption" in tex
        assert "A test diagram" in tex
        assert r"\chabbr:fig:" in tex

    def test_table(self):
        ch = Chapter(
            title="Test",
            sections=[
                Section(
                    title="Tables",
                    level=1,
                    content=[
                        Table(
                            caption="Sample data",
                            headers=[TableCell(text="Name"), TableCell(text="Value")],
                            rows=[
                                [TableCell(text="A"), TableCell(text="1")],
                                [TableCell(text="B"), TableCell(text="2")],
                            ],
                        )
                    ],
                )
            ],
        )
        tex = generate_chapter_tex(ch)
        assert r"\begin{table}" in tex
        assert r"\toprule" in tex
        assert r"\midrule" in tex
        assert r"\bottomrule" in tex
        assert "Name & Value" in tex
        assert "A & 1" in tex

    def test_list_block(self):
        ch = Chapter(
            title="Test",
            sections=[
                Section(
                    title="Lists",
                    level=1,
                    content=[
                        ListBlock(
                            ordered=False,
                            items=[
                                ListItem(runs=[InlineRun(text="First item")]),
                                ListItem(runs=[InlineRun(text="Second item")]),
                            ],
                        )
                    ],
                )
            ],
        )
        tex = generate_chapter_tex(ch)
        assert r"\begin{itemize}" in tex
        assert r"\item First item" in tex
        assert r"\item Second item" in tex

    def test_ordered_list(self):
        ch = Chapter(
            title="Test",
            sections=[
                Section(
                    title="Lists",
                    level=1,
                    content=[
                        ListBlock(
                            ordered=True,
                            items=[
                                ListItem(runs=[InlineRun(text="Step one")]),
                            ],
                        )
                    ],
                )
            ],
        )
        tex = generate_chapter_tex(ch)
        assert r"\begin{enumerate}" in tex

    def test_code_block(self):
        ch = Chapter(
            title="Test",
            sections=[
                Section(
                    title="Code",
                    level=1,
                    content=[CodeBlock(code="x = 1\ny = 2")],
                )
            ],
        )
        tex = generate_chapter_tex(ch)
        assert r"\begin{verbatim}" in tex
        assert "x = 1" in tex

    def test_figure_labels_are_unique(self):
        """Multiple figures with empty captions must get distinct labels.

        Regression: pptx parsing produces many figures with empty captions and
        identical alt-text, causing duplicate \\label entries in the output.
        """
        ch = Chapter(
            title="Test",
            sections=[
                Section(
                    title="Figures",
                    level=1,
                    content=[
                        Figure(output_filename="slideimage.pdf"),
                        Figure(output_filename="slideimage2.pdf"),
                        Figure(output_filename="slideimage3.pdf"),
                    ],
                )
            ],
        )
        tex = generate_chapter_tex(ch)
        # Extract all \label{\chabbr:fig:...} tokens
        import re
        labels = re.findall(r"\\label\{\\chabbr:fig:([^}]+)\}", tex)
        assert len(labels) == 3
        assert len(set(labels)) == 3, f"duplicate fig labels: {labels}"


class TestGenerateChapterJson:
    def test_valid_json(self):
        result = generate_chapter_json(_simple_chapter(), chabbr="BASCRY")
        data = json.loads(result)
        assert data["title"] == "Basic Crystallography"
        assert data["chabbr"] == "BASCRY"
        assert data["chapter_type"] == "topical"
        assert data["published"] is False

    def test_toc_from_sections(self):
        result = generate_chapter_json(_simple_chapter())
        data = json.loads(result)
        assert "Introduction" in data["toc"]
        assert "Methods" in data["toc"]

    def test_authors(self):
        result = generate_chapter_json(_simple_chapter())
        data = json.loads(result)
        assert "Marc De Graef" in data["authors"]

    def test_defaults_for_empty_chapter(self):
        result = generate_chapter_json(Chapter())
        data = json.loads(result)
        assert data["title"] == "REPLACE: Your Chapter Title"
        assert data["authors"] == ["REPLACE: Your Name"]

    def test_metadata_overrides(self):
        metadata = {
            "description": "A short chapter on diffraction.",
            "keywords": ["diffraction", "crystallography"],
            "depends_on": ["BASCRY"],
            "discipline": "physics",
            "published": True,
            "unknown_key": "ignored",
        }
        result = generate_chapter_json(
            _simple_chapter(), chabbr="BASCRY", metadata=metadata
        )
        data = json.loads(result)
        assert data["description"] == "A short chapter on diffraction."
        assert data["keywords"] == ["diffraction", "crystallography"]
        assert data["depends_on"] == ["BASCRY"]
        assert data["discipline"] == "physics"
        assert data["published"] is True
        assert "unknown_key" not in data


class TestGenerateBib:
    def test_default_bib(self):
        result = generate_bib([])
        assert "Add your references" in result or "lastnameYEAR" in result

    def test_entries(self):
        entries = [
            BibEntry(
                key="smith2026a",
                entry_type="article",
                fields={
                    "author": "Smith, John",
                    "title": "A Great Paper",
                    "journal": "Nature",
                    "year": "2026",
                },
            )
        ]
        result = generate_bib(entries)
        assert "@article{smith2026a," in result
        assert "A Great Paper" in result
        assert "Nature" in result
