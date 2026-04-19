"""Tests for occonvert.utils."""

from occonvert.model import InlineRun
from occonvert.utils import (
    bib_key,
    derive_chabbr,
    escape_latex,
    make_label,
    runs_to_latex,
    slugify,
)


class TestSlugify:
    def test_basic(self):
        assert slugify("Introduction") == "introduction"

    def test_removes_numerals(self):
        assert slugify("Section 1") == "section"

    def test_removes_spaces_and_underscores(self):
        assert slugify("my_label name") == "mylabelname"

    def test_removes_special_chars(self):
        assert slugify("Héllo Wörld!") == "helloworld"

    def test_truncates_long_text(self):
        result = slugify("a" * 50)
        assert len(result) == 30

    def test_empty_string(self):
        assert slugify("") == ""


class TestMakeLabel:
    def test_section_label(self):
        label = make_label("BASCRY", "sec", "Introduction")
        assert label == r"\chabbr:sec:introduction"

    def test_figure_label(self):
        label = make_label("BASCRY", "fig", "Complex Plane")
        assert label == r"\chabbr:fig:complexplane"

    def test_empty_name(self):
        label = make_label("BASCRY", "eq", "")
        assert label == r"\chabbr:eq:unnamed"


class TestDeriveChabbr:
    def test_basic(self):
        result = derive_chabbr("Basic Crystallography")
        assert len(result) == 6
        assert result.isupper()
        assert result.isalpha()

    def test_short_title(self):
        result = derive_chabbr("AI")
        assert len(result) == 6

    def test_strips_stopwords(self):
        result = derive_chabbr("The Art of War")
        # "Art" and "War" are the significant words
        assert result[0] == "R"  # first consonant from "Art"
        assert "W" in result or "R" in result

    def test_all_vowels_title(self):
        result = derive_chabbr("Aeiou")
        assert len(result) == 6


class TestEscapeLatex:
    def test_ampersand(self):
        assert escape_latex("A & B") == r"A \& B"

    def test_percent(self):
        assert escape_latex("100%") == r"100\%"

    def test_hash(self):
        assert escape_latex("#1") == r"\#1"

    def test_underscore(self):
        assert escape_latex("var_name") == r"var\_name"

    def test_dollar(self):
        assert escape_latex("$5") == r"\$5"

    def test_plain_text_unchanged(self):
        assert escape_latex("Hello World") == "Hello World"


class TestBibKey:
    def test_basic(self):
        assert bib_key("Smith", "2026") == "smith2026a"

    def test_suffix(self):
        assert bib_key("Smith", "2026", "b") == "smith2026b"

    def test_cleans_name(self):
        assert bib_key("O'Brien", "2025") == "obrien2025a"


class TestRunsToLatex:
    def test_plain_text(self):
        runs = [InlineRun(text="Hello world")]
        assert runs_to_latex(runs) == "Hello world"

    def test_bold(self):
        runs = [InlineRun(text="bold", bold=True)]
        assert runs_to_latex(runs) == r"\textbf{bold}"

    def test_italic(self):
        runs = [InlineRun(text="italic", italic=True)]
        assert runs_to_latex(runs) == r"\textit{italic}"

    def test_bold_italic(self):
        runs = [InlineRun(text="both", bold=True, italic=True)]
        assert runs_to_latex(runs) == r"\textbf{\textit{both}}"

    def test_inline_math(self):
        runs = [InlineRun(text="E=mc^2", math=True)]
        assert runs_to_latex(runs) == "$E=mc^2$"

    def test_code(self):
        runs = [InlineRun(text="x = 1", code=True)]
        assert runs_to_latex(runs) == r"\verb|x = 1|"

    def test_href(self):
        runs = [InlineRun(text="click here", href="http://example.com")]
        result = runs_to_latex(runs)
        assert r"\href" in result
        assert "click here" in result

    def test_mixed_runs(self):
        runs = [
            InlineRun(text="Hello "),
            InlineRun(text="world", bold=True),
            InlineRun(text="!"),
        ]
        assert runs_to_latex(runs) == r"Hello \textbf{world}!"

    def test_superscript(self):
        runs = [InlineRun(text="2", superscript=True)]
        assert runs_to_latex(runs) == r"\textsuperscript{2}"
