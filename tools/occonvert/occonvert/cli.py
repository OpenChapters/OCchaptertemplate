"""Command-line interface for OCconvert."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .converter import SUPPORTED_EXTENSIONS, convert


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="occonvert",
        description="Convert documents to OpenChapters LaTeX format.",
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Input file (.md, .docx, or .pptx)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: ./output)",
    )
    parser.add_argument(
        "--chabbr",
        type=str,
        default=None,
        help="6-character chapter abbreviation (auto-derived from title if omitted)",
    )
    parser.add_argument(
        "--title",
        type=str,
        default=None,
        help="Override the chapter title",
    )

    args = parser.parse_args(argv)

    # Validate input
    if not args.input.exists():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    ext = args.input.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        print(
            f"Error: unsupported format '{ext}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.chabbr and (len(args.chabbr) != 6 or not args.chabbr.isalpha()):
        print(
            "Error: --chabbr must be exactly 6 alphabetic characters (e.g. LINALG)",
            file=sys.stderr,
        )
        sys.exit(1)

    output_dir = args.output_dir or Path("output")
    chabbr = args.chabbr.upper() if args.chabbr else None

    try:
        tex_path = convert(args.input, output_dir, chabbr=chabbr, title=args.title)
        print(f"Generated: {tex_path}")
        print(f"  chapter.json: {tex_path.parent / 'chapter.json'}")
        print(f"  bibliography: {tex_path.parent / 'chaptercitations.bib'}")
        print(f"  figures dir:  {tex_path.parent / 'pdf/'}")
        print()
        print("Review the TODO comments in MyChapter.tex for items requiring attention.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
