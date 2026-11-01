#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pushuuu Launcher - look & feel: palette, fonts, DPI scaling and custom-drawn widgets.

Tk's built-in buttons can't look "gamey", so the important controls are drawn on canvases
(rounded corners, neon glow, hover/press states).
"""
from __future__ import annotations

import random
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

# ---- palette ------------------------------------------------------------------ #
BG0 = "#080b10"      # window
BG1 = "#0e131a"      # sidebar, footer, lists
BG2 = "#151b24"      # cards
BG3 = "#1c2430"      # inputs, hover
LINE = "#232d3b"
FG = "#e8eef6"
MUTED = "#7f8b9b"
ACCENT = "#2bff88"   # neon green
ACCENT_D = "#14c866"
ACCENT_DD = "#0a6b3a"
VIOLET = "#a78bfa"
CYAN = "#22d3ee"
AMBER = "#fbbf24"
DANGER = "#ff5470"

SCALE = 1.0          # set once by init_scale(); everything pixel-based goes through px()
FONTS: dict = {}


def px(n: float) -> int:
    return int(round(n * SCALE))


def init_scale(root: tk.Misc) -> None:
    """Pixel sizes follow the screen's DPI (macOS handles Retina scaling itself)."""
    global SCALE
    SCALE = 1.0
    if root.tk.call("tk", "windowingsystem") != "aqua":
        try:
            SCALE = max(1.0, min(2.5, float(root.winfo_fpixels("1i")) / 96.0))
        except (tk.TclError, TypeError, ValueError):
            SCALE = 1.0


def _pick(available: set, candidates: list, fallback: str) -> str:
    return next((c for c in candidates if c in available), fallback)


def init_fonts(root: tk.Misc) -> None:
    fams = set(tkfont.families(root))
    base = tkfont.nametofont("TkDefaultFont").actual("family")
    ui = _pick(fams, ["Segoe UI Variable Text", "Segoe UI", "SF Pro Text", "Helvetica Neue", "Inter",
                      "Ubuntu", "Cantarell", "Noto Sans", "DejaVu Sans"], base)
    mono = _pick(fams, ["Cascadia Mono", "Consolas", "SF Mono", "Menlo", "DejaVu Sans Mono",
                        "Liberation Mono", "Courier New"], "Courier")

    def f(size, weight="normal", family=None):
        return tkfont.Font(root=root, family=family or ui, size=size, weight=weight)

    FONTS.update(ui=f(10), ui_b=f(10, "bold"), small=f(9), small_b=f(9, "bold"), caps=f(8, "bold"),
                 nav=f(10, "bold"), btn=f(11, "bold"), play=f(20, "bold"), h1=f(24, "bold"), h2=f(14, "bold"),
                 hero=f(30, "bold"), logo=f(16, "bold"), score=f(44, "bold"), overlay=f(22, "bold"),
                 mono=f(9, family=mono))


# ---- helpers ---------------------------------------------------------------------- #
def _rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a: str, b: str, t: float) -> str:
    """Blend colour a toward colour b by t (0..1)."""
    ra, rb = _rgb(a), _rgb(b)
    return "#%02x%02x%02x" % tuple(int(ra[i] + (rb[i] - ra[i]) * t) for i in range(3))


def round_rect(canvas: tk.Canvas, x1, y1, x2, y2, r, **kw):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
           x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


