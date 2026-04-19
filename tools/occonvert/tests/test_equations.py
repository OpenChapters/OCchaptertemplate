"""Tests for OMML-to-LaTeX equation conversion."""

import pytest
from lxml import etree

from occonvert.equations import _builtin_convert, omml_to_latex

_M = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def _omml(xml_body: str):
    """Wrap an OMML fragment in the proper namespace and parse it."""
    xml = f'<m:oMath xmlns:m="{_M}">{xml_body}</m:oMath>'
    return etree.fromstring(xml.encode())


class TestBuiltinFraction:
    def test_simple_fraction(self):
        el = _omml(
            f'<m:f><m:num><m:r><m:t>a</m:t></m:r></m:num>'
            f'<m:den><m:r><m:t>b</m:t></m:r></m:den></m:f>'
        )
        result = _builtin_convert(el)
        assert r"\frac{a}{b}" in result

    def test_nested_fraction(self):
        el = _omml(
            '<m:f>'
            '  <m:num><m:r><m:t>x</m:t></m:r></m:num>'
            '  <m:den>'
            '    <m:f>'
            '      <m:num><m:r><m:t>y</m:t></m:r></m:num>'
            '      <m:den><m:r><m:t>z</m:t></m:r></m:den>'
            '    </m:f>'
            '  </m:den>'
            '</m:f>'
        )
        result = _builtin_convert(el)
        assert r"\frac" in result
        assert "x" in result
        assert "y" in result
        assert "z" in result


class TestBuiltinSuperscript:
    def test_simple_superscript(self):
        el = _omml(
            '<m:sSup>'
            '  <m:e><m:r><m:t>x</m:t></m:r></m:e>'
            '  <m:sup><m:r><m:t>2</m:t></m:r></m:sup>'
            '</m:sSup>'
        )
        result = _builtin_convert(el)
        assert "x" in result
        assert "^" in result
        assert "2" in result


class TestBuiltinSubscript:
    def test_simple_subscript(self):
        el = _omml(
            '<m:sSub>'
            '  <m:e><m:r><m:t>x</m:t></m:r></m:e>'
            '  <m:sub><m:r><m:t>i</m:t></m:r></m:sub>'
            '</m:sSub>'
        )
        result = _builtin_convert(el)
        assert "x" in result
        assert "_" in result
        assert "i" in result


class TestBuiltinRadical:
    def test_square_root(self):
        el = _omml(
            '<m:rad>'
            '  <m:deg/>'
            '  <m:e><m:r><m:t>x</m:t></m:r></m:e>'
            '</m:rad>'
        )
        result = _builtin_convert(el)
        assert r"\sqrt" in result
        assert "x" in result

    def test_nth_root(self):
        el = _omml(
            '<m:rad>'
            '  <m:deg><m:r><m:t>3</m:t></m:r></m:deg>'
            '  <m:e><m:r><m:t>x</m:t></m:r></m:e>'
            '</m:rad>'
        )
        result = _builtin_convert(el)
        assert r"\sqrt[3]" in result


class TestBuiltinRun:
    def test_plain_text(self):
        el = _omml('<m:r><m:t>abc</m:t></m:r>')
        result = _builtin_convert(el)
        assert "abc" in result

    def test_multiple_text_nodes(self):
        el = _omml('<m:r><m:t>a</m:t><m:t>b</m:t></m:r>')
        result = _builtin_convert(el)
        assert "ab" in result


class TestBuiltinOmath:
    def test_omath_container(self):
        el = _omml(
            '<m:r><m:t>E</m:t></m:r>'
            '<m:r><m:t>=</m:t></m:r>'
            '<m:r><m:t>mc</m:t></m:r>'
        )
        result = _builtin_convert(el)
        assert "E" in result
        assert "=" in result
        assert "mc" in result

    def test_empty_element(self):
        el = _omml('')
        result = _builtin_convert(el)
        assert result == ""


class TestOmmlToLatex:
    def test_falls_back_to_builtin(self):
        """When Pandoc is not available, should fall back to builtin converter."""
        el = _omml('<m:r><m:t>x</m:t></m:r>')
        result = omml_to_latex(el)
        assert "x" in result

    def test_fraction_through_api(self):
        el = _omml(
            '<m:f>'
            '  <m:num><m:r><m:t>1</m:t></m:r></m:num>'
            '  <m:den><m:r><m:t>2</m:t></m:r></m:den>'
            '</m:f>'
        )
        result = omml_to_latex(el)
        assert "1" in result
        assert "2" in result
