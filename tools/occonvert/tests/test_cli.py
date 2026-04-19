"""Tests for the CLI interface."""

from pathlib import Path

import pytest

from occonvert.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


class TestCliValidation:
    def test_missing_input_file(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main(["nonexistent.md"])
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err

    def test_unsupported_format(self, tmp_path, capsys):
        txt = tmp_path / "test.txt"
        txt.write_text("hello")
        with pytest.raises(SystemExit) as exc:
            main([str(txt)])
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "unsupported" in captured.err.lower()

    def test_invalid_chabbr_too_short(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main([str(FIXTURES / "simple.md"), "--chabbr", "ABC"])
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "6 alphabetic" in captured.err

    def test_invalid_chabbr_with_digits(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main([str(FIXTURES / "simple.md"), "--chabbr", "ABC123"])
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "6 alphabetic" in captured.err


class TestCliMarkdown:
    def test_basic_conversion(self, tmp_path, capsys):
        main([str(FIXTURES / "simple.md"), "-o", str(tmp_path)])
        captured = capsys.readouterr()
        assert "Generated:" in captured.out
        assert (tmp_path / "chapter" / "MyChapter.tex").exists()
        assert (tmp_path / "chapter" / "chapter.json").exists()
        assert (tmp_path / "chapter" / "chaptercitations.bib").exists()

    def test_with_chabbr(self, tmp_path):
        main([str(FIXTURES / "simple.md"), "-o", str(tmp_path), "--chabbr", "FNTELM"])
        tex = (tmp_path / "chapter" / "MyChapter.tex").read_text()
        assert "FNTELM" in tex

    def test_with_title_override(self, tmp_path):
        main([
            str(FIXTURES / "simple.md"), "-o", str(tmp_path),
            "--title", "Custom Title",
        ])
        tex = (tmp_path / "chapter" / "MyChapter.tex").read_text()
        assert "Custom Title" in tex

    def test_chabbr_uppercased(self, tmp_path):
        main([str(FIXTURES / "simple.md"), "-o", str(tmp_path), "--chabbr", "fntelm"])
        tex = (tmp_path / "chapter" / "MyChapter.tex").read_text()
        assert "FNTELM" in tex


class TestCliDocx:
    def test_basic_conversion(self, tmp_path):
        main([str(FIXTURES / "simple.docx"), "-o", str(tmp_path)])
        assert (tmp_path / "chapter" / "MyChapter.tex").exists()
        tex = (tmp_path / "chapter" / "MyChapter.tex").read_text()
        assert r"\chapter{Finite Element Methods}" in tex


class TestCliPptx:
    def test_basic_conversion(self, tmp_path):
        main([str(FIXTURES / "simple.pptx"), "-o", str(tmp_path)])
        assert (tmp_path / "chapter" / "MyChapter.tex").exists()
        tex = (tmp_path / "chapter" / "MyChapter.tex").read_text()
        assert r"\chapter{Finite Element Methods}" in tex
