#!/usr/bin/env python3
"""FolderCheck — compare two sets of files/folders side by side.

Cross-platform (macOS, Linux, Windows). Requires only the Python standard
library. Run with:  python3 foldercheck.py
"""

from __future__ import annotations

import hashlib
import os
import queue
import sys
import threading
import time
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import filedialog, ttk


# ---------- scanning ----------

@dataclass
class FileEntry:
    abs_path: str
    size: int
    mtime: float


@dataclass
class SideResult:
    paths: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    file_inputs: int = 0
    folder_inputs: int = 0
    size: int = 0
    files: int = 0
    subfolders: int = 0
    largest_file: tuple[str, int] = ("", 0)
    extensions: dict[str, int] = field(default_factory=dict)
    errors: int = 0
    sha256: str = ""
    # Per-file index keyed by a stable relative path used to pair with the
    # other side. For a single folder input, keys are paths relative to that
    # folder. For multiple inputs or bare files, keys are prefixed with the
    # input's basename to avoid collisions.
    entries: dict[str, FileEntry] = field(default_factory=dict)

    @property
    def total_items(self) -> int:
        return self.files + self.subfolders


def scan_side(paths: list[str], progress_cb=None) -> SideResult:
    r = SideResult(paths=list(paths))
    single_folder = len(paths) == 1 and Path(paths[0]).is_dir()

    for raw in paths:
        p = Path(raw)
        if not p.exists():
            r.missing.append(raw)
            continue
        if p.is_file():
            r.file_inputs += 1
            _scan_file(p, r, key=p.name, label=p.name)
            if progress_cb:
                progress_cb(r.files, r.size)
        elif p.is_dir():
            r.folder_inputs += 1
            prefix = "" if single_folder else (os.path.basename(str(p).rstrip(os.sep)) or str(p))
            _scan_dir(str(p), r, progress_cb, key_prefix=prefix)

    if len(paths) == 1 and r.file_inputs == 1 and not r.missing:
        try:
            r.sha256 = _hash_file(Path(paths[0]))
        except OSError:
            r.errors += 1
    return r


def _scan_file(p: Path, r: SideResult, key: str, label: str) -> None:
    try:
        st = p.stat()
    except OSError:
        r.errors += 1
        return
    r.files += 1
    r.size += st.st_size
    if st.st_size > r.largest_file[1]:
        r.largest_file = (label, st.st_size)
    ext = p.suffix.lower() or "(none)"
    r.extensions[ext] = r.extensions.get(ext, 0) + 1
    r.entries[key] = FileEntry(str(p), st.st_size, st.st_mtime)


def _scan_dir(path: str, r: SideResult, progress_cb, key_prefix: str) -> None:
    base_name = os.path.basename(path.rstrip(os.sep)) or path
    for root, dirs, files in os.walk(path, onerror=lambda e: _bump_err(r)):
        r.subfolders += len(dirs)
        for name in files:
            fp = os.path.join(root, name)
            try:
                st = os.stat(fp, follow_symlinks=False)
            except OSError:
                r.errors += 1
                continue
            r.files += 1
            r.size += st.st_size
            rel = os.path.relpath(fp, path).replace(os.sep, "/")
            key = f"{key_prefix}/{rel}" if key_prefix else rel
            label = f"{base_name}/{rel}"
            if st.st_size > r.largest_file[1]:
                r.largest_file = (label, st.st_size)
            ext = os.path.splitext(name)[1].lower() or "(none)"
            r.extensions[ext] = r.extensions.get(ext, 0) + 1
            r.entries[key] = FileEntry(fp, st.st_size, st.st_mtime)
            if progress_cb and r.files % 200 == 0:
                progress_cb(r.files, r.size)
    if progress_cb:
        progress_cb(r.files, r.size)


def _bump_err(r: SideResult) -> None:
    r.errors += 1