# ---- NeonButton --------------------------------------------------------------------- #
class NeonButton(tk.Canvas):
    """Rounded button with glow. kind: 'primary' (neon green), 'ghost' (outlined), 'danger' (red)."""

    def __init__(self, parent, text: str, command=None, kind: str = "primary", width: int = 150,
                 height: int = 40, font_key: str = "btn", bg: str = BG0):
        super().__init__(parent, width=px(width), height=px(height), bg=bg, highlightthickness=0, bd=0,
                         cursor="hand2")
        self.label, self.command, self.kind, self.font_key, self.bgc = text, command, kind, font_key, bg
        self.bw, self.bh = px(width), px(height)
        self.enabled, self.hover, self.pressed = True, False, False
        self.bind("<Enter>", lambda e: self._set(hover=True))
        self.bind("<Leave>", lambda e: self._set(hover=False, pressed=False))
        self.bind("<ButtonPress-1>", lambda e: self._set(pressed=True))
        self.bind("<ButtonRelease-1>", self._release)
        self._draw()

    def _set(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)
        self._draw()

    def _release(self, e):
        fire = self.pressed and self.enabled and 0 <= e.x <= self.bw and 0 <= e.y <= self.bh
        self._set(pressed=False)
        if fire and self.command:
            self.command()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self._draw()

    def set_text(self, text: str) -> None:
        self.label = text
        self._draw()

    def _colors(self):
        """-> fill, outline, text colour, glow colour (or None)"""
        if not self.enabled:
            if self.kind == "primary":
                return ACCENT_DD, ACCENT_DD, mix(ACCENT_DD, BG0, 0.45), None
            return BG2, LINE, MUTED, None
        if self.kind == "primary":
            fill = ACCENT_D if self.pressed else (mix(ACCENT, "#ffffff", 0.18) if self.hover else ACCENT)
            return fill, fill, "#04210f", ACCENT
        if self.kind == "danger":
            fill = "#55141f" if self.hover else "#3a1019"
            return fill, DANGER, "#ffd6dd", DANGER if self.hover else None
        fill = BG3 if self.hover else BG2
        return fill, ACCENT if self.hover else LINE, FG, ACCENT if self.hover else None

    def _draw(self):
        self.delete("all")
        fill, outline, fg, glow = self._colors()
        pad, r = px(4), px(10)
        if glow:                                     # fake a glow with a few fading outer rounded rects
            for i, t in ((3, 0.08), (2, 0.14), (1, 0.26)):
                g = px(i)
                round_rect(self, pad - g, pad - g, self.bw - pad + g, self.bh - pad + g, r + g,
                           fill=mix(self.bgc, glow, t), outline="")
        round_rect(self, pad, pad, self.bw - pad, self.bh - pad, r, fill=fill, outline=outline, width=1)
        if self.kind == "primary" and self.enabled and not self.pressed:   # subtle top highlight
            self.create_line(pad + r, pad + 2, self.bw - pad - r, pad + 2, fill=mix(fill, "#ffffff", 0.45))
        self.create_text(self.bw / 2, self.bh / 2 + (1 if self.pressed else 0), text=self.label, fill=fg,
                         font=FONTS[self.font_key])


# ---- NeonProgress ----------------------------------------------------------------------- #
class NeonProgress(tk.Canvas):
    """Slim progress bar. idle() / set(0..1) / indeterminate()."""

    def __init__(self, parent, width: int = 300, height: int = 10, bg: str = BG1):
        super().__init__(parent, width=px(width), height=px(height), bg=bg, highlightthickness=0, bd=0)
        self.mode, self.value, self.phase, self._job = "idle", 0.0, 0.0, None
        self.bind("<Configure>", lambda e: self._draw())

    def _stop(self):
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None

    def idle(self):
        self._stop()
        self.mode, self.value = "idle", 0.0
        self._draw()

    def set(self, fraction: float):
        self._stop()
        self.mode, self.value = "det", max(0.0, min(1.0, fraction))
        self._draw()

    def indeterminate(self):
        if self.mode == "ind":
            return
        self._stop()
        self.mode = "ind"
        self._tick()

    def _tick(self):
        self.phase = (self.phase + 0.022) % 1.0
        self._draw()
        self._job = self.after(30, self._tick)

    def _draw(self):
        w, h = max(self.winfo_width(), 20), max(self.winfo_height(), 6)
        self.delete("all")
        round_rect(self, 1, 1, w - 1, h - 1, h / 2, fill=BG3, outline=LINE)
        if self.mode == "det" and self.value > 0:
            fw = max(float(h), (w - 2) * self.value)
            round_rect(self, 1, 1, 1 + fw, h - 1, h / 2, fill=ACCENT, outline="")
            if fw > h:
                self.create_line(h / 2, 3, fw - h / 2, 3, fill=mix(ACCENT, "#ffffff", 0.55))
        elif self.mode == "ind":
            seg = w * 0.28
            x = -seg + (w + seg) * self.phase
            x1, x2 = max(3.0, x), min(w - 3.0, x + seg)
            if x2 > x1:
                self.create_rectangle(x1, 3, x2, h - 3, fill=ACCENT, outline="")


