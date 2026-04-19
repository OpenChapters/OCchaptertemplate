## OCconvert ##

In the folder ../OCchaptertemplate you will find a main.tex file that controls typesetting of an individual chapter.  The LaTeX template for such a chapter can be found in the folder ../OCchaptertemplate/chapter and is called MyChapter.tex.  Author guidelines can be found in ../OCchaptertemplate/AuthorGuide/AuthorGuidelines.tex and .pdf for the formatted version. It can be a tedious task to manually convert an existing document (in one of the following formats: Word: .docx; PowerPoint: .pptx; MarkDown: .md; or KeyNote: .key) into a LaTeX formatted chapter, so it could be useful for inexperienced LaTeX authors to have a tool (likely python) that would take the existing document and convert it into a LaTeX file that follows the author guidelines; this file will then need to be edited by the author, but having a starting point in the correct format could be a real time saver.  Please evaluate whether or not this is a feasible project, and, if it is, please create a detailed implementation plan.

---

## Feasibility Evaluation

**Verdict: Yes, this is feasible.** A Python tool can produce a useful first-draft LaTeX file for each of the four input formats. The output will always require human editing — equations will need checking, figures will need to be redrawn as editable PDFs, and learning objectives must be written by the author — but the tool can handle the bulk of the structural conversion and save substantial time.

Below is a per-format assessment, followed by the implementation plan.

### Format-by-Format Assessment

#### Markdown (.md) — Easiest

Markdown maps almost directly onto LaTeX. Headings become `\section`/`\subsection`, bold/italic map to `\textbf`/`\textit`, inline code maps to `\verb`, lists map to `itemize`/`enumerate`, and many authors already write LaTeX math inside Markdown (`$...$` and `$$...$$`). Images have explicit paths. Tables have a well-defined syntax. The Python `markdown-it-py` parser (or similar) produces an AST that can be walked to emit OC-formatted LaTeX directly.

**Confidence: High.** Very little information is lost.

#### Word (.docx) — Moderate

A `.docx` file is a ZIP containing XML (`word/document.xml`). The `python-docx` library exposes paragraphs, runs (with bold/italic/font info), tables, and inline images. Key challenges:

- **Equations**: Word uses OMML (Office Math Markup Language). The open-source XSLT stylesheet `OMML2MML.XSL` (ships with every Office install) converts OMML to MathML, and the Python package `latex2mathml` (or its inverse pathway via `mml2tex`) can then convert to LaTeX. Alternatively, Pandoc's OMML-to-LaTeX path is mature and could be called as a subprocess. Equation conversion is imperfect — complex multi-line equations will need author review.
- **Images**: Embedded images can be extracted from the ZIP (`word/media/`). They will typically be PNG/JPEG and will need to be converted to PDF (trivially done via Pillow or `img2pdf`). However, per the Author Guidelines, figures must be *editable* PDFs, so extracted raster images are placeholders at best — the author must redraw them.
- **Structure**: Heading styles (Heading 1, Heading 2, ...) map to `\section`, `\subsection`, etc. Documents without heading styles will fall back to font-size heuristics, which is less reliable.

**Confidence: Moderate.** The structural skeleton and plain text will be good; equations will be approximate; images will be placeholders.

#### PowerPoint (.pptx) — Moderate, with Caveats

A `.pptx` is also a ZIP with XML. The `python-pptx` library provides access to slides, shapes, text frames, tables, and images. Challenges:

- **Structure mapping**: Slides don't have a natural hierarchy. The tool can treat each slide title as a `\section` or `\subsection`, and bullet-point text as `itemize` items or as prose paragraphs.
- **Equations**: PowerPoint equations are OMML, same as Word — same conversion path.
- **Images**: Same as Word — extractable but raster.
- **Layout**: Spatial layout (side-by-side text boxes, overlapping shapes, animations) does not translate to LaTeX. The tool should linearize content in reading order (title first, then content shapes top-to-bottom, left-to-right).
- **Speaker notes**: Could optionally be included as LaTeX comments, which may be useful source material for the author when expanding slides into chapter prose.

**Confidence: Moderate.** Useful as a content extraction and skeleton tool, but slide decks are inherently terse — the author will need to write significant additional prose.

#### Keynote (.key) — Hardest, but Still Feasible

Keynote files are ZIP archives containing an IWA (iWork Archive) protobuf-based binary format. Apple does not publish the format specification. Approaches:

- **Primary approach**: Export to an intermediate format first. Keynote can export to PPTX from the command line on macOS via AppleScript/`osascript`: `osascript -e 'tell application "Keynote" to export ...'`. The tool can automate this, then process the resulting PPTX. This is by far the most reliable path.
- **Fallback approach**: Export Keynote to PDF, then extract text and images from the PDF. This loses structure but captures content.
- **Direct parsing**: Libraries like `iWorkFileFormat` exist but are incomplete and fragile. Not recommended for production use.

**Confidence: Moderate** (via PPTX intermediary on macOS); **Low** if direct parsing is attempted.

### What the Tool Cannot Do Automatically

Regardless of input format, the following will always require human input:

1. **Learning Objectives**: These are pedagogical content that must be written by the author.
2. **Chapter abbreviation (`\chabbr`)**: The 6-character code is a creative/editorial decision.
3. **Label names**: Auto-generated labels (e.g., `\chabbr:sec:introduction`) will be reasonable guesses from heading text, but may need refinement.
4. **Cross-chapter references**: References to other OC chapters require knowing the target chapter's `\chabbr`.
5. **Editable PDF figures**: Raster images extracted from source documents are placeholders only.
6. **Citation keys**: The tool can extract reference lists and generate `.bib` entries, but matching to existing DOIs and formatting keys as `lastnameYEARa` will require author verification.
7. **Index entries**: The tool has no way to know which terms should be indexed.
8. **Header image**: The 2480x1240 chapter header image must be created by the author.

---

## Detailed Implementation Plan

### Project Structure

```
OCconvert/
    occonvert/
        __init__.py
        cli.py                  # command-line interface
        converter.py            # main orchestrator
        template.py             # OC LaTeX template generation
        formats/
            __init__.py
            markdown.py         # .md parser and converter
            docx.py             # .docx parser and converter
            pptx.py             # .pptx parser and converter
            keynote.py          # .key handler (export via applescript, then pptx)
        equations.py            # OMML/MathML to LaTeX conversion
        images.py               # image extraction and PDF conversion
        bibtex.py               # bibliography extraction and .bib generation
        utils.py                # slugify, label generation, text cleaning
    tests/
        test_markdown.py
        test_docx.py
        test_pptx.py
        test_keynote.py
        test_template.py
        test_equations.py
        fixtures/               # sample input files for testing
    pyproject.toml
    README.md
```

### Phase 1: Core Infrastructure and Template Engine

**Goal**: Build the internal document representation and the LaTeX output engine.

#### 1.1 Internal Document Model

Define a simple intermediate representation (IR) that all parsers produce. This decouples parsing from LaTeX generation.

```python
@dataclass
class Chapter:
    title: str
    authors: list[Author]
    sections: list[Section]
    bibliography: list[BibEntry]
    images: list[ImageAsset]

@dataclass
class Author:
    first: str
    last: str
    department: str
    institution: str
    email: str
    url: str

@dataclass
class Section:
    title: str
    level: int              # 1=section, 2=subsection, 3=subsubsection
    content: list[Block]    # paragraphs, equations, figures, tables, lists

@dataclass
class Block:
    kind: str               # "paragraph", "equation", "figure", "table",
                            # "itemize", "enumerate", "code"
    content: ...            # varies by kind
```

#### 1.2 LaTeX Template Generator (`template.py`)

This module takes a `Chapter` object and emits a complete `MyChapter.tex` file following the OC format. It generates:

- The copyright header block (with REPLACE placeholders for author name)
- `\OCchapterauthor{}` from the Author data
- `\renewcommand{\chabbr}{XXXXXX}` with a 6-character abbreviation auto-derived from the chapter title (first 6 consonants, uppercased), marked with a TODO comment
- `\chapterimage{\noheaderimage}` (always, since no header image can be auto-generated)
- `\chapter{Title}\label{\chabbr:ch:ChapterName}`
- `\writeauthor{...}{...}{...}{...}{...}{...}{...}{...}` for each author
- A `learningobjectives` skeleton with one entry per section, using placeholder verbs and the correct label format, marked with TODO comments
- All sections/subsections with auto-generated labels following the `\chabbr:TYPE:name` convention
- Figures with `\includegraphics` pointing to `\graphicspath filename.pdf` and `\label{\chabbr:fig:name}`
- Tables with `booktabs` formatting (`\toprule`, `\midrule`, `\bottomrule`) and `\label{\chabbr:tb:name}`
- Equations with `\label{\chabbr:eq:name}`
- A `TODO` comment at the end of the file listing items requiring author attention

It also generates:

- A `chapter.json` file with fields populated from the parsed content
- A `chaptercitations.bib` file from extracted references

#### 1.3 Label Generation (`utils.py`)

Labels are generated from heading/caption text by:
1. Lowercasing
2. Removing non-alphanumeric characters (no spaces, no underscores, no numerals per guidelines)
3. Truncating to a reasonable length
4. Prepending `\chabbr:TYPE:`