def _hash_file(p: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


# ---------- diff ----------

@dataclass
class DiffRow:
    status: str          # "added", "removed", "modified", "unchanged"
    key: str
    a: FileEntry | None
    b: FileEntry | None
    note: str = ""       # what differs (size/mtime/content)


def diff_sides(a: SideResult, b: SideResult, deep: bool = False,
               progress_cb=None) -> list[DiffRow]:
    rows: list[DiffRow] = []
    keys = set(a.entries) | set(b.entries)
    total = len(keys)
    for i, k in enumerate(sorted(keys)):
        ea, eb = a.entries.get(k), b.entries.get(k)
        if ea and not eb:
            rows.append(DiffRow("removed", k, ea, None, "only in A"))
        elif eb and not ea:
            rows.append(DiffRow("added", k, None, eb, "only in B"))
        else:
            assert ea and eb
            notes = []
            size_diff = ea.size != eb.size
            mtime_diff = abs(ea.mtime - eb.mtime) > 1.0
            if size_diff:
                notes.append(f"size {ea.size:,} → {eb.size:,}")
            if mtime_diff and not size_diff:
                notes.append("mtime changed")

            if deep and not size_diff:
                # Same size — hash to see if content actually matches.
                try:
                    ha = _hash_file(Path(ea.abs_path))
                    hb = _hash_file(Path(eb.abs_path))
                    if ha != hb:
                        notes.append("content differs")
                    else:
                        notes = []  # identical, ignore mtime
                except OSError:
                    notes.append("hash error")

            if notes:
                rows.append(DiffRow("modified", k, ea, eb, "; ".join(notes)))
            else:
                rows.append(DiffRow("unchanged", k, ea, eb))
        if progress_cb and i % 500 == 0:
            progress_cb(i, total)
    if progress_cb:
        progress_cb(total, total)
    return rows


# ---------- formatting ----------

def human_size(n: int) -> str:
    if n < 0:
        return f"-{human_size(-n)}"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    x = float(n)
    for u in units:
        if x < 1024 or u == units[-1]:
            return f"{x:,.2f} {u}" if u != "B" else f"{int(x):,} B"
        x /= 1024
    return f"{n} B"


def fmt_time(ts: float | None) -> str:
    if not ts:
        return "—"
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
    except (ValueError, OSError):
        return "—"


def describe_side(r: SideResult) -> str:
    if not r.paths:
        return "(empty)"
    parts = []
    if r.file_inputs:
        parts.append(f"{r.file_inputs} file(s)")
    if r.folder_inputs:
        parts.append(f"{r.folder_inputs} folder(s)")
    if r.missing:
        parts.append(f"{len(r.missing)} missing")
    return ", ".join(parts) or "(nothing valid)"


# ---------- GUI helpers ----------

class RoundedCard(tk.Frame):
    """A card container with canvas-drawn rounded corners + optional accent stripe.

    Children go into `self.body` (a regular tk.Frame).
    """

    def __init__(self, master, *, bg="#ffffff", border="#d8dee7",
                 radius: int = 14, border_width: int = 1,
                 accent: str | None = None, accent_height: int = 3,
                 padding: int = 0, parent_bg: str | None = None) -> None:
        # Match the parent bg so the canvas "clears" cleanly outside the rounded shape.
        pbg = parent_bg or (master.cget("bg") if isinstance(master, (tk.Widget, tk.Tk)) else "#eef1f6")
        super().__init__(master, bg=pbg)

        self._bg = bg
        self._border = border
        self._radius = radius
        self._bw = border_width
        self._accent = accent
        self._accent_h = accent_height if accent else 0
        self._padding = padding

        self.canvas = tk.Canvas(self, highlightthickness=0, bg=pbg, bd=0,
                                width=1, height=1)
        self.canvas.pack(fill="both", expand=True)

        self.body = tk.Frame(self.canvas, bg=bg)
        self._body_id = self.canvas.create_window(0, 0, anchor="nw",
                                                   window=self.body)

        self.canvas.bind("<Configure>", self._redraw)
        # Propagate body's natural size up so the card grows with its content
        # when packed with fill="x" only.
        self.body.bind("<Configure>", self._sync_body_size)

    def _sync_body_size(self, _evt=None) -> None:
        # Track only vertical growth from body; width comes from parent.
        need_h = self.body.winfo_reqheight()
        chrome = 2 * self._bw + self._accent_h + 2 * self._padding
        target = need_h + chrome
        if self.canvas.winfo_reqheight() != target:
            self.canvas.configure(height=target)

    def _redraw(self, _evt=None) -> None:
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w <= 2 or h <= 2:
            return
        self.canvas.delete("bg")

        r = self._radius
        # Filled rounded rectangle (body)
        self._round_rect(0, 0, w - 1, h - 1, r,
                         fill=self._bg, outline=self._border,
                         width=self._bw, tags="bg")

        # Top accent stripe: draw a slightly taller rect and let the card mask
        # its bottom edge. Since Canvas rounded polygons cap corners cleanly,
        # we approximate the stripe as a rounded rect the width of the card,
        # then re-cover the lower part with the body color.
        if self._accent:
            self._round_rect(0, 0, w - 1, self._accent_h + r,
                             r, fill=self._accent, outline="", tags="bg")
            # Cover the extra: leave only the top `accent_h` visible.
            self.canvas.create_rectangle(
                self._bw, self._accent_h, w - 1 - self._bw,
                self._accent_h + r,
                fill=self._bg, outline="", tags="bg")
            # Redraw the top border pixel-perfect (outline of the main card).
            self._round_rect(0, 0, w - 1, h - 1, r,
                             fill="", outline=self._border,
                             width=self._bw, tags="bg")

        # Place body content
        m = self._bw + self._accent_h + self._padding
        self.canvas.coords(self._body_id, self._bw + self._padding, m)
        self.canvas.itemconfig(
            self._body_id,
            width=max(1, w - 2 * (self._bw + self._padding)),
            height=max(1, h - m - self._bw - self._padding),
        )
        self.canvas.tag_lower("bg")

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [
            x1 + r, y1,  x2 - r, y1,  x2, y1,
            x2, y1 + r,  x2, y2 - r,  x2, y2,
            x2 - r, y2,  x1 + r, y2,  x1, y2,
            x1, y2 - r,  x1, y1 + r,  x1, y1,
        ]
        return self.canvas.create_polygon(pts, smooth=True, **kw)


class ScanDialog(tk.Toplevel):
    """Modal 'Scanning…' popup with a live status line and slim progress bar."""

    def __init__(self, master: tk.Tk, palette: dict, fonts: dict) -> None:
        super().__init__(master)
        self.palette = palette
        self.title("")
        self.configure(bg=palette["card"])
        self.resizable(False, False)
        # Undecorated look isn't great on macOS aqua, keep native chrome but
        # hide the title. Make it float above the main window.
        self.transient(master)
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass
        # Prevent accidental close mid-scan (worker can't be cancelled cleanly).
        self.protocol("WM_DELETE_WINDOW", lambda: None)

        pad_x, pad_y = 28, 22
        outer = tk.Frame(self, bg=palette["card"])
        outer.pack(padx=pad_x, pady=pad_y)

        tk.Label(outer, text="Scanning…", bg=palette["card"],
                 fg=palette["text"], font=fonts["h2"]).pack(anchor="w")

        self._status_var = tk.StringVar(value="Preparing…")
        tk.Label(outer, textvariable=self._status_var, bg=palette["card"],
                 fg=palette["muted"], font=fonts["subtle"],
                 wraplength=380, justify="left").pack(anchor="w", pady=(6, 14))

        self._pbar = ttk.Progressbar(outer, mode="indeterminate", length=380,
                                      style="Slim.Horizontal.TProgressbar")
        self._pbar.pack(fill="x")
        self._pbar.start(70)

        self.update_idletasks()
        # Center over master
        try:
            mx = master.winfo_rootx()
            my = master.winfo_rooty()
            mw = master.winfo_width()
            mh = master.winfo_height()
            w = self.winfo_reqwidth()
            h = self.winfo_reqheight()
            x = mx + (mw - w) // 2
            y = my + (mh - h) // 3
            self.geometry(f"+{x}+{y}")
        except tk.TclError:
            pass

        try:
            self.grab_set()
        except tk.TclError:
            pass

    def set_status(self, text: str) -> None:
        self._status_var.set(text)

    def close(self) -> None:
        try:
            self._pbar.stop()
        except tk.TclError:
            pass
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


def animate_number(widget: tk.Misc, var: tk.StringVar, target: int,
                   duration_ms: int = 500,
                   formatter=lambda n: f"{n:,}") -> None:
    """Ease-out count-up from 0 to target, writing to `var`."""
    steps = max(8, duration_ms // 25)
    interval = duration_ms // steps

    def ease(t: float) -> float:
        return 1 - (1 - t) ** 3

    def tick(i: int = 0) -> None:
        t = i / steps
        val = int(round(target * ease(t)))
        var.set(formatter(val))
        if i < steps:
            widget.after(interval, lambda: tick(i + 1))
        else:
            var.set(formatter(target))

    tick(0)


# ---------- Widgets ----------

class PathList(RoundedCard):
    """Card-style A/B input with a colored letter badge."""

    def __init__(self, master, label: str, letter: str, accent: str,
                 palette: dict) -> None:
        super().__init__(master, bg=palette["card"], border=palette["border"],
                         accent=accent, accent_height=4, radius=14,
                         parent_bg=palette["bg"])
        self.accent = accent
        self.palette = palette
        body = self.body
        body.configure(bg=palette["card"])

        # Header: badge + title
        header = tk.Frame(body, bg=palette["card"])
        header.pack(fill="x", padx=14, pady=(12, 8))

        badge = tk.Label(header, text=letter, bg=accent, fg="white",
                         font=palette["font_ui_bold"],
                         width=2, padx=0, pady=1)
        badge.pack(side="left")
        tk.Label(header, text="  " + label, bg=palette["card"],
                 fg=palette["text"],
                 font=palette["font_h2"]).pack(side="left")
        self._count = tk.StringVar(value="0 items")
        tk.Label(header, textvariable=self._count, bg=palette["card"],
                 fg=palette["muted"],
                 font=palette["font_subtle"]).pack(side="right")

        # Listbox area
        list_frame = tk.Frame(body, bg=palette["card"])
        list_frame.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.listbox = tk.Listbox(
            list_frame, selectmode="extended", height=6,
            activestyle="none", borderwidth=0, relief="flat",
            highlightthickness=1, highlightbackground=palette["border"],
            bg="white", fg=palette["text"],
            selectbackground=accent, selectforeground="white",
            font=palette["font_ui"],
        )
        self.listbox.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.listbox.configure(yscrollcommand=sb.set)

        # Empty-state hint
        self._hint = tk.Label(list_frame,
                              text="No items yet.\nClick + File(s) or + Folder below.",
                              bg="white", fg=palette["muted"],
                              font=palette["font_subtle"],
                              justify="center")
        self._hint.place(relx=0.5, rely=0.5, anchor="center")
        self.listbox.bind("<<ListboxSelect>>", lambda e: self._update_hint())

        # Button row
        btns = tk.Frame(body, bg=palette["card"])
        btns.pack(fill="x", padx=14, pady=(0, 12))
        ttk.Button(btns, text="＋ File(s)", command=self._add_files).pack(side="left")
        ttk.Button(btns, text="＋ Folder", command=self._add_folder).pack(side="left", padx=(6, 0))
        ttk.Button(btns, text="Remove", command=self._remove).pack(side="right")
        ttk.Button(btns, text="Clear", command=self.clear).pack(side="right", padx=(0, 6))

    def _add_files(self) -> None:
        for p in filedialog.askopenfilenames(title="Choose file(s)"):
            self._add_unique(p)

    def _add_folder(self) -> None:
        p = filedialog.askdirectory(title="Choose a folder", mustexist=True)
        if p:
            self._add_unique(p)

    def _add_unique(self, p: str) -> None:
        if p not in self.get_paths():
            self.listbox.insert("end", p)
        self._update_hint()

    def _remove(self) -> None:
        for i in reversed(self.listbox.curselection()):
            self.listbox.delete(i)
        self._update_hint()

    def clear(self) -> None:
        self.listbox.delete(0, "end")
        self._update_hint()

    def get_paths(self) -> list[str]:
        return list(self.listbox.get(0, "end"))

    def set_paths(self, items: list[str]) -> None:
        self.listbox.delete(0, "end")
        for p in items:
            self.listbox.insert("end", p)
        self._update_hint()

    def _update_hint(self) -> None:
        n = self.listbox.size()
        self._count.set(f"{n} item{'s' if n != 1 else ''}")
        if n == 0:
            self._hint.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self._hint.place_forget()


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("FolderCheck")
        self.geometry("1180x820")
        self.minsize(920, 640)

        self.status = tk.StringVar(value="Add items to A and B, then press Compare.")
        self.deep = tk.BooleanVar(value=False)
        self.show_unchanged = tk.BooleanVar(value=False)
        self.filter_added = tk.BooleanVar(value=True)
        self.filter_removed = tk.BooleanVar(value=True)
        self.filter_modified = tk.BooleanVar(value=True)
        self._queue: queue.Queue = queue.Queue()
        self._worker: threading.Thread | None = None
        self._diff_rows: list[DiffRow] = []

        self._build_ui()
        self.after(100, self._poll_queue)

    # Palette — refined for a quieter, more premium look. Slightly desaturated
    # from raw NSColor blues/greens/reds so the tables don't glow at you when
    # dense.
    P = {
        "bg":         "#f2f3f5",   # window
        "card":       "#ffffff",
        "border":     "#e2e5ea",   # softer separator
        "border_strong": "#c8ccd4",
        "text":       "#1a1c1f",
        "muted":      "#6f7480",
        "muted_soft": "#a1a6b0",
        "header_bg":  "#f6f7f9",
        "row_alt":    "#fafbfc",
        "sel_bg":     "#dbe9ff",
        "a":          "#3b7dd8",
        "b":          "#e37c26",
        "same":       "#2ea15b",
        "diff":       "#d64545",
        "mod":        "#c48317",
        "accent":     "#0a6cf5",
        "accent_dark":"#0a5cd0",
        "accent_soft":"#e4efff",
    }
    C_A = "#3b7dd8"
    C_B = "#e37c26"
    C_SAME = "#2ea15b"
    C_DIFF = "#d64545"
    C_MODIFIED = "#c48317"

    # Font stack — SF Pro on macOS, Segoe UI on Windows, sane fallback elsewhere.
    if sys.platform == "darwin":
        FONT_UI = ("SF Pro Text", 12)
        FONT_UI_BOLD = ("SF Pro Text", 12, "bold")
        FONT_TITLE = ("SF Pro Display", 22, "bold")
        FONT_H2 = ("SF Pro Display", 15, "bold")
        FONT_STAT_BIG = ("SF Pro Display", 24, "bold")
        FONT_STAT_SMALL = ("SF Pro Text", 13, "bold")
        FONT_SUBTLE = ("SF Pro Text", 11)
        FONT_MONO = ("SF Mono", 11)
    elif sys.platform.startswith("win"):
        FONT_UI = ("Segoe UI", 10)
        FONT_UI_BOLD = ("Segoe UI Semibold", 10)
        FONT_TITLE = ("Segoe UI Semibold", 18)
        FONT_H2 = ("Segoe UI Semibold", 13)
        FONT_STAT_BIG = ("Segoe UI Semibold", 20)
        FONT_STAT_SMALL = ("Segoe UI Semibold", 11)
        FONT_SUBTLE = ("Segoe UI", 9)
        FONT_MONO = ("Consolas", 10)
    else:
        FONT_UI = ("TkDefaultFont", 10)
        FONT_UI_BOLD = ("TkDefaultFont", 10, "bold")
        FONT_TITLE = ("TkDefaultFont", 18, "bold")
        FONT_H2 = ("TkDefaultFont", 13, "bold")
        FONT_STAT_BIG = ("TkDefaultFont", 20, "bold")
        FONT_STAT_SMALL = ("TkDefaultFont", 11, "bold")
        FONT_SUBTLE = ("TkDefaultFont", 9)
        FONT_MONO = ("TkFixedFont", 10)

    def _build_ui(self) -> None:
        # Inject font stack into the palette dict so PathList (and any child
        # widget receiving palette) can use platform-appropriate fonts.
        self.P = dict(self.P)  # local copy
        self.P.update({
            "font_ui":       self.FONT_UI,
            "font_ui_bold":  self.FONT_UI_BOLD,
            "font_h2":       self.FONT_H2,
            "font_subtle":   self.FONT_SUBTLE,
        })

        self.configure(bg=self.P["bg"])
        self._apply_style()

        # --- App header (kept quiet — the real UI is the panes below) ---
        header = tk.Frame(self, bg=self.P["bg"])
        header.pack(fill="x", padx=22, pady=(18, 10))
        tk.Label(header, text="FolderCheck", bg=self.P["bg"],
                 fg=self.P["text"],
                 font=self.FONT_TITLE).pack(anchor="w")
        tk.Label(header,
                 text="Compare two sets of files or folders side by side.",
                 bg=self.P["bg"], fg=self.P["muted"],
                 font=self.FONT_SUBTLE).pack(anchor="w", pady=(2, 0))

        # --- A / B input cards ---
        cards = tk.Frame(self, bg=self.P["bg"])
        cards.pack(fill="x", padx=14, pady=(10, 6))
        cards.columnconfigure(0, weight=1, uniform="side")
        cards.columnconfigure(1, weight=1, uniform="side")
        self.side_a = PathList(cards, "Side A", "A", accent=self.C_A, palette=self.P)
        self.side_b = PathList(cards, "Side B", "B", accent=self.C_B, palette=self.P)
        self.side_a.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.side_b.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        # --- Toolbar (rounded card) ---
        toolbar_card = RoundedCard(self, bg=self.P["card"],
                                    border=self.P["border"], radius=14,
                                    parent_bg=self.P["bg"])
        toolbar_card.pack(fill="x", padx=18, pady=(12, 8))
        inner = tk.Frame(toolbar_card.body, bg=self.P["card"])
        inner.pack(fill="x", padx=16, pady=12)

        ttk.Button(inner, text="Compare", style="Accent.TButton",
                   command=self._start).pack(side="left")
        ttk.Button(inner, text="Swap  A ⇄ B",
                   command=self._swap).pack(side="left", padx=(10, 0))
        ttk.Button(inner, text="Clear all",
                   command=self._clear_all).pack(side="left", padx=(6, 0))
        # Divider
        tk.Frame(inner, bg=self.P["border"], width=1, height=22).pack(
            side="left", padx=14, pady=2)
        ttk.Checkbutton(inner, text="Deep compare",
                        variable=self.deep).pack(side="left")
        tk.Label(inner, text="hash same-size files to detect content changes",
                 bg=self.P["card"], fg=self.P["muted_soft"],
                 font=self.FONT_SUBTLE).pack(side="left", padx=(6, 0))

        self.progress = ttk.Progressbar(inner, mode="indeterminate",
                                         length=160, style="Slim.Horizontal.TProgressbar")
        self.progress.pack(side="right")

        # --- Notebook ---
        nb_wrap = tk.Frame(self, bg=self.P["bg"])
        nb_wrap.pack(fill="both", expand=True, padx=14, pady=(4, 6))
        self.nb = ttk.Notebook(nb_wrap)
        self.nb.pack(fill="both", expand=True)

        # ===== Summary tab =====
        summary = tk.Frame(self.nb, bg=self.P["bg"])
        self.nb.add(summary, text="  Summary  ")

        # Stat cards row
        self.summary_stats = tk.Frame(summary, bg=self.P["bg"])
        self.summary_stats.pack(fill="x", padx=10, pady=(10, 4))
        self._summary_stat_vars = {}
        self._build_stat_cards(self.summary_stats, [
            ("files",   "Total files",     self.P["accent"], 13),
            ("size",    "Total size",      self.P["accent"], 13),
            ("added",   "Added",           self.P["same"],   20),
            ("removed", "Removed",         self.P["diff"],   20),
            ("modified","Modified",        self.P["mod"],    20),
        ], self._summary_stat_vars)

        # Legend
        legend = tk.Frame(summary, bg=self.P["bg"])
        legend.pack(fill="x", padx=10, pady=(4, 2))
        tk.Label(legend, text="Row color:", bg=self.P["bg"],
                 fg=self.P["muted"]).pack(side="left")
        for text, color in (("A is larger", self.C_A),
                            ("B is larger", self.C_B),
                            ("Same", self.C_SAME),
                            ("Differs", self.C_DIFF)):
            chip = tk.Frame(legend, bg=self.P["bg"])
            chip.pack(side="left", padx=(12, 0))
            tk.Frame(chip, bg=color, width=12, height=12,
                     highlightthickness=0).pack(side="left")
            tk.Label(chip, text="  " + text, bg=self.P["bg"],
                     fg=self.P["text"]).pack(side="left")

        # Tree card
        tree_card = RoundedCard(summary, bg=self.P["card"],
                                 border=self.P["border"], radius=12,
                                 parent_bg=self.P["bg"])
        tree_card.pack(fill="both", expand=True, padx=10, pady=(6, 10))
        cols = ("metric", "a", "b", "winner")
        self.tree = ttk.Treeview(tree_card.body, columns=cols, show="headings",
                                  style="Modern.Treeview")
        for c, w, anchor in (("metric", 240, "w"), ("a", 220, "w"),
                             ("b", 220, "w"), ("winner", 260, "w")):
            self.tree.heading(c, text={
                "metric": "Metric", "a": "A", "b": "B",
                "winner": "Comparison",
            }[c])
            self.tree.column(c, width=w, anchor=anchor, stretch=True)
        self.tree.tag_configure("a_wins", foreground=self.C_A)
        self.tree.tag_configure("b_wins", foreground=self.C_B)
        self.tree.tag_configure("same", foreground=self.C_SAME)
        self.tree.tag_configure("diff", foreground=self.C_DIFF)
        self.tree.tag_configure("header", background=self.P["header_bg"],
                                foreground=self.P["muted"],
                                font=self.FONT_STAT_SMALL)
        self.tree.tag_configure("odd", background=self.P["row_alt"])
        s_sb = ttk.Scrollbar(tree_card.body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=s_sb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=1, pady=1)
        s_sb.pack(side="right", fill="y")

        # ===== File differences tab =====
        diff_tab = tk.Frame(self.nb, bg=self.P["bg"])
        self.nb.add(diff_tab, text="  File differences  ")

        # Stat cards for diff view
        self.diff_stats = tk.Frame(diff_tab, bg=self.P["bg"])
        self.diff_stats.pack(fill="x", padx=10, pady=(10, 4))
        self._diff_stat_vars = {}
        self._build_stat_cards(self.diff_stats, [
            ("added",     "Added (in B)",   self.P["same"],  20),
            ("removed",   "Removed (in A)", self.P["diff"],  20),
            ("modified",  "Modified",       self.P["mod"],   20),
            ("unchanged", "Unchanged",      self.P["muted"], 20),
        ], self._diff_stat_vars)

        # Filter bar
        filters = tk.Frame(diff_tab, bg=self.P["bg"])
        filters.pack(fill="x", padx=10, pady=(4, 4))
        tk.Label(filters, text="Show:", bg=self.P["bg"],
                 fg=self.P["muted"]).pack(side="left")
        for label, var in (("Added", self.filter_added),
                           ("Removed", self.filter_removed),
                           ("Modified", self.filter_modified),
                           ("Unchanged", self.show_unchanged)):
            ttk.Checkbutton(filters, text=label, variable=var,
                            command=self._refresh_diff).pack(side="left", padx=6)
        ttk.Button(filters, text="Export CSV…",
                   command=self._export_csv).pack(side="right")
        self.diff_count = tk.StringVar(value="")
        tk.Label(filters, textvariable=self.diff_count,
                 bg=self.P["bg"], fg=self.P["muted"]).pack(side="right", padx=8)

        # Tree card
        diff_card = RoundedCard(diff_tab, bg=self.P["card"],
                                 border=self.P["border"], radius=12,
                                 parent_bg=self.P["bg"])
        diff_card.pack(fill="both", expand=True, padx=10, pady=(2, 10))
        dcols = ("status", "path", "a_size", "b_size", "a_mtime", "b_mtime", "newer", "note")
        self.diff_tree = ttk.Treeview(diff_card.body, columns=dcols, show="headings",
                                      style="Modern.Treeview")
        for c, w, anchor in (
            ("status", 90, "w"),
            ("path", 420, "w"),
            ("a_size", 100, "e"),
            ("b_size", 100, "e"),
            ("a_mtime", 150, "w"),
            ("b_mtime", 150, "w"),
            ("newer", 70, "center"),
            ("note", 240, "w"),
        ):
            self.diff_tree.heading(c, text={
                "status": "Status", "path": "Path",
                "a_size": "A size", "b_size": "B size",
                "a_mtime": "A modified", "b_mtime": "B modified",
                "newer": "Newer", "note": "Change",
            }[c])
            self.diff_tree.column(c, width=w, anchor=anchor, stretch=(c == "path"))
        self.diff_tree.tag_configure("added", foreground=self.C_SAME)
        self.diff_tree.tag_configure("removed", foreground=self.C_DIFF)
        self.diff_tree.tag_configure("modified", foreground=self.C_MODIFIED)
        self.diff_tree.tag_configure("unchanged", foreground=self.P["muted"])
        self.diff_tree.tag_configure("odd", background=self.P["row_alt"])
        d_sb = ttk.Scrollbar(diff_card.body, orient="vertical", command=self.diff_tree.yview)
        self.diff_tree.configure(yscrollcommand=d_sb.set)
        self.diff_tree.pack(side="left", fill="both", expand=True, padx=1, pady=1)
        d_sb.pack(side="right", fill="y")

        # --- Status bar ---
        status = tk.Frame(self, bg=self.P["header_bg"],
                          highlightthickness=1,
                          highlightbackground=self.P["border"])
        status.pack(fill="x", side="bottom")
        tk.Label(status, textvariable=self.status, bg=self.P["header_bg"],
                 fg=self.P["muted"], anchor="w",
                 font=self.FONT_SUBTLE).pack(side="left", fill="x",
                                              expand=True, padx=14, pady=7)

    def _build_stat_cards(self, parent: tk.Frame, defs: list, store: dict) -> None:
        for i, spec in enumerate(defs):
            key, label, color, font_size = spec if len(spec) == 4 else (*spec, 18)
            parent.columnconfigure(i, weight=1, uniform="stats")
            card = RoundedCard(parent, bg=self.P["card"],
                                border=self.P["border"], radius=12,
                                accent=color, accent_height=3,
                                parent_bg=self.P["bg"])
            card.grid(row=0, column=i, sticky="nsew",
                      padx=(0 if i == 0 else 8, 0))
            inner = tk.Frame(card.body, bg=self.P["card"])
            inner.pack(fill="both", expand=True, padx=14, pady=(10, 12))
            tk.Label(inner, text=label.upper(), bg=self.P["card"],
                     fg=self.P["muted"],
                     font=(self.FONT_SUBTLE[0], max(9, self.FONT_SUBTLE[1] - 1)),
                     ).pack(anchor="w")
            v = tk.StringVar(value="—")
            store[key] = v
            fam = self.FONT_STAT_BIG[0]
            tk.Label(inner, textvariable=v, bg=self.P["card"], fg=color,
                     font=(fam, font_size, "bold"),
                     anchor="w", justify="left").pack(anchor="w", pady=(4, 0),
                                                       fill="x")

    def _apply_style(self) -> None:
        style = ttk.Style(self)
        P = self.P
        is_mac = sys.platform == "darwin"

        # Use native aqua on macOS (it gives real rounded buttons, focus rings,
        # and the correct HIG-look). Use 'clam' elsewhere for a consistent
        # flat modern look — the built-in Windows/Linux themes are dated.
        try:
            if is_mac:
                style.theme_use("aqua")
            else:
                style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", background=P["bg"], foreground=P["text"],
                        font=self.FONT_UI)
        style.configure("TFrame", background=P["bg"])
        style.configure("TLabel", background=P["bg"], foreground=P["text"])
        style.configure("TCheckbutton", background=P["card"],
                        foreground=P["text"], font=self.FONT_UI)
        style.map("TCheckbutton", background=[("active", P["card"])])

        if not is_mac:
            # On non-aqua themes we need to style buttons ourselves.
            style.configure("TButton",
                            background="#ffffff", foreground=P["text"],
                            bordercolor=P["border"],
                            lightcolor=P["border"], darkcolor=P["border"],
                            focusthickness=0, padding=(12, 6),
                            font=self.FONT_UI)
            style.map("TButton",
                      background=[("active", "#f5f5f7"),
                                  ("pressed", "#e5e5ea")],
                      bordercolor=[("active", "#b5bfcc")])

            style.configure("Accent.TButton",
                            background=P["accent"], foreground="white",
                            bordercolor=P["accent_dark"],
                            lightcolor=P["accent"], darkcolor=P["accent_dark"],
                            font=self.FONT_UI_BOLD,
                            padding=(16, 8))
            style.map("Accent.TButton",
                      background=[("active", P["accent_dark"]),
                                  ("pressed", P["accent_dark"])])

        # Treeview — safe to override on all platforms.
        style.configure("Modern.Treeview",
                        background=P["card"], fieldbackground=P["card"],
                        foreground=P["text"], rowheight=28,
                        bordercolor=P["border"], borderwidth=0,
                        font=self.FONT_UI)
        style.configure("Modern.Treeview.Heading",
                        background=P["header_bg"], foreground=P["muted"],
                        font=self.FONT_STAT_SMALL,
                        padding=(12, 9), relief="flat", borderwidth=0)
        style.map("Modern.Treeview.Heading",
                  background=[("active", "#ecedf1")])
        style.map("Modern.Treeview",
                  background=[("selected", P["sel_bg"])],
                  foreground=[("selected", P["text"])])

        # Slim progress bar shown in the toolbar during scans.
        style.configure("Slim.Horizontal.TProgressbar",
                        background=P["accent"],
                        troughcolor=P["header_bg"],
                        bordercolor=P["header_bg"],
                        lightcolor=P["accent"],
                        darkcolor=P["accent"],
                        thickness=6)

        # Notebook — on macOS aqua we can't fully restyle tabs; leave native.
        if not is_mac:
            style.configure("TNotebook", background=P["bg"], borderwidth=0)
            style.configure("TNotebook.Tab",
                            background=P["header_bg"], foreground=P["muted"],
                            padding=(20, 9), borderwidth=0,
                            font=self.FONT_UI)
            style.map("TNotebook.Tab",
                      background=[("selected", P["card"])],
                      foreground=[("selected", P["accent"])])

            # Progressbar
            style.configure("Horizontal.TProgressbar",
                            background=P["accent"], troughcolor="#e5e5ea",
                            bordercolor="#e5e5ea", lightcolor=P["accent"],
                            darkcolor=P["accent"])

            # Scrollbar
            style.configure("Vertical.TScrollbar",
                            background="#c7c7cc", troughcolor=P["card"],
                            bordercolor=P["card"], arrowcolor=P["muted"],
                            gripcount=0, arrowsize=12)

    def _swap(self) -> None:
        a, b = self.side_a.get_paths(), self.side_b.get_paths()
        self.side_a.set_paths(b)
        self.side_b.set_paths(a)

    def _clear_all(self) -> None:
        self.side_a.clear()
        self.side_b.clear()
        for i in self.tree.get_children():
            self.tree.delete(i)
        for i in self.diff_tree.get_children():
            self.diff_tree.delete(i)
        self._diff_rows = []
        self.diff_count.set("")
        self.status.set("Cleared.")

    def _start(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        a = self.side_a.get_paths()
        b = self.side_b.get_paths()
        if not a or not b:
            self.status.set("Add at least one item to each of A and B.")
            return
        for i in self.tree.get_children():
            self.tree.delete(i)
        for i in self.diff_tree.get_children():
            self.diff_tree.delete(i)
        self._diff_rows = []
        self.diff_count.set("")
        self.status.set("Scanning…")
        self.progress.start(80)

        # Modal "Scanning…" popup, updated by _poll_queue as messages arrive.
        self._scan_dialog = ScanDialog(
            self, self.P,
            fonts={"h2": self.FONT_H2, "subtle": self.FONT_SUBTLE},
        )

        deep = self.deep.get()

        def run() -> None:
            try:
                ra = scan_side(a, progress_cb=lambda n, s: self._queue.put(("prog", "A", n, s)))
                rb = scan_side(b, progress_cb=lambda n, s: self._queue.put(("prog", "B", n, s)))
                self._queue.put(("phase", "Comparing files…"))
                rows = diff_sides(ra, rb, deep=deep,
                                  progress_cb=lambda i, t: self._queue.put(("diffprog", i, t)))
                self._queue.put(("done", ra, rb, rows))
            except Exception as e:
                self._queue.put(("error", str(e)))

        self._worker = threading.Thread(target=run, daemon=True)
        self._worker.start()

    def _poll_queue(self) -> None:
        try:
            while True:
                msg = self._queue.get_nowait()
                dlg = getattr(self, "_scan_dialog", None)
                if msg[0] == "prog":
                    _, side, n, s = msg
                    text = f"Scanning {side}: {n:,} files, {human_size(s)}…"
                    self.status.set(text)
                    if dlg: dlg.set_status(text)
                elif msg[0] == "phase":
                    self.status.set(msg[1])
                    if dlg: dlg.set_status(msg[1])
                elif msg[0] == "diffprog":
                    _, i, t = msg
                    text = f"Comparing: {i:,} / {t:,}"
                    self.status.set(text)
                    if dlg: dlg.set_status(text)
                elif msg[0] == "done":
                    _, ra, rb, rows = msg
                    self.progress.stop()
                    self._close_scan_dialog()
                    self._render_summary(ra, rb, rows)
                    self._diff_rows = rows
                    self._refresh_diff()
                elif msg[0] == "error":
                    self.progress.stop()
                    self._close_scan_dialog()
                    self.status.set(f"Error: {msg[1]}")
        except queue.Empty:
            pass
        self.after(120, self._poll_queue)

    def _close_scan_dialog(self) -> None:
        dlg = getattr(self, "_scan_dialog", None)
        if dlg is not None:
            dlg.close()
            self._scan_dialog = None

    def _render_summary(self, a: SideResult, b: SideResult, rows: list[DiffRow]) -> None:
        added = sum(1 for r in rows if r.status == "added")
        removed = sum(1 for r in rows if r.status == "removed")
        modified = sum(1 for r in rows if r.status == "modified")
        unchanged = sum(1 for r in rows if r.status == "unchanged")

        # Update stat cards (with count-up animation for the pure numeric ones).
        self._summary_stat_vars["files"].set(f"A {a.files:,}  ·  B {b.files:,}")
        self._summary_stat_vars["size"].set(
            f"A {human_size(a.size)}  ·  B {human_size(b.size)}"
        )
        animate_number(self, self._summary_stat_vars["added"], added)
        animate_number(self, self._summary_stat_vars["removed"], removed)
        animate_number(self, self._summary_stat_vars["modified"], modified)

        animate_number(self, self._diff_stat_vars["added"], added)
        animate_number(self, self._diff_stat_vars["removed"], removed)
        animate_number(self, self._diff_stat_vars["modified"], modified)
        animate_number(self, self._diff_stat_vars["unchanged"], unchanged)

        row_i = [0]

        def add(metric, va, vb, winner="", tag=""):
            tags: list[str] = []
            if tag:
                tags.append(tag)
            if tag != "header" and row_i[0] % 2 == 1:
                tags.append("odd")
            row_i[0] += 1
            self.tree.insert("", "end", values=(metric, va, vb, winner), tags=tuple(tags))

        def num_row(label, na, nb, formatter=lambda x: f"{x:,}"):
            """Number-comparison row. Colors and describes which side is larger."""
            if na == nb:
                add(label, formatter(na), formatter(nb),
                    f"Same ({formatter(na)})", "same")
                return
            diff = abs(nb - na)
            if na > nb:
                winner_side, tag = "A", "a_wins"
            else:
                winner_side, tag = "B", "b_wins"
            add(label, formatter(na), formatter(nb),
                f"{winner_side} larger by {formatter(diff)}", tag)

        def text_row(label, va, vb):
            """Non-numeric row — just flag same vs differs."""
            same = va == vb
            add(label, va, vb, "Same" if same else "Differs",
                "same" if same else "diff")

        add("  INPUTS", "", "", "", "header")
        num_row("Item count", len(a.paths), len(b.paths))
        text_row("Composition", describe_side(a), describe_side(b))
        num_row("Missing paths", len(a.missing), len(b.missing))

        add("  TOTALS", "", "", "", "header")
        num_row("Total size", a.size, b.size, human_size)
        num_row("Total files", a.files, b.files)
        num_row("Total subfolders", a.subfolders, b.subfolders)
        num_row("Files + subfolders", a.total_items, b.total_items)
        num_row("Read errors", a.errors, b.errors)

        add("  FILE-LEVEL CHANGES", "", "", "", "header")
        add("Added (only in B)", "—", str(added),
            f"{added} added to B" if added else "None",
            "b_wins" if added else "same")
        add("Removed (only in A)", str(removed), "—",
            f"{removed} removed from A" if removed else "None",
            "a_wins" if removed else "same")
        add("Modified", "—", "—",
            f"{modified} file(s) changed" if modified else "None",
            "diff" if modified else "same")
        add("Unchanged", "—", "—",
            f"{unchanged} file(s) identical", "same")

        add("  LARGEST FILE", "", "", "", "header")
        text_row("Name", a.largest_file[0] or "—", b.largest_file[0] or "—")
        num_row("Size", a.largest_file[1], b.largest_file[1], human_size)

        if a.sha256 or b.sha256:
            add("  FILE HASH  (single-file sides)", "", "", "", "header")
            same = a.sha256 and b.sha256 and a.sha256 == b.sha256
            add("SHA-256", a.sha256 or "—", b.sha256 or "—",
                "Identical content" if same
                else ("Content differs" if a.sha256 and b.sha256 else "n/a"),
                "same" if same else ("diff" if a.sha256 and b.sha256 else ""))

        add("  EXTENSIONS  (top 15 by combined count)", "", "", "", "header")
        keys = sorted(set(a.extensions) | set(b.extensions),
                      key=lambda k: -(a.extensions.get(k, 0) + b.extensions.get(k, 0)))
        for k in keys[:15]:
            num_row(f"  {k}", a.extensions.get(k, 0), b.extensions.get(k, 0))

        self.status.set(
            f"Done. A: {a.files:,} files / {human_size(a.size)}   "
            f"B: {b.files:,} files / {human_size(b.size)}   "
            f"(+{added} added, -{removed} removed, {modified} modified)"
        )

    def _refresh_diff(self) -> None:
        for i in self.diff_tree.get_children():
            self.diff_tree.delete(i)
        wanted = set()
        if self.filter_added.get(): wanted.add("added")
        if self.filter_removed.get(): wanted.add("removed")
        if self.filter_modified.get(): wanted.add("modified")
        if self.show_unchanged.get(): wanted.add("unchanged")

        order = {"removed": 0, "added": 1, "modified": 2, "unchanged": 3}
        shown = sorted((r for r in self._diff_rows if r.status in wanted),
                       key=lambda r: (order[r.status], r.key))
        for idx, r in enumerate(shown):
            a_sz = human_size(r.a.size) if r.a else "—"
            b_sz = human_size(r.b.size) if r.b else "—"
            a_mt = fmt_time(r.a.mtime) if r.a else "—"
            b_mt = fmt_time(r.b.mtime) if r.b else "—"
            if r.a and r.b:
                if abs(r.a.mtime - r.b.mtime) <= 1.0:
                    newer = "="
                else:
                    newer = "B" if r.b.mtime > r.a.mtime else "A"
            elif r.a:
                newer = "A"
            elif r.b:
                newer = "B"
            else:
                newer = ""
            tags = [r.status]
            if idx % 2 == 1:
                tags.append("odd")
            self.diff_tree.insert("", "end",
                                  values=(r.status, r.key, a_sz, b_sz,
                                          a_mt, b_mt, newer, r.note),
                                  tags=tuple(tags))
        self.diff_count.set(f"{len(shown):,} of {len(self._diff_rows):,} entries")

    def _export_csv(self) -> None:
        if not self._diff_rows:
            self.status.set("Nothing to export yet.")
            return
        p = filedialog.asksaveasfilename(
            title="Export file differences",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
        if not p:
            return
        import csv
        try:
            with open(p, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["status", "path", "a_size", "b_size",
                            "a_mtime", "b_mtime", "note"])
                for r in self._diff_rows:
                    w.writerow([
                        r.status, r.key,
                        r.a.size if r.a else "",
                        r.b.size if r.b else "",
                        r.a.mtime if r.a else "",
                        r.b.mtime if r.b else "",
                        r.note,
                    ])
            self.status.set(f"Exported {len(self._diff_rows):,} rows to {p}")
        except OSError as e:
            self.status.set(f"Export failed: {e}")


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