# ---- HeroBanner ----------------------------------------------------------------------------- #
class HeroBanner(tk.Canvas):
    """Pixel-landscape header for the selected instance: big title, subtitle and info chips."""

    def __init__(self, parent, height: int = 250):
        super().__init__(parent, height=px(height), bg=BG0, highlightthickness=0, bd=0)
        self.title_text, self.sub_text, self.chips = "No instance yet", "", []
        self.bind("<Configure>", lambda e: self._draw())

    def set(self, title: str, sub: str, chips: list) -> None:
        self.title_text, self.sub_text, self.chips = title, sub, chips
        self._draw()

    def _draw(self):
        w, h = max(self.winfo_width(), 300), max(self.winfo_height(), 120)
        self.delete("all")
        bands = 56
        for i in range(bands):                                   # night-sky gradient
            col = mix("#0c1d36", "#06130f", i / (bands - 1))
            self.create_rectangle(0, h * i / bands, w, h * (i + 1) / bands + 1, fill=col, outline="")
        rng = random.Random(11)                                  # stars (fixed seed = stable look)
        for _ in range(60):
            x, y, s = rng.random() * w, rng.random() * h * 0.62, rng.choice((1, 1, 2)) * SCALE
            self.create_rectangle(x, y, x + s, y + s, fill=mix(BG0, "#ffffff", rng.uniform(0.25, 0.85)), outline="")
        sky, moon = mix("#0c1d36", "#06130f", 0.28), "#dff1ff"      # pixel-art moon with a soft halo
        mx, my, cs, rad = w - px(150), h * 0.30, px(9), 5
        for gy in range(-rad - 2, rad + 3):
            for gx in range(-rad - 2, rad + 3):
                d2 = gx * gx + gy * gy
                fill = None
                if d2 <= rad * rad:
                    fill = mix(sky, moon, 0.72 if d2 > (rad - 1.2) ** 2 else 0.95)   # dimmer rim = round shading
                elif d2 <= (rad + 1.7) ** 2:
                    fill = mix(sky, CYAN, 0.11)
                if fill:
                    self.create_rectangle(mx + gx * cs, my + gy * cs, mx + (gx + 1) * cs, my + (gy + 1) * cs,
                                          fill=fill, outline="")
        for gx, gy in ((-2, -1), (1, 2), (2, -2), (-1, 2)):
            self.create_rectangle(mx + gx * cs, my + gy * cs, mx + (gx + 1) * cs, my + (gy + 1) * cs,
                                  fill=mix(moon, sky, 0.22), outline="")
        cell = px(26)                                            # blocky terrain, three parallax layers
        for layer, (base, body, top) in enumerate((
                (0.72, "#0b2a24", "#14493c"), (0.83, "#09201b", "#0f372e"), (0.93, "#06140f", "#0a2a1f"))):
            lr, level = random.Random(40 + layer), base
            for i in range(int(w / cell) + 2):
                level = max(base - 0.11, min(base + 0.05, level + lr.choice((-1, 0, 0, 1)) * 0.045))
                y = h * level
                self.create_rectangle(i * cell, y, (i + 1) * cell, h, fill=body, outline="")
                self.create_rectangle(i * cell, y, (i + 1) * cell, y + px(5), fill=top, outline="")
        x0, y0 = px(40), h * 0.30
        title = self.title_text if len(self.title_text) <= 26 else self.title_text[:25] + "…"
        glow = mix("#06130f", ACCENT, 0.38)
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2)):   # glow = offset copies in a dim colour
            self.create_text(x0 + dx, y0 + dy, anchor="w", text=title, font=FONTS["hero"], fill=glow)
        self.create_text(x0, y0, anchor="w", text=title, font=FONTS["hero"], fill=FG)
        self.create_text(x0, y0 + px(42), anchor="w", text=self.sub_text, font=FONTS["ui"], fill=MUTED)
        cx, cy, ch = x0, y0 + px(76), px(26)
        for text, col in self.chips:
            cw = FONTS["small_b"].measure(text) + px(24)
            round_rect(self, cx, cy, cx + cw, cy + ch, ch / 2, fill=mix("#06130f", col, 0.2), outline=mix("#06130f", col, 0.75))
            self.create_text(cx + cw / 2, cy + ch / 2, text=text, fill=col, font=FONTS["small_b"])
            cx += cw + px(8)


# ---- Logo ---------------------------------------------------------------------------------------- #
class Logo(tk.Canvas):
    def __init__(self, parent, bg: str = BG1):
        super().__init__(parent, height=px(86), bg=bg, highlightthickness=0, bd=0)
        cell, ox, oy = px(7), px(24), px(18)
        shape = ["XXXX.", "X...X", "X...X", "XXXX.", "X....", "X....", "X...."]
        for r, row in enumerate(shape):
            for c, ch in enumerate(row):
                if ch == "X":
                    x, y = ox + c * cell, oy + r * cell
                    self.create_rectangle(x, y, x + cell, y + cell, fill=ACCENT_D, outline="")
                    self.create_rectangle(x, y, x + cell - px(1), y + cell - px(1), fill=ACCENT, outline="")
        tx = ox + 5 * cell + px(18)
        self.create_text(tx, oy + 2.0 * cell, anchor="w", text="PUSHUUU", font=FONTS["logo"], fill=FG)
        self.create_text(tx, oy + 4.1 * cell, anchor="w", text="L A U N C H E R", font=FONTS["caps"], fill=ACCENT)