Example: "The Finite Element Method" -> `\chabbr:sec:thefiniteelementmethod`

#### 1.4 CLI (`cli.py`)

```
occonvert input_file.docx [--output-dir ./output] [--chabbr FELEME] 
          [--author-first John --author-last Smith ...] [--title "My Chapter"]
```

The CLI:
- Detects input format from extension
- Calls the appropriate parser to produce a `Chapter` IR
- Calls the template generator to emit the output files
- Creates the output directory structure matching the OCchaptertemplate layout:
  ```
  output/
      chapter/
          MyChapter.tex
          chaptercitations.bib
          chapter.json
          pdf/
              (extracted/converted figures)
  ```

### Phase 2: Markdown Converter

**Goal**: The simplest converter; validates the full pipeline end-to-end.

#### 2.1 Parser (`formats/markdown.py`)

Use `markdown-it-py` to parse the Markdown AST. Walk the token stream and build the `Chapter` IR:

| Markdown element | IR Block kind |
|---|---|
| `# Heading` | Section (level from heading level) |
| Paragraph text | `paragraph` with inline formatting |
| `$...$` / `$$...$$` | Inline math kept as-is / `equation` block |
| `![alt](path)` | `figure` with image path and alt as caption |
| `|table|` | `table` |
| `- item` / `1. item` | `itemize` / `enumerate` |
| `` `code` `` / ```` ```code``` ```` | Inline verb / `code` block |
| `> blockquote` | `messagebox` (informational box) |
| `[text](url)` | `\href{url}{text}` |
| `**bold**` / `*italic*` | `\textbf{}` / `\textit{}` |

#### 2.2 Special handling

- YAML front matter (`---` blocks): Extract `title`, `author`, `date` if present.
- Footnotes: Convert to `\footnote{}`.
- LaTeX pass-through: If the Markdown contains raw LaTeX (common in academic Markdown), preserve it unchanged.

### Phase 3: Word (.docx) Converter

#### 3.1 Parser (`formats/docx.py`)

Use `python-docx` to iterate through the document:

- **Paragraphs**: Check `paragraph.style.name` for heading levels (`Heading 1`, `Heading 2`, etc.). Normal paragraphs become `paragraph` blocks.
- **Runs**: Iterate `paragraph.runs` to detect bold, italic, subscript, superscript, and map to LaTeX commands.
- **Tables**: `document.tables` provides cell-by-cell access. Convert to `tabular` with `booktabs`.
- **Images**: Inline shapes (`paragraph.runs` containing `InlineShape`) have their image data in the `.docx` ZIP. Extract and save.

#### 3.2 Equation Handling (`equations.py`)

Word equations are stored as OMML in the XML. `python-docx` does not expose these directly, so:

1. Parse the raw XML of each paragraph (`paragraph._element.xml`)
2. Find `<m:oMath>` and `<m:oMathPara>` elements
3. Convert OMML to LaTeX using one of:
   - **Option A (preferred)**: Use the `omml2latex` Python package or the `OMML2MML.XSL` + `mml2tex` pipeline
   - **Option B (fallback)**: Call Pandoc as a subprocess on the paragraph XML fragment
4. Inline equations become `$...$`; display equations become `\begin{equation}...\end{equation}`

#### 3.3 Image Extraction (`images.py`)

1. Extract images from `word/media/` in the ZIP
2. Determine original format (PNG, JPEG, EMF, WMF)
3. Convert raster images to PDF using `Pillow` + `img2pdf`
4. For EMF/WMF (vector): use `inkscape` CLI if available, or `libreoffice --convert-to pdf`, otherwise keep as raster fallback
5. Place converted PDFs in `chapter/pdf/`
6. Add a TODO comment in the LaTeX noting that figures should be replaced with editable originals

### Phase 4: PowerPoint (.pptx) Converter

#### 4.1 Parser (`formats/pptx.py`)

Use `python-pptx` to iterate slides:

- **Slide titles**: The title placeholder shape on each slide becomes a `\section` or `\subsection`
- **Structure heuristic**: If slide titles show clear hierarchy patterns (e.g., "1. Introduction", "1.1 Background"), parse the numbering to determine section levels. Otherwise, treat all slides as sections.
- **Text content**: Iterate non-title shapes sorted by vertical position (top to bottom), then horizontal (left to right). Text frames become paragraphs; bulleted lists become `itemize`.
- **Tables**: `python-pptx` provides table shape access, same conversion as docx.
- **Images**: Extract from slide shapes; same pipeline as docx.
- **Equations**: Same OMML handling as docx.
- **Speaker notes**: If present, include as LaTeX comments (`% NOTE: ...`) after the corresponding section.

