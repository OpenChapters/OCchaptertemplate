# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OCconvert is a Python tool that converts documents (.docx, .pptx, .md) into LaTeX files conforming to the OpenChapters chapter template format. It lives in the `tools/occonvert/` directory of the OCchaptertemplate repository.

## Build & Run

Uses a miniconda environment named `occonvert` (Python 3.12):

```bash
conda activate occonvert
cd tools/occonvert
pip install -e ".[dev]"        # editable install with pytest
pytest tests/ -v               # run all tests (191 tests)
occonvert input.md -o output/  # CLI usage
```

## Architecture

All format parsers produce a common **Chapter IR** (`occonvert/model.py`), which the **template engine** (`occonvert/template.py`) renders into OC-compliant LaTeX. This decouples parsing from output generation.

```
Input file  -->  Format Parser  -->  Chapter IR  -->  Template Engine  -->  .tex + .json + .bib
                 (formats/*.py)      (model.py)       (template.py)
```

Key modules:
- `model.py` — dataclasses: Chapter, Section, Block types (Paragraph, Equation, Figure, Table, ListBlock, CodeBlock), Author, BibEntry
- `template.py` — generates MyChapter.tex, chapter.json, chaptercitations.bib
- `utils.py` — label slugification, `\chabbr` derivation, LaTeX escaping, InlineRun-to-LaTeX
- `converter.py` — orchestrator: detects format, calls parser, relocates images, writes output
- `cli.py` — argparse CLI entry point
- `equations.py` — OMML-to-LaTeX conversion (Pandoc preferred, built-in fallback)
- `images.py` — image extraction and raster-to-PDF conversion
- `bibtex.py` — bibliography extraction (Word customXml, Markdown refs, .bib file import)

Format parsers:
- `formats/markdown.py` — Markdown via markdown-it-py; handles front matter, math, tables, references sections
- `formats/docx.py` — Word via python-docx; walks body XML for correct paragraph/table interleaving
- `formats/pptx.py` — PowerPoint via python-pptx; slide titles become sections, speaker notes become comments

## Test Suite

191 tests across 9 test files, covering all modules:
```bash
pytest tests/ -v               # full suite
pytest tests/test_markdown.py  # single format
pytest tests/ -k "edge"        # by keyword
```

## Related Resources

- **Chapter template**: `../../chapter/MyChapter.tex`
- **Author guidelines**: `../../AuthorGuide/AuthorGuidelines.tex`
- **OC style files**: `../../style/`
- **Project spec & plan**: `OCconvert.md`

## OC LaTeX Conventions (from Author Guidelines)

- Labels: `\chabbr:TYPE:name` where TYPE is ch/sec/ssec/sssec/fig/tb/eq — no numerals, no spaces/underscores
- `\chabbr` is a 6-character uppercase code unique per chapter
- Figures must be editable PDFs in `chapter/pdf/`
- Citations use biblatex/biber; keys formatted as `lastnameYEARa`
- Tables use booktabs (\toprule, \midrule, \bottomrule)
