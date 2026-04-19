# OCconvert

A Python tool that converts existing documents into LaTeX chapter files following the [OpenChapters](https://github.com/OpenChapters) template format.

Authors often have course notes in Word, PowerPoint, or Markdown that they'd like to contribute as an OpenChapters chapter. Manually reformatting these into the OC LaTeX template is tedious. OCconvert automates the structural conversion, producing a first-draft `.tex` file, `chapter.json`, and `chaptercitations.bib` that the author can then edit and refine.

## Supported Input Formats

| Format | Extension | What converts well | What needs manual editing |
|--------|-----------|-------------------|--------------------------|
| **Markdown** | `.md` | Headings, bold/italic/code, math (`$...$`, `$$...$$`), tables, lists, images, links, code blocks, references section | Learning objectives, index entries, figure quality |
| **Word** | `.docx` | Heading styles, bold/italic/sub/superscript, tables, lists (bullet & numbered), images, OMML equations, bibliography (citation manager) | Equation review, editable PDF figures, index entries |
| **PowerPoint** | `.pptx` | Slide titles as sections, bullet lists, tables, images, bold/italic, speaker notes (as LaTeX comments) | Expanding slides into prose, figures, index entries |

### Always requires author attention

- Learning objectives (pedagogical content)
- The 6-character `\chabbr` abbreviation code
- Editable PDF figures (extracted raster images are placeholders)
- Cross-chapter references
- Index entries (`\index{}`, `\indexit{}`)
- Chapter header image (2480 x 1240 px)

## Installation

```bash
# Create and activate a conda environment
conda create -n occonvert python=3.12 -y
conda activate occonvert

# Install the package (from the tools/occonvert directory)
cd tools/occonvert
pip install -e .

# Or use the environment file
conda env create -f environment.yml
conda activate occonvert
```

Alternatively, install with test dependencies:

```bash
pip install -e ".[dev]"
```

## Usage

```bash
# Basic conversion
occonvert my_notes.md

# Specify output directory and chapter abbreviation
occonvert lecture_slides.pptx -o ../chapter --chabbr FLUIDY

# Override the chapter title
occonvert paper_draft.docx --title "Introduction to Fluid Dynamics"
```

### Options

```
positional arguments:
  input                 Input file (.md, .docx, or .pptx)

options:
  -o, --output-dir DIR  Output directory (default: ./output)
  --chabbr CODE         6-character chapter abbreviation (auto-derived if omitted)
  --title TEXT           Override the chapter title
```

### Output

OCconvert generates three files in the output directory:

```
output/
└── chapter/
    ├── MyChapter.tex          LaTeX chapter file (OC template format)
    ├── chapter.json           Metadata for the OC web interface
    ├── chaptercitations.bib   Bibliography entries
    └── pdf/                   Extracted/converted figures
```

The generated `.tex` file includes TODO comments marking items that need author attention. A summary checklist appears at the end of the file.

## Running Tests

```bash
conda activate occonvert
cd tools/occonvert
pytest tests/ -v
```

## Dependencies

| Package | Purpose |
|---------|---------|
| `markdown-it-py` | Markdown parsing |
| `python-docx` | Word .docx parsing |
| `python-pptx` | PowerPoint .pptx parsing |
| `Pillow` | Image format detection |
| `img2pdf` | Raster-to-PDF conversion |
| `lxml` | XML processing (OMML equations, Word bibliography) |

Optional: [Pandoc](https://pandoc.org/) (system install) improves equation conversion quality for Word/PowerPoint documents. The tool works without it using a built-in converter.

## Architecture

```
Input file ──> Format Parser ──> Chapter IR ──> Template Engine ──> .tex + .json + .bib
               (formats/*.py)    (model.py)     (template.py)
```

All format-specific parsers produce a common intermediate representation (the `Chapter` dataclass in `model.py`), which the template engine renders into OC-compliant LaTeX. This makes it straightforward to add new input formats.

## License

Licensed under the [Creative Commons CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) License, consistent with the OpenChapters project.