#### 4.2 Slide-to-Chapter Logic

Since slide decks are terse, the converter should:
- Add a TODO comment after each section: `% TODO: Expand slide content into full prose`
- Convert bullet points to `itemize` but also add a comment suggesting the author may want to convert these to flowing paragraphs
- Group consecutive slides with no title change under the same section

### Phase 5: Keynote (.key) Converter

#### 5.1 Handler (`formats/keynote.py`)

The primary strategy is conversion via an intermediate format:

1. **Check if Keynote is available** (macOS only): test for `/Applications/Keynote.app`
2. **Export to PPTX** via AppleScript:
   ```python
   subprocess.run([
       "osascript", "-e",
       f'tell application "Keynote" to export '
       f'(open POSIX file "{abspath}") to POSIX file "{pptx_path}" as Microsoft PowerPoint'
   ])
   ```
3. **Delegate to the PPTX converter** from Phase 4
4. **Clean up** the temporary PPTX file

If Keynote is not installed (e.g., running on Linux), the tool should:
- Print a clear error message explaining that `.key` files require macOS with Keynote installed
- Suggest the user export to PPTX manually from Keynote and then run the tool on the PPTX

### Phase 6: Bibliography Handling

#### 6.1 BibTeX Generator (`bibtex.py`)

- **From Word/PPTX**: Extract bibliography entries from Word's built-in citation manager (stored in `customXml/` in the ZIP) if present. Convert to BibTeX entries with keys formatted as `lastnameYEARa`.
- **From Markdown**: If a `## References` section exists, attempt to parse each entry. If a `.bib` file is referenced, copy it.
- **From all formats**: For each generated `.bib` entry, add a `% TODO: add DOI` comment if no DOI is present.
- Write the result to `chaptercitations.bib`.

### Phase 7: Testing

#### 7.1 Test Strategy

- **Unit tests**: One test file per format, using small fixture files in `tests/fixtures/`
- **Template tests**: Verify that the LaTeX output compiles without errors using `pdflatex` (if available in CI)
- **Round-trip sanity check**: For Markdown, verify that the original structure is preserved through parse -> IR -> LaTeX
- **Equation tests**: A fixture with common equation patterns (fractions, matrices, integrals, Greek letters) to verify OMML-to-LaTeX accuracy

#### 7.2 Fixture Files

Create minimal test documents:
- `tests/fixtures/simple.md` — headings, paragraphs, math, a figure, a table
- `tests/fixtures/simple.docx` — same content in Word format
- `tests/fixtures/simple.pptx` — a 5-slide deck with titles, bullets, an image, an equation
- `tests/fixtures/equations.docx` — a document heavy on equations to stress-test OMML conversion

### Phase 8: Packaging and Documentation

- `pyproject.toml` with dependencies: `markdown-it-py`, `python-docx`, `python-pptx`, `Pillow`, `img2pdf`, `lxml`
- Entry point: `occonvert` CLI command
- `README.md` with usage examples and a table showing what converts well vs. what needs manual editing per format

### Dependencies

| Package | Purpose | PyPI |
|---|---|---|
| `markdown-it-py` | Markdown parsing | yes |
| `python-docx` | .docx parsing | yes |
| `python-pptx` | .pptx parsing | yes |
| `Pillow` | Image format detection/conversion | yes |
| `img2pdf` | Raster image to PDF conversion | yes |
| `lxml` | XML/XSLT processing for OMML | yes |

Optional: `pandoc` (system install) as a fallback for equation conversion.

### Suggested Build Order

| Order | Phase | Rationale |
|---|---|---|
| 1 | Core IR + Template Engine + CLI | Foundation everything else builds on |
| 2 | Markdown converter | Simplest format; validates the full pipeline |
| 3 | Word converter | Highest demand (most authors have .docx) |
| 4 | PowerPoint converter | Shares equation/image code with Word |
| 5 | Keynote converter | Thin wrapper around PPTX converter |
| 6 | Bibliography handling | Can be refined incrementally |
| 7 | Testing + polish | Comprehensive test suite |
| 8 | Packaging | Make it installable and distributable |

### Summary

The project is feasible and well-scoped for a Python tool. The Markdown and Word converters will produce the highest-quality output. The PowerPoint and Keynote converters will produce useful structural skeletons that require more author effort to flesh out. In all cases, the tool's value proposition is clear: it eliminates the mechanical work of setting up the OC template structure, generating labels, formatting sections, and converting basic content — letting the author focus on the pedagogical and editorial work that only a human can do.
