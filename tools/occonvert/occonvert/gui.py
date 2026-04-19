"""Tkinter GUI for OCconvert.

Single-window form that lets a user pick an input document, edit the
chapter.json metadata fields in a form, and run the conversion.

Run via the ``occonvert-gui`` entry point (see pyproject.toml) or:

    python -m occonvert.gui
"""

from __future__ import annotations

import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .converter import SUPPORTED_EXTENSIONS, convert, parse_only
from .model import Author, Chapter, Section
from .utils import derive_chabbr

DISCIPLINES = ["mse", "physics", "chemistry", "math", "biology", "other"]


class ConvertGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("OCconvert")
        self.root.geometry("720x780")

        # State
        self.input_path: Path | None = None
        self.output_dir = tk.StringVar(value=str(Path.cwd() / "output"))
        self.parsed_chapter: Chapter | None = None
        self._toc_sections: list[Section] = []  # parallel to lst_toc entries
        self._result_queue: queue.Queue = queue.Queue()

        # Form variables
        self.var_title = tk.StringVar()
        self.var_chabbr = tk.StringVar()
        self.var_chapter_type = tk.StringVar(value="topical")
        self.var_discipline = tk.StringVar(value="mse")
        self.var_entry_file = tk.StringVar(value="MyChapter.tex")
        self.var_cover_image = tk.StringVar(value="cover.png")
        self.var_published = tk.BooleanVar(value=False)

        self._build_ui()
        self.root.after(100, self._poll_results)

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}

        # --- Input / output row ------------------------------------------------
        io_frame = ttk.LabelFrame(self.root, text="Files")
        io_frame.pack(fill="x", **pad)

        ttk.Label(io_frame, text="Input file:").grid(row=0, column=0, sticky="e", **pad)
        self.input_label = ttk.Label(io_frame, text="(none selected)", foreground="gray")
        self.input_label.grid(row=0, column=1, sticky="w", **pad)
        ttk.Button(io_frame, text="Browse…", command=self._pick_input).grid(
            row=0, column=2, **pad
        )

        ttk.Label(io_frame, text="Output dir:").grid(row=1, column=0, sticky="e", **pad)
        ttk.Entry(io_frame, textvariable=self.output_dir, width=50).grid(
            row=1, column=1, sticky="we", **pad
        )
        ttk.Button(io_frame, text="Browse…", command=self._pick_output).grid(
            row=1, column=2, **pad
        )
        io_frame.columnconfigure(1, weight=1)

        # --- Scrollable form --------------------------------------------------
        form_outer = ttk.LabelFrame(self.root, text="chapter.json fields")
        form_outer.pack(fill="both", expand=True, **pad)

        canvas = tk.Canvas(form_outer, borderwidth=0, highlightthickness=0)
        vscroll = ttk.Scrollbar(form_outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vscroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        form = ttk.Frame(canvas)
        form_window = canvas.create_window((0, 0), window=form, anchor="nw")

        def _on_form_config(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(form_window, width=event.width)

        form.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(form_window, width=e.width),
        )

        row = 0

        def label(text: str) -> None:
            nonlocal row
            ttk.Label(form, text=text).grid(row=row, column=0, sticky="ne", **pad)

        # Title
        label("Title:")
        ttk.Entry(form, textvariable=self.var_title).grid(
            row=row, column=1, sticky="we", **pad
        )
        row += 1

        # Chabbr
        label("Chabbr (6 letters):")
        ttk.Entry(form, textvariable=self.var_chabbr, width=10).grid(
            row=row, column=1, sticky="w", **pad
        )
        row += 1

        # Authors (multi-line: one "First Last" per line)
        label("Authors (one per line):")
        self.txt_authors = tk.Text(form, height=4, width=50)
        self.txt_authors.grid(row=row, column=1, sticky="we", **pad)
        row += 1

        # Description
        label("Description:")
        self.txt_description = tk.Text(form, height=4, width=50)
        self.txt_description.grid(row=row, column=1, sticky="we", **pad)
        row += 1

        # Keywords
        label("Keywords (one per line):")
        self.txt_keywords = tk.Text(form, height=3, width=50)
        self.txt_keywords.grid(row=row, column=1, sticky="we", **pad)
        row += 1

        # Chapter type
        label("Chapter type:")
        type_frame = ttk.Frame(form)
        type_frame.grid(row=row, column=1, sticky="w", **pad)
        ttk.Radiobutton(
            type_frame, text="topical", variable=self.var_chapter_type, value="topical"
        ).pack(side="left", padx=(0, 12))
        ttk.Radiobutton(
            type_frame,
            text="foundational",
            variable=self.var_chapter_type,
            value="foundational",
        ).pack(side="left")
        row += 1

        # Depends on
        label("Depends on (one chabbr per line):")
        self.txt_depends_on = tk.Text(form, height=3, width=50)
        self.txt_depends_on.grid(row=row, column=1, sticky="we", **pad)
        row += 1

        # Discipline
        label("Discipline:")
        ttk.Combobox(
            form,
            textvariable=self.var_discipline,
            values=DISCIPLINES,
            width=20,
        ).grid(row=row, column=1, sticky="w", **pad)
        row += 1

        # entry_file
        label("Entry file:")
        ttk.Entry(form, textvariable=self.var_entry_file).grid(
            row=row, column=1, sticky="we", **pad
        )
        row += 1

        # cover_image
        label("Cover image:")
        ttk.Entry(form, textvariable=self.var_cover_image).grid(
            row=row, column=1, sticky="we", **pad
        )
        row += 1

        # Published
        label("Published:")
        ttk.Checkbutton(form, variable=self.var_published).grid(
            row=row, column=1, sticky="w", **pad
        )
        row += 1

        # TOC — editable: double-click to rename, Remove button to drop
        label("TOC (sections):")
        toc_frame = ttk.Frame(form)
        toc_frame.grid(row=row, column=1, sticky="we", **pad)
        self.lst_toc = tk.Listbox(toc_frame, height=5, exportselection=False)
        self.lst_toc.pack(side="left", fill="both", expand=True)
        self.lst_toc.bind("<Double-Button-1>", lambda e: self._toc_edit())
        toc_btns = ttk.Frame(toc_frame)
        toc_btns.pack(side="left", fill="y", padx=(6, 0))
        ttk.Button(toc_btns, text="Edit…", command=self._toc_edit).pack(fill="x")
        ttk.Button(toc_btns, text="Remove", command=self._toc_remove).pack(
            fill="x", pady=(4, 0)
        )
        row += 1

        form.columnconfigure(1, weight=1)

        # --- Convert button + status line ------------------------------------
        bottom = ttk.Frame(self.root)
        bottom.pack(fill="x", **pad)
        self.btn_convert = ttk.Button(
            bottom, text="Convert", command=self._on_convert, state="disabled"
        )
        self.btn_convert.pack(side="left", padx=8)
        self.status_var = tk.StringVar(value="Pick an input file to begin.")
        ttk.Label(bottom, textvariable=self.status_var, foreground="gray").pack(
            side="left", padx=8
        )

    # ------------------------------------------------------------ file pickers

    def _pick_input(self) -> None:
        path = filedialog.askopenfilename(
            title="Select input document",
            filetypes=[
                ("Supported", "*.md *.docx *.pptx"),
                ("Markdown", "*.md"),
                ("Word", "*.docx"),
                ("PowerPoint", "*.pptx"),
            ],
        )
        if not path:
            return
        p = Path(path)
        if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
            messagebox.showerror(
                "Unsupported format",
                f"'{p.suffix}' is not supported. Use .md, .docx, or .pptx.",
            )
            return
        self.input_path = p
        self.input_label.config(text=str(p), foreground="black")
        self.status_var.set(f"Parsing {p.name}…")
        self.btn_convert.config(state="disabled")
        threading.Thread(target=self._parse_worker, args=(p,), daemon=True).start()

    def _pick_output(self) -> None:
        path = filedialog.askdirectory(
            title="Select output directory",
            initialdir=self.output_dir.get() or str(Path.cwd()),
        )
        if path:
            self.output_dir.set(path)

    # ---------------------------------------------------------- worker threads

    def _parse_worker(self, path: Path) -> None:
        try:
            chapter = parse_only(path)
            self._result_queue.put(("parsed", chapter))
        except Exception as exc:  # noqa: BLE001 — report all parser errors
            self._result_queue.put(("parse_error", exc))

    def _convert_worker(
        self,
        input_path: Path,
        output_dir: Path,
        chabbr: str,
        metadata: dict,
        chapter: Chapter,
    ) -> None:
        try:
            tex_path = convert(
                input_path,
                output_dir,
                chabbr=chabbr,
                metadata=metadata,
                chapter=chapter,
            )
            self._result_queue.put(("converted", tex_path))
        except Exception as exc:  # noqa: BLE001
            self._result_queue.put(("convert_error", exc))

    def _poll_results(self) -> None:
        try:
            while True:
                kind, payload = self._result_queue.get_nowait()
                if kind == "parsed":
                    self._on_parsed(payload)
                elif kind == "parse_error":
                    self.status_var.set("Parse failed.")
                    messagebox.showerror("Parse error", str(payload))
                elif kind == "converted":
                    self._on_converted(payload)
                elif kind == "convert_error":
                    self.status_var.set("Conversion failed.")
                    self.btn_convert.config(state="normal")
                    messagebox.showerror("Conversion error", str(payload))
        except queue.Empty:
            pass
        self.root.after(100, self._poll_results)

    # ---------------------------------------------------------- populate form

    def _on_parsed(self, chapter: Chapter) -> None:
        self.parsed_chapter = chapter

        # Title
        self.var_title.set(chapter.title or "")

        # Chabbr
        self.var_chabbr.set(derive_chabbr(chapter.title or "MyChapter"))

        # Chapter type
        self.var_chapter_type.set(chapter.chapter_type or "topical")

        # Authors (only if form is empty — don't clobber user edits)
        self.txt_authors.delete("1.0", "end")
        for a in chapter.authors:
            name = f"{a.first} {a.last}".strip()
            if name:
                self.txt_authors.insert("end", name + "\n")

        # TOC — parallel list of Section refs so edits/removals map back
        self.lst_toc.delete(0, "end")
        self._toc_sections = []
        for s in chapter.sections:
            if s.level == 1 and s.title:
                self.lst_toc.insert("end", s.title)
                self._toc_sections.append(s)

        self.btn_convert.config(state="normal")
        self.status_var.set(f"Parsed {len(chapter.sections)} section(s). Review fields and Convert.")

    # ------------------------------------------------------------ TOC editing

    def _toc_edit(self) -> None:
        sel = self.lst_toc.curselection()
        if not sel:
            return
        idx = sel[0]
        current = self.lst_toc.get(idx)
        new = simpledialog.askstring(
            "Rename section",
            "Section title:",
            initialvalue=current,
            parent=self.root,
        )
        if new is None:
            return
        new = new.strip()
        if not new:
            return
        self.lst_toc.delete(idx)
        self.lst_toc.insert(idx, new)
        self.lst_toc.selection_set(idx)
        self._toc_sections[idx].title = new

    def _toc_remove(self) -> None:
        sel = self.lst_toc.curselection()
        if not sel:
            return
        idx = sel[0]
        self.lst_toc.delete(idx)
        self._toc_sections.pop(idx)

    def _on_converted(self, tex_path: Path) -> None:
        self.status_var.set(f"Done: {tex_path}")
        self.btn_convert.config(state="normal")
        out_dir = tex_path.parent
        if messagebox.askyesno(
            "Conversion complete",
            f"Wrote:\n  {tex_path}\n  {out_dir / 'chapter.json'}\n"
            f"  {out_dir / 'chaptercitations.bib'}\n\nOpen output folder?",
        ):
            _open_in_file_manager(out_dir)

    # -------------------------------------------------------------- submit

    def _on_convert(self) -> None:
        if not self.input_path or not self.parsed_chapter:
            messagebox.showerror("No input", "Pick an input file first.")
            return

        chabbr = self.var_chabbr.get().strip().upper()
        if len(chabbr) != 6 or not chabbr.isalpha():
            messagebox.showerror(
                "Invalid chabbr",
                "Chabbr must be exactly 6 alphabetic characters (e.g. LINALG).",
            )
            return

        output_dir = Path(self.output_dir.get()).expanduser()
        if not output_dir.parent.exists():
            messagebox.showerror(
                "Bad output directory",
                f"Parent directory does not exist: {output_dir.parent}",
            )
            return

        # Rebuild authors on the parsed Chapter from the form text
        author_lines = [
            ln.strip() for ln in self.txt_authors.get("1.0", "end").splitlines() if ln.strip()
        ]
        if author_lines:
            new_authors = []
            # Preserve original author metadata (dept/institution/email/url) when
            # the name still matches; otherwise use a bare Author with just the name.
            existing = {
                f"{a.first} {a.last}".strip(): a for a in self.parsed_chapter.authors
            }
            for line in author_lines:
                if line in existing:
                    new_authors.append(existing[line])
                else:
                    first, _, last = line.partition(" ")
                    new_authors.append(Author(first=first, last=last))
            self.parsed_chapter.authors = new_authors

        self.parsed_chapter.title = self.var_title.get().strip() or self.parsed_chapter.title
        self.parsed_chapter.chapter_type = self.var_chapter_type.get()

        # Reconcile TOC edits: keep only level-1 sections the user hasn't removed.
        # Non-level-1 sections (shouldn't exist at top level, but be safe) pass through.
        kept = set(id(s) for s in self._toc_sections)
        self.parsed_chapter.sections = [
            s for s in self.parsed_chapter.sections
            if s.level != 1 or id(s) in kept
        ]

        metadata = {
            "title": self.var_title.get().strip() or None,
            "authors": author_lines or None,
            "description": self.txt_description.get("1.0", "end").strip() or None,
            "keywords": _text_to_list(self.txt_keywords) or None,
            "chapter_type": self.var_chapter_type.get(),
            "chabbr": chabbr,
            "depends_on": _text_to_list(self.txt_depends_on) or None,
            "discipline": self.var_discipline.get().strip() or None,
            "entry_file": self.var_entry_file.get().strip() or None,
            "cover_image": self.var_cover_image.get().strip() or None,
            "published": self.var_published.get(),
        }

        self.status_var.set("Converting…")
        self.btn_convert.config(state="disabled")
        threading.Thread(
            target=self._convert_worker,
            args=(self.input_path, output_dir, chabbr, metadata, self.parsed_chapter),
            daemon=True,
        ).start()


# ---------------------------------------------------------------- helpers


def _text_to_list(widget: tk.Text) -> list[str]:
    return [ln.strip() for ln in widget.get("1.0", "end").splitlines() if ln.strip()]


def _open_in_file_manager(path: Path) -> None:
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        elif sys.platform.startswith("win"):
            subprocess.run(["explorer", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except Exception:
        pass


def main() -> None:
    root = tk.Tk()
    ConvertGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