# ---- Card ---------------------------------------------------------------------------------------- #
class Card(tk.Frame):
    """Raised panel. Put children in card.body."""

    def __init__(self, parent, title: str | None = None):
        super().__init__(parent, bg=BG2, highlightthickness=1, highlightbackground=LINE,
                         highlightcolor=LINE, bd=0)
        self.body = tk.Frame(self, bg=BG2)
        self.body.pack(fill="both", expand=True, padx=px(20), pady=px(16))
        if title:
            tk.Label(self.body, text=title.upper(), bg=BG2, fg=ACCENT, font=FONTS["caps"]
                     ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, px(10)))


# ---- ttk theme ---------------------------------------------------------------------------------------- #
def apply_theme(root: tk.Tk) -> None:
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(".", background=BG0, foreground=FG, fieldbackground=BG3, bordercolor=LINE, lightcolor=LINE,
                darkcolor=LINE, troughcolor=BG1, focuscolor=BG0, font=FONTS["ui"])
    s.configure("TFrame", background=BG0)
    s.configure("TLabel", background=BG0, foreground=FG)
    s.configure("Muted.TLabel", foreground=MUTED)
    s.configure("TButton", background=BG3, foreground=FG, bordercolor=LINE, padding=(px(14), px(8)),
                borderwidth=1, relief="flat", font=FONTS["ui_b"])
    s.map("TButton", background=[("active", "#26313f"), ("disabled", BG2)], foreground=[("disabled", MUTED)],
          bordercolor=[("active", ACCENT)])
    s.configure("Accent.TButton", background=ACCENT, foreground="#04210f", bordercolor=ACCENT,
                font=FONTS["btn"], padding=(px(22), px(10)))
    s.map("Accent.TButton", background=[("active", mix(ACCENT, "#ffffff", 0.18)), ("disabled", ACCENT_DD)],
          foreground=[("disabled", "#0c2a16")], bordercolor=[("active", ACCENT)])
    for name in ("TEntry", "TCombobox"):
        s.configure(name, fieldbackground=BG3, foreground=FG, insertcolor=ACCENT, bordercolor=LINE,
                    lightcolor=LINE, darkcolor=LINE, padding=px(7), selectbackground=ACCENT_DD,
                    selectforeground=FG)
        s.map(name, bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)],
              darkcolor=[("focus", ACCENT)])
    s.configure("TCombobox", background=BG3, arrowcolor=FG)
    s.map("TCombobox", fieldbackground=[("readonly", BG3), ("disabled", BG2)],
          foreground=[("readonly", FG), ("disabled", MUTED)])
    s.configure("Treeview", background=BG1, fieldbackground=BG1, foreground=FG, rowheight=px(32),
                borderwidth=0, font=FONTS["ui"])
    s.map("Treeview", background=[("selected", "#123d29")], foreground=[("selected", ACCENT)])
    s.configure("Treeview.Heading", background=BG2, foreground=MUTED, relief="flat", padding=px(8),
                font=FONTS["small_b"], borderwidth=0)
    s.map("Treeview.Heading", background=[("active", BG3)])
    s.configure("Vertical.TScrollbar", background=BG3, troughcolor=BG1, bordercolor=BG1, arrowcolor=MUTED,
                lightcolor=BG3, darkcolor=BG3, gripcount=0)
    s.map("Vertical.TScrollbar", background=[("active", LINE)])
    s.configure("Pill.Toolbutton", background=BG3, foreground=MUTED, padding=(px(14), px(6)), borderwidth=0,
                font=FONTS["small_b"])
    s.map("Pill.Toolbutton", background=[("selected", ACCENT), ("active", "#26313f")],
          foreground=[("selected", "#04210f")])
    s.configure("Card.Horizontal.TScale", background=ACCENT, troughcolor=BG3, bordercolor=BG2,
                lightcolor=ACCENT, darkcolor=ACCENT_D)
    root.option_add("*TCombobox*Listbox.background", BG3)
    root.option_add("*TCombobox*Listbox.foreground", FG)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT_DD)
    root.option_add("*TCombobox*Listbox.selectForeground", FG)
    root.option_add("*TCombobox*Listbox.font", FONTS["ui"])
