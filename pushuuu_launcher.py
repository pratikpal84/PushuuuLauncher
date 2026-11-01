#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pushuuu Launcher - desktop GUI (Windows / Linux / macOS).

    python pushuuu_launcher.py            normal start
    python pushuuu_launcher.py --portable keep all data next to the program

Launcher logic: pushuuu_core.py - look & feel: pushuuu_ui.py - mini-games: pushuuu_arcade.py
"""
from __future__ import annotations

import queue
import re
import shutil
import threading
import time
import traceback
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import pushuuu_core as core
import pushuuu_ui as theme
from pushuuu_arcade import ArcadePage
from pushuuu_core import Cancelled, Ctx
from pushuuu_ui import (ACCENT, AMBER, BG0, BG1, BG2, CYAN, DANGER, FG, FONTS, LINE, MUTED, VIOLET, Card,
                        HeroBanner, Logo, NeonButton, NeonProgress, mix, px)

TYPE_NAMES = {"release": "Release", "snapshot": "Snapshot", "old_beta": "Old beta", "old_alpha": "Old alpha"}
TYPE_COLORS = {"release": FG, "snapshot": AMBER, "old_beta": VIOLET, "old_alpha": CYAN}

# 128px app icon, embedded so no data files need bundling into the executables
ICON_B64 = (
    "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"
)


def ago(ts: float) -> str:
    if not ts:
        return "Never played"
    s = int(time.time() - ts)
    for secs, name in ((86400 * 30, "month"), (86400, "day"), (3600, "hour"), (60, "minute")):
        if s >= secs:
            n = s // secs
            return f"Played {n} {name}{'s' if n != 1 else ''} ago"
    return "Played just now"


def label(parent, text, bg=BG0, fg=FG, font="ui", **kw):
    return tk.Label(parent, text=text, bg=bg, fg=fg, font=FONTS[font], **kw)


# =========================================================================== #
# New-instance dialog: version list with Release / Snapshot / Beta / Alpha toggles
# =========================================================================== #
class NewInstanceDialog(tk.Toplevel):
    def __init__(self, app: "App"):
        super().__init__(app)
        self.app = app
        self.title("New instance")
        self.geometry(f"{px(740)}x{px(780)}")
        self.minsize(px(640), px(600))
        self.configure(bg=BG0)
        self.transient(app)
        self.versions: list[dict] = []
        self.token = 0
        self.columnconfigure(0, weight=1)
        self.rowconfigure(4, weight=1)

        label(self, "NEW INSTANCE", font="h2").grid(row=0, column=0, sticky="w", padx=px(24), pady=(px(22), px(4)))
        top = tk.Frame(self, bg=BG0)
        top.grid(row=1, column=0, sticky="ew", padx=px(24), pady=(px(8), px(6)))
        top.columnconfigure(1, weight=1)
        label(top, "Name", fg=MUTED).grid(row=0, column=0)
        self.name = tk.StringVar()
        ttk.Entry(top, textvariable=self.name).grid(row=0, column=1, sticky="ew", padx=px(12))

        tg = tk.Frame(self, bg=BG0)
        tg.grid(row=2, column=0, sticky="ew", padx=px(24), pady=px(6))
        label(tg, "Show", fg=MUTED).pack(side="left", padx=(0, px(12)))
        self.flt: dict[str, tk.BooleanVar] = {}
        for key in core.VERSION_TYPES:
            var = tk.BooleanVar(value=bool(app.cfg["show"].get(key)))
            self.flt[key] = var
            ttk.Checkbutton(tg, text=TYPE_NAMES[key], variable=var, style="Pill.Toolbutton",
                            command=self._filter).pack(side="left", padx=3)

        sf = tk.Frame(self, bg=BG0)
        sf.grid(row=3, column=0, sticky="ew", padx=px(24), pady=px(6))
        sf.columnconfigure(1, weight=1)
        label(sf, "Search", fg=MUTED).grid(row=0, column=0, padx=(0, px(12)))
        self.q = tk.StringVar()
        self.q.trace_add("write", lambda *_: self._filter())
        ttk.Entry(sf, textvariable=self.q).grid(row=0, column=1, sticky="ew")

        tf = tk.Frame(self, bg=BG0)
        tf.grid(row=4, column=0, sticky="nsew", padx=px(24), pady=px(6))
        tf.columnconfigure(0, weight=1)
        tf.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(tf, columns=("ver", "type", "date"), show="headings", selectmode="browse")
        for col, text, w in (("ver", "Version", 280), ("type", "Type", 120), ("date", "Released", 120)):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=px(w), anchor="w")
        for t, colour in TYPE_COLORS.items():
            self.tree.tag_configure(t, foreground=colour)
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<<TreeviewSelect>>", self._load_loader_versions)

        lf = tk.Frame(self, bg=BG0)
        lf.grid(row=5, column=0, sticky="ew", padx=px(24), pady=px(8))
        lf.columnconfigure(3, weight=1)
        label(lf, "Mod loader", fg=MUTED).grid(row=0, column=0, padx=(0, px(10)))
        self.loader = tk.StringVar(value="Vanilla")
        lc = ttk.Combobox(lf, textvariable=self.loader, state="readonly", width=12,
                          values=[core.LOADER_NAMES[x] for x in core.LOADERS])
        lc.grid(row=0, column=1)
        lc.bind("<<ComboboxSelected>>", self._load_loader_versions)
        label(lf, "Loader version", fg=MUTED).grid(row=0, column=2, padx=(px(20), px(10)))
        self.lver = tk.StringVar()
        self.lcombo = ttk.Combobox(lf, textvariable=self.lver, state="disabled")
        self.lcombo.grid(row=0, column=3, sticky="ew")

        self.msg = tk.StringVar(value="Loading version list...")
        tk.Label(self, textvariable=self.msg, bg=BG0, fg=AMBER, font=FONTS["small"]
                 ).grid(row=6, column=0, sticky="w", padx=px(24))
        bf = tk.Frame(self, bg=BG0)
        bf.grid(row=7, column=0, sticky="e", padx=px(24), pady=px(18))
        NeonButton(bf, "Cancel", self.destroy, kind="ghost", width=110, height=44).pack(side="left", padx=6)
        NeonButton(bf, "Create instance", self._create, kind="primary", width=190, height=44).pack(side="left")

        app.when_manifest(self._populate)

    def _populate(self):
        if not self.winfo_exists():
            return
        m = self.app.manifest or {}
        self.versions = m.get("versions") or core.installed_vanilla_versions()
        self.msg.set("Offline - showing cached / already-installed versions only." if m.get("offline") else "")
        self._filter(select=(m.get("latest") or {}).get("release"))

    def _filter(self, select: str | None = None):
        types = {k for k, v in self.flt.items() if v.get()}
        for k, v in self.flt.items():
            self.app.cfg["show"][k] = v.get()
        q = self.q.get().strip().lower()
        sel = self.tree.selection()
        keep = select or (sel[0] if sel else None)
        self.tree.delete(*self.tree.get_children())
        for v in self.versions:
            if v.get("type") in types and q in v["id"].lower():
                self.tree.insert("", "end", iid=v["id"], tags=(v["type"],),
                                 values=(v["id"], TYPE_NAMES.get(v["type"], v["type"]), v.get("releaseTime", "")[:10]))
        if keep and self.tree.exists(keep):
            self.tree.selection_set(keep)
            self.tree.see(keep)

    def _loader_key(self) -> str:
        return self.loader.get().lower()

    def _load_loader_versions(self, *_):
        loader, sel = self._loader_key(), self.tree.selection()
        self.token += 1
        tok = self.token
        if loader == "vanilla" or not sel:
            self.lcombo.configure(values=[], state="disabled")
            self.lver.set("")
            return
        mc = sel[0]
        self.lcombo.configure(state="disabled")
        self.lver.set("loading...")

        def work():
            try:
                vs, err = core.list_loader_versions(loader, mc), ""
            except Exception as e:  # noqa: BLE001
                vs, err = [], str(e)
            self.app.ui(self._set_lvers, tok, vs, err, mc)

        threading.Thread(target=work, daemon=True).start()

    def _set_lvers(self, tok, vs, err, mc):
        if tok != self.token or not self.winfo_exists():
            return
        if vs:
            self.lcombo.configure(values=vs, state="readonly")
            self.lver.set(vs[0])
            self.msg.set("")
        else:
            self.lcombo.configure(values=[], state="disabled")
            self.lver.set("")
            self.msg.set(f"No {self.loader.get()} build found for {mc}." + (f" ({err})" if err else ""))

    def _create(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Pick a version", "Select a Minecraft version first.", parent=self)
            return
        loader, lv = self._loader_key(), self.lver.get()
        if loader != "vanilla" and (not lv or lv.startswith("loading")):
            messagebox.showwarning("No loader build", "No loader version is available for this Minecraft version.",
                                   parent=self)
            return
        inst = core.new_instance(self.name.get(), sel[0], loader, "" if loader == "vanilla" else lv)
        core.save_config(self.app.cfg)
        self.app.show_page("play")
        self.app.refresh_instances(select=inst["id"])
        self.destroy()


# =========================================================================== #
# Modrinth browser: mods, resource packs, shaders, modpacks
# =========================================================================== #
class ModrinthBrowser(tk.Toplevel):
    TYPES = {"Mods": "mod", "Resource packs": "resourcepack", "Shaders": "shader",
             "Modpacks (creates a new instance)": "modpack"}

    def __init__(self, app: "App", inst: dict):
        super().__init__(app)
        self.app, self.inst = app, inst
        self.token = 0
        self.offset = 0
        self.title(f"Modrinth - {inst['name']}")
        self.geometry(f"{px(960)}x{px(680)}")
        self.minsize(px(760), px(520))
        self.configure(bg=BG0)
        self.transient(app)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        label(self, "MODRINTH", font="h2").grid(row=0, column=0, sticky="w", padx=px(20), pady=(px(20), 0))
        bar = tk.Frame(self, bg=BG0)
        bar.grid(row=1, column=0, sticky="ew", padx=px(20), pady=(px(10), px(6)))
        bar.columnconfigure(1, weight=1)
        self.ptype = tk.StringVar(value="Mods")
        cb = ttk.Combobox(bar, textvariable=self.ptype, values=list(self.TYPES), state="readonly", width=30)
        cb.grid(row=0, column=0, padx=(0, px(8)))
        cb.bind("<<ComboboxSelected>>", lambda e: self.search())
        self.q = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=self.q)
        entry.grid(row=0, column=1, sticky="ew")
        entry.bind("<Return>", lambda e: self.search())
        NeonButton(bar, "Search", self.search, kind="ghost", width=100, height=38).grid(row=0, column=2, padx=(px(8), 0))
        entry.focus_set()

        self.info = tk.StringVar()
        tk.Label(self, textvariable=self.info, bg=BG0, fg=MUTED, font=FONTS["small"]
                 ).grid(row=2, column=0, sticky="w", padx=px(22))

        tf = tk.Frame(self, bg=BG0)
        tf.grid(row=3, column=0, sticky="nsew", padx=px(20), pady=px(8))
        tf.columnconfigure(0, weight=1)
        tf.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(tf, columns=("title", "author", "downloads", "desc"), show="headings",
                                 selectmode="browse")
        for col, text, w in (("title", "Name", 210), ("author", "Author", 110), ("downloads", "Downloads", 100),
                             ("desc", "Description", 440)):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=px(w), anchor="w")
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<Double-1>", lambda e: self.install())

        bot = tk.Frame(self, bg=BG0)
        bot.grid(row=4, column=0, sticky="ew", padx=px(20), pady=(0, px(18)))
        bot.columnconfigure(0, weight=1)
        self.status = tk.StringVar(value="Search for something, or leave the box empty for the most popular.")
        tk.Label(bot, textvariable=self.status, bg=BG0, fg=MUTED, font=FONTS["small"]).grid(row=0, column=0, sticky="w")
        NeonButton(bot, "Load more", lambda: self.search(more=True), kind="ghost", width=120, height=42
                   ).grid(row=0, column=1, padx=8)
        self.btn = NeonButton(bot, "Install selected", self.install, kind="primary", width=190, height=42)
        self.btn.grid(row=0, column=2)
        self.search()

    def _kind(self) -> str:
        return self.TYPES[self.ptype.get()]

    def search(self, more: bool = False):
        kind = self._kind()
        self.token += 1
        tok = self.token
        if not more:
            self.offset = 0
            self.tree.delete(*self.tree.get_children())
        inst = self.inst
        if kind == "modpack":
            self.info.set("Modpacks are installed as a brand-new instance.")
            mc = loader = None
        else:
            loader = inst["loader"] if kind == "mod" else None
            mc = inst["mc"]
            extra = f" · {core.LOADER_NAMES[inst['loader']]}" if kind == "mod" else ""
            self.info.set(f"Showing results compatible with Minecraft {inst['mc']}{extra}")
            if kind == "mod" and inst["loader"] == "vanilla":
                self.info.set("This is a Vanilla instance - create a Fabric / Quilt / Forge / NeoForge instance "
                              "to use mods.")
        self.status.set("Searching...")
        query, offset = self.q.get().strip(), self.offset

        def work():
            try:
                hits, err = core.modrinth_search(query, kind, mc, loader, offset=offset), ""
            except Exception as e:  # noqa: BLE001
                hits, err = [], str(e)
            self.app.ui(self._show, tok, hits, err)

        threading.Thread(target=work, daemon=True).start()

    def _show(self, tok, hits, err):
        if tok != self.token or not self.winfo_exists():
            return
        if err:
            self.status.set(f"Search failed: {err}")
            return
        for h in hits:
            if not self.tree.exists(h["project_id"]):
                desc = (h.get("description") or "").replace("\n", " ")
                self.tree.insert("", "end", iid=h["project_id"],
                                 values=(h["title"], h.get("author", ""), f"{h.get('downloads', 0):,}", desc))
        self.offset += len(hits)
        self.status.set(f"{len(self.tree.get_children())} results. Double-click or press Install."
                        if hits or self.offset else "Nothing found.")

    def install(self):
        sel = self.tree.selection()
        if not sel:
            return
        pid, kind, inst = sel[0], self._kind(), self.inst
        if kind == "mod" and inst["loader"] == "vanilla":
            messagebox.showinfo("Mod loader needed", "Create an instance with Fabric, Quilt, Forge or NeoForge "
                                "to install mods.", parent=self)
            return
        title = self.tree.set(pid, "title")
        self.btn.set_enabled(False)
        self.status.set(f"Installing {title}...")
        ctx = Ctx(on_status=lambda t: self.app.ui(self._set_status, t),
                  on_progress=lambda lab, d, t: self.app.ui(self._set_status, f"{lab} {d}/{t}"),
                  on_log=self.app.ctx.log)

        def work():
            try:
                if kind == "modpack":
                    new = core.modrinth_install_modpack(pid, ctx)
                    self.app.ui(self._finished, f"Created instance \"{new['name']}\" - press Play to finish setup.",
                                new["id"])
                else:
                    files = core.modrinth_install(pid, kind, inst, ctx)
                    self.app.ui(self._finished, "Installed: " + ", ".join(files), None)
            except Exception as e:  # noqa: BLE001
                self.app.ui(self._finished, f"Failed: {e}", None)

        threading.Thread(target=work, daemon=True).start()

    def _set_status(self, text):
        if self.winfo_exists():
            self.status.set(text)

    def _finished(self, text, new_id):
        if self.winfo_exists():
            self.status.set(text)
            self.btn.set_enabled(True)
        self.app.refresh_mods()
        if new_id:
            self.app.refresh_instances(select=new_id)


# =========================================================================== #
# Main window
# =========================================================================== #
class App(tk.Tk):
    PAGES = (("play", "PLAY"), ("mods", "MODS & PACKS"), ("settings", "SETTINGS"),
             ("console", "CONSOLE"), ("arcade", "ARCADE"))

    def __init__(self):
        super().__init__()
        theme.init_scale(self)
        theme.init_fonts(self)
        theme.apply_theme(self)
        self.title(f"{core.APP_NAME} {core.APP_VERSION}")
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(px(1200), sw - px(60)), min(px(800), sh - px(100))
        self.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 3)}")
        self.minsize(min(px(1040), w), min(px(700), h))
        self.configure(bg=BG0)
        try:
            self._icon = tk.PhotoImage(data=ICON_B64)  # keep a reference or Tk drops it
            self.iconphoto(True, self._icon)
        except tk.TclError:
            pass

        self.cfg = core.load_config()
        hs = self.cfg.setdefault("highscores", {})
        hs.setdefault("snake", 0)
        hs.setdefault("pong", 0)
        self.bus: queue.Queue = queue.Queue()
        self.manifest: dict | None = None
        self._pending: list = []
        self.insts: list[dict] = []
        self.cur: dict | None = None
        self.proc = None
        self.busy = False
        self.in_game = False
        self.stopping = False
        self.page = "play"
        self.ctx = Ctx(on_status=lambda t: self.ui(self._on_status, t),
                       on_progress=lambda lab, d, t: self.ui(self._set_progress, lab, d, t),
                       on_log=lambda s: self.ui(self._console_write, s))

        self._menu()
        self._build()
        self.refresh_instances()
        self.show_page("play")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(40, self._pump)
        threading.Thread(target=lambda: self.ui(self._manifest_ready, core.get_manifest()), daemon=True).start()

    # ---- thread -> UI plumbing ------------------------------------------------ #
    def ui(self, fn, *args):
        self.bus.put((fn, args))

    def _pump(self):
        for _ in range(300):
            try:
                fn, args = self.bus.get_nowait()
            except queue.Empty:
                break
            try:
                fn(*args)
            except tk.TclError:
                pass  # widget was destroyed while a message was in flight
            except Exception:  # noqa: BLE001  - never let one bad message kill the pump
                try:                       # a windowed .exe has no stderr, so report in the Console tab
                    self._console_write(traceback.format_exc())
                except Exception:  # noqa: BLE001
                    pass
        self.after(40, self._pump)

    def report_callback_exception(self, exc, val, tb):
        self._console_write("".join(traceback.format_exception(exc, val, tb)))
        messagebox.showerror("Unexpected error", f"{val}\n\n(Details are in the Console tab.)")

    def _manifest_ready(self, manifest):
        self.manifest = manifest
        pending, self._pending = self._pending, []
        for cb in pending:
            cb()

    def when_manifest(self, cb):
        if self.manifest is not None:
            cb()
        else:
            self._pending.append(cb)

    def save_highscores(self):
        core.save_config(self.cfg)

    def _menu(self):
        bar = tk.Menu(self)
        fm = tk.Menu(bar, tearoff=0)
        fm.add_command(label="New instance...", command=self.new_instance)
        fm.add_command(label="Import modpack (.mrpack)...", command=self.import_pack)
        fm.add_separator()
        fm.add_command(label="Open launcher data folder", command=lambda: core.open_folder(core.ROOT))
        fm.add_separator()
        fm.add_command(label="Quit", command=self.on_close)
        bar.add_cascade(label="File", menu=fm)
        hm = tk.Menu(bar, tearoff=0)
        hm.add_command(label="About", command=self.about)
        bar.add_cascade(label="Help", menu=hm)
        self.config(menu=bar)

    # ---- layout --------------------------------------------------------------------- #
    def _build(self):
        self.status_var = tk.StringVar(value="Ready")
        self.name_var = tk.StringVar(value=self.cfg.get("username", "Player"))
        self.chip_var = tk.StringVar()
        self.name_var.trace_add("write", lambda *_: self.chip_var.set(f"●  {self.name_var.get() or '—'}"))
        self.chip_var.set(f"●  {self.name_var.get()}")
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # -- sidebar
        side = tk.Frame(self, bg=BG1, width=px(290))
        side.grid(row=0, column=0, sticky="ns")
        side.pack_propagate(False)
        Logo(side).pack(fill="x")
        tk.Frame(side, bg=LINE, height=1).pack(fill="x", padx=px(18))
        label(side, "INSTANCES", bg=BG1, fg=MUTED, font="caps").pack(anchor="w", padx=px(24), pady=(px(18), px(8)))
        self.tree = ttk.Treeview(side, show="tree", selectmode="browse")
        self.tree.column("#0", width=px(250), stretch=True)
        self.tree.pack(fill="both", expand=True, padx=px(10))
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._on_select())
        bf = tk.Frame(side, bg=BG1)
        bf.pack(fill="x", padx=px(14), pady=px(14))
        bf.columnconfigure((0, 1), weight=1)
        for i, (text, cmd, kind) in enumerate((("+  New", self.new_instance, "primary"),
                                               ("Import pack", self.import_pack, "ghost"),
                                               ("Duplicate", self.duplicate, "ghost"),
                                               ("Delete", self.delete, "ghost"))):
            NeonButton(bf, text, cmd, kind=kind, width=122, height=40, font_key="small_b", bg=BG1
                       ).grid(row=i // 2, column=i % 2, padx=1, pady=1)

        # -- main column: nav + pages
        main = tk.Frame(self, bg=BG0)
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)
        nav = tk.Frame(main, bg=BG0)
        nav.grid(row=0, column=0, sticky="ew")
        tk.Frame(main, bg=LINE, height=1).grid(row=0, column=0, sticky="sew")
        self.nav: dict = {}
        for n, (key, text) in enumerate(self.PAGES):
            f = tk.Frame(nav, bg=BG0, cursor="hand2")
            f.pack(side="left", padx=(px(22) if n == 0 else 0, 0))
            lab = tk.Label(f, text=text, bg=BG0, fg=MUTED, font=FONTS["nav"], padx=px(16), pady=px(16),
                           cursor="hand2")
            lab.pack()
            bar = tk.Frame(f, bg=BG0, height=px(3))
            bar.pack(fill="x")
            for wdg in (f, lab):
                wdg.bind("<Button-1>", lambda e, k=key: self.show_page(k))
            self.nav[key] = (lab, bar)
        tk.Label(nav, textvariable=self.chip_var, bg=BG2, fg=ACCENT, font=FONTS["small_b"], padx=px(14),
                 pady=px(7)).pack(side="right", padx=px(24))
        self.container = tk.Frame(main, bg=BG0)
        self.container.grid(row=1, column=0, sticky="nsew")
        self.container.columnconfigure(0, weight=1)
        self.container.rowconfigure(0, weight=1)
        self.pages = {key: tk.Frame(self.container, bg=BG0) for key, _ in self.PAGES}
        for pg in self.pages.values():
            pg.grid(row=0, column=0, sticky="nsew")
        self._build_play(self.pages["play"])
        self._build_mods(self.pages["mods"])
        self._build_settings(self.pages["settings"])
        self._build_console(self.pages["console"])
        self.arcade = ArcadePage(self.pages["arcade"], self)
        self.arcade.pack(fill="both", expand=True)

        # -- footer: status text + global progress bar (visible on every page, including the Arcade)
        foot = tk.Frame(self, bg=BG1, height=px(40))
        foot.grid(row=1, column=0, columnspan=2, sticky="ew")
        foot.pack_propagate(False)
        tk.Frame(self, bg=LINE, height=1).grid(row=1, column=0, columnspan=2, sticky="new")
        tk.Label(foot, textvariable=self.status_var, bg=BG1, fg=MUTED, font=FONTS["small"]
                 ).pack(side="left", padx=px(20))
        label(foot, f"v{core.APP_VERSION}", bg=BG1, fg=MUTED, font="small").pack(side="right", padx=px(20))
        self.progress = NeonProgress(foot, width=340, height=10, bg=BG1)
        self.progress.pack(side="right", padx=px(12), pady=px(15))

    def show_page(self, name: str):
        self.page = name
        self.pages[name].tkraise()
        self._paint_nav()
        if name == "arcade":
            self.arcade.on_show()
        else:
            self.arcade.on_hide()

    def _paint_nav(self):
        for key, (lab, bar) in self.nav.items():
            on = key == self.page
            hint = key == "arcade" and self.busy and not self.in_game and not on   # nudge while downloads run
            lab.configure(fg=FG if on else (VIOLET if hint else MUTED))
            bar.configure(bg=ACCENT if on else BG0)

    def _build_play(self, p):
        p.columnconfigure(0, weight=1)
        self.hero = HeroBanner(p, height=250)
        self.hero.grid(row=0, column=0, sticky="ew")

        row = tk.Frame(p, bg=BG0)
        row.grid(row=1, column=0, sticky="ew", padx=px(40), pady=(px(28), 0))
        row.columnconfigure(2, weight=1)
        self.play_btn = NeonButton(row, "PLAY", self.play, kind="primary", width=260, height=68, font_key="play")
        self.play_btn.grid(row=0, column=0)
        self.stop_btn = NeonButton(row, "STOP", self.stop, kind="danger", width=120, height=68)
        self.stop_btn.grid(row=0, column=1, padx=px(14))
        self.stop_btn.grid_remove()
        card = Card(row, "Player")
        card.grid(row=0, column=2, sticky="e")
        ttk.Entry(card.body, textvariable=self.name_var, width=24).grid(row=1, column=0, sticky="ew")
        tk.Label(card.body, text="Offline account: singleplayer, LAN and offline-mode servers", bg=BG2, fg=MUTED,
                 font=FONTS["small"]).grid(row=2, column=0, sticky="w", pady=(px(6), 0))

        banner_bg = mix(BG0, VIOLET, 0.12)
        self.wait_banner = tk.Frame(p, bg=banner_bg, highlightthickness=1, highlightbackground=mix(BG0, VIOLET, 0.55))
        self.wait_banner.grid(row=2, column=0, sticky="ew", padx=px(40), pady=(px(24), 0))
        self.wait_banner.columnconfigure(0, weight=1)
        tk.Label(self.wait_banner, text="Setting things up. Downloads can take a few minutes - how about a quick game?",
                 bg=banner_bg, fg=FG, font=FONTS["ui"]).grid(row=0, column=0, sticky="w", padx=px(20), pady=px(14))
        NeonButton(self.wait_banner, "Open Arcade", lambda: self.show_page("arcade"), kind="ghost", width=150,
                   height=40, bg=banner_bg).grid(row=0, column=1, padx=px(14), pady=px(8))
        self.wait_banner.grid_remove()

        quick = tk.Frame(p, bg=BG0)
        quick.grid(row=3, column=0, sticky="w", padx=px(40), pady=px(22))
        for text, cmd in (("Open game folder", lambda: self.cur and core.open_folder(core.game_dir(self.cur))),
                          ("Open saves", lambda: self.cur and core.open_folder(core.game_dir(self.cur) / "saves")),
                          ("Open screenshots",
                           lambda: self.cur and core.open_folder(core.game_dir(self.cur) / "screenshots"))):
            NeonButton(quick, text, cmd, kind="ghost", width=170, height=40, font_key="small_b"
                       ).pack(side="left", padx=(0, px(10)))

    def _build_mods(self, p):
        p.columnconfigure(0, weight=1)
        p.rowconfigure(2, weight=1)
        bar = tk.Frame(p, bg=BG0)
        bar.grid(row=0, column=0, sticky="ew", padx=px(36), pady=(px(26), px(8)))
        NeonButton(bar, "Browse Modrinth", self.browse_modrinth, kind="primary", width=180, height=42
                   ).pack(side="left", padx=(0, px(10)))
        for text, cmd in (("Add files...", self.add_mod_files), ("Enable / Disable", self.toggle_mods),
                          ("Remove", self.remove_mods),
                          ("Open folder", lambda: self.cur and core.open_folder(core.mods_dir(self.cur)))):
            NeonButton(bar, text, cmd, kind="ghost", width=140, height=42, font_key="small_b"
                       ).pack(side="left", padx=(0, px(10)))
        self.mods_hint = tk.StringVar()
        tk.Label(p, textvariable=self.mods_hint, bg=BG0, fg=MUTED, font=FONTS["small"]
                 ).grid(row=1, column=0, sticky="w", padx=px(38))
        tf = tk.Frame(p, bg=BG0)
        tf.grid(row=2, column=0, sticky="nsew", padx=px(36), pady=px(12))
        tf.columnconfigure(0, weight=1)
        tf.rowconfigure(0, weight=1)
        self.mods = ttk.Treeview(tf, columns=("name", "size", "state"), show="headings", selectmode="extended")
        for col, text, w in (("name", "Mod file", 460), ("size", "Size", 100), ("state", "Status", 100)):
            self.mods.heading(col, text=text)
            self.mods.column(col, width=px(w), anchor="w")
        self.mods.tag_configure("off", foreground=MUTED)
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.mods.yview)
        self.mods.configure(yscrollcommand=sb.set)
        self.mods.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")

    def _build_settings(self, p):
        p.columnconfigure(0, weight=1)
        self.s_name, self.s_jvm, self.s_java = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.s_w, self.s_h = tk.StringVar(value="854"), tk.StringVar(value="480")
        self.s_ram, self.ram_lbl = tk.IntVar(value=2048), tk.StringVar()
        self.max_ram = max(2048, (core.total_ram_mb() - 1024) // 256 * 256)

        def row_label(parent, text, r):
            tk.Label(parent, text=text, bg=BG2, fg=FG, font=FONTS["ui"]).grid(row=r, column=0, sticky="w",
                                                                             padx=(0, px(18)), pady=px(8))

        c1 = Card(p, "Instance")
        c1.grid(row=0, column=0, sticky="ew", padx=px(36), pady=(px(28), px(12)))
        c1.body.columnconfigure(1, weight=1)
        row_label(c1.body, "Name", 1)
        ttk.Entry(c1.body, textvariable=self.s_name).grid(row=1, column=1, sticky="ew")
        row_label(c1.body, "Window size", 2)
        sz = tk.Frame(c1.body, bg=BG2)
        sz.grid(row=2, column=1, sticky="w")
        ttk.Entry(sz, textvariable=self.s_w, width=7).pack(side="left")
        tk.Label(sz, text="  ×  ", bg=BG2, fg=MUTED, font=FONTS["ui"]).pack(side="left")
        ttk.Entry(sz, textvariable=self.s_h, width=7).pack(side="left")

        c2 = Card(p, "Performance")
        c2.grid(row=1, column=0, sticky="ew", padx=px(36), pady=px(12))
        c2.body.columnconfigure(1, weight=1)
        row_label(c2.body, "Memory", 1)
        self.ram_scale = ttk.Scale(c2.body, from_=512, to=self.max_ram, orient="horizontal",
                                   command=self._ram_changed, style="Card.Horizontal.TScale")
        self.ram_scale.grid(row=1, column=1, sticky="ew")
        tk.Label(c2.body, textvariable=self.ram_lbl, bg=BG2, fg=ACCENT, font=FONTS["ui_b"], width=18
                 ).grid(row=1, column=2, padx=(px(12), 0))
        row_label(c2.body, "JVM arguments", 2)
        ttk.Entry(c2.body, textvariable=self.s_jvm).grid(row=2, column=1, columnspan=2, sticky="ew")

        c3 = Card(p, "Java")
        c3.grid(row=2, column=0, sticky="ew", padx=px(36), pady=px(12))
        c3.body.columnconfigure(1, weight=1)
        row_label(c3.body, "Path (blank = auto)", 1)
        ttk.Entry(c3.body, textvariable=self.s_java).grid(row=1, column=1, sticky="ew")
        ttk.Button(c3.body, text="Browse...", command=self._pick_java).grid(row=1, column=2, padx=(px(10), 0))
        tk.Label(c3.body, text="Java is downloaded automatically (the same builds Mojang ships), so you normally "
                               "don't need to install anything.", bg=BG2, fg=MUTED, font=FONTS["small"],
                 wraplength=px(700), justify="left").grid(row=2, column=0, columnspan=3, sticky="w", pady=(px(6), 0))
        NeonButton(p, "Save settings", self.save_settings, kind="primary", width=200, height=48
                   ).grid(row=3, column=0, sticky="w", padx=px(36), pady=px(18))

    def _build_console(self, p):
        p.columnconfigure(0, weight=1)
        p.rowconfigure(1, weight=1)
        bar = tk.Frame(p, bg=BG0)
        bar.grid(row=0, column=0, sticky="ew", padx=px(36), pady=(px(26), px(8)))
        NeonButton(bar, "Clear", self._console_clear, kind="ghost", width=100, height=38, font_key="small_b"
                   ).pack(side="left", padx=(0, px(10)))
        NeonButton(bar, "Copy all", self._console_copy, kind="ghost", width=110, height=38, font_key="small_b"
                   ).pack(side="left")
        wrap = tk.Frame(p, bg=BG1, highlightthickness=1, highlightbackground=LINE)
        wrap.grid(row=1, column=0, sticky="nsew", padx=px(36), pady=(0, px(24)))
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(0, weight=1)
        self.console = tk.Text(wrap, bg=BG1, fg="#c9d1d9", insertbackground=FG, relief="flat", borderwidth=0,
                               font=FONTS["mono"], wrap="none", state="disabled", padx=px(12), pady=px(10),
                               selectbackground="#123d29")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.console.yview)
        self.console.configure(yscrollcommand=sb.set)
        self.console.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        for tag, colour in (("launcher", ACCENT), ("warn", AMBER), ("error", DANGER)):
            self.console.tag_configure(tag, foreground=colour)

    # ---- console ------------------------------------------------------------------- #
    def _console_write(self, line: str):
        low = line.lower()
        tag = ("launcher" if line.startswith("[launcher]") else
               "error" if ("error" in low or "exception" in low or "fatal" in low) else
               "warn" if "warn" in low else None)
        self.console.configure(state="normal")
        self.console.insert("end", line + "\n", (tag,) if tag else ())
        n = int(self.console.index("end-1c").split(".")[0])
        if n > 6000:
            self.console.delete("1.0", f"{n - 5000}.0")
        self.console.see("end")
        self.console.configure(state="disabled")

    def _console_clear(self):
        self.console.configure(state="normal")
        self.console.delete("1.0", "end")
        self.console.configure(state="disabled")

    def _console_copy(self):
        self.clipboard_clear()
        self.clipboard_append(self.console.get("1.0", "end"))

    def _on_status(self, text):
        self.status_var.set(text)
        if self.busy and not self.in_game:
            self.progress.indeterminate()      # a new phase without numbers yet

    def _set_progress(self, lab, done, total):
        self.progress.set(done / max(total, 1))
        self.status_var.set(f"{lab}  {done}/{total}")

    # ---- instances ------------------------------------------------------------------- #
    def refresh_instances(self, select: str | None = None):
        self.insts = core.load_instances()
        self.tree.delete(*self.tree.get_children())
        for i in self.insts:
            loader = "" if i["loader"] == "vanilla" else f" {core.LOADER_NAMES[i['loader']]}"
            self.tree.insert("", "end", iid=i["id"], text=f"  {i['name']}   ·   {i['mc']}{loader}")
        ids = [i["id"] for i in self.insts]
        target = select if select in ids else (self.cfg.get("last_instance") if self.cfg.get("last_instance") in ids
                                               else (ids[0] if ids else None))
        if target:
            self.tree.selection_set(target)
            self.tree.see(target)
        self._on_select()

    def _on_select(self):
        sel = self.tree.selection()
        self.cur = next((i for i in self.insts if i["id"] == sel[0]), None) if sel else None
        inst = self.cur
        if inst:
            self.cfg["last_instance"] = inst["id"]
            loader = core.LOADER_NAMES[inst["loader"]].upper()
            if inst.get("loader_version"):
                loader += f" {inst['loader_version']}"
            chips = [(f"MINECRAFT {inst['mc']}", CYAN),
                     (loader, MUTED if inst["loader"] == "vanilla" else VIOLET),
                     (f"{inst.get('ram_mb', 2048) / 1024:.1f} GB RAM", ACCENT)]
            self.hero.set(inst["name"], ago(inst.get("last_played", 0)), chips)
        else:
            self.hero.set("No instance yet", "Press \"+ New\" in the sidebar to create your first one.", [])
        self._load_settings()
        self.refresh_mods()
        self._sync_buttons()

    def _sync_buttons(self):
        self.play_btn.set_enabled(bool(self.cur) and not self.busy)
        self.play_btn.set_text("RUNNING" if self.in_game else ("WORKING..." if self.busy else "PLAY"))
        if self.busy:
            self.stop_btn.grid()
        else:
            self.stop_btn.grid_remove()
        if self.busy and not self.in_game:
            self.wait_banner.grid()
        else:
            self.wait_banner.grid_remove()
        self._paint_nav()

    def new_instance(self):
        NewInstanceDialog(self)

    def import_pack(self):
        path = filedialog.askopenfilename(title="Import Modrinth modpack",
                                          filetypes=[("Modrinth modpack", "*.mrpack"), ("All files", "*.*")])
        if not path:
            return
        self.status_var.set("Importing modpack...")
        self.progress.indeterminate()

        def work():
            try:
                inst = core.import_mrpack(Path(path), self.ctx)
                self.ui(self._pack_done, inst, "")
            except Exception as e:  # noqa: BLE001
                self.ui(self._pack_done, None, str(e))

        threading.Thread(target=work, daemon=True).start()

    def _pack_done(self, inst, err):
        self.status_var.set("Ready")
        self.progress.idle()
        if err:
            messagebox.showerror("Import failed", err)
            return
        self.show_page("play")
        self.refresh_instances(select=inst["id"])
        messagebox.showinfo("Modpack imported", f"\"{inst['name']}\" is ready. Press Play - the game and loader "
                                                "download on first launch.")

    def duplicate(self):
        if self.cur and not self.busy:
            self.refresh_instances(select=core.duplicate_instance(self.cur)["id"])

    def delete(self):
        if not self.cur or self.busy:
            return
        if messagebox.askyesno("Delete instance", f"Delete \"{self.cur['name']}\" including its worlds, mods and "
                                                  "settings? This cannot be undone."):
            core.delete_instance(self.cur)
            self.cfg["last_instance"] = None
            self.refresh_instances()

    # ---- settings -------------------------------------------------------------------- #
    def _ram_changed(self, value):
        mb = max(512, int(round(float(value) / 256) * 256))
        self.s_ram.set(mb)
        self.ram_lbl.set(f"{mb} MB  ({mb / 1024:.1f} GB)")

    def _load_settings(self):
        inst = self.cur or {}
        self.s_name.set(inst.get("name", ""))
        self.s_jvm.set(inst.get("jvm_args", ""))
        self.s_java.set(inst.get("java_path", ""))
        self.s_w.set(str(inst.get("width", 854)))
        self.s_h.set(str(inst.get("height", 480)))
        self.ram_scale.set(min(inst.get("ram_mb", 2048), self.max_ram))
        self._ram_changed(self.ram_scale.get())

    def _pick_java(self):
        path = filedialog.askopenfilename(title="Select the java executable")
        if path:
            self.s_java.set(path)

    def save_settings(self):
        inst = self.cur
        if not inst:
            return
        inst["name"] = self.s_name.get().strip() or inst["name"]
        inst["ram_mb"] = int(self.s_ram.get())
        inst["jvm_args"] = self.s_jvm.get().strip()
        inst["java_path"] = self.s_java.get().strip()
        for key, var, default in (("width", self.s_w, 854), ("height", self.s_h, 480)):
            try:
                inst[key] = max(320, int(var.get()))
            except ValueError:
                inst[key] = default
        core.save_instance(inst)
        self.status_var.set("Settings saved.")
        self.refresh_instances(select=inst["id"])

    # ---- mods ------------------------------------------------------------------------- #
    def refresh_mods(self):
        self.mods.delete(*self.mods.get_children())
        inst = self.cur
        if not inst:
            self.mods_hint.set("")
            return
        if inst["loader"] == "vanilla":
            self.mods_hint.set("Vanilla instance: mods need Fabric, Quilt, Forge or NeoForge. "
                               "Resource packs and shaders still work.")
        else:
            self.mods_hint.set(f"{core.LOADER_NAMES[inst['loader']]} instance - add .jar files or browse Modrinth.")
        for p in core.list_mods(inst):
            off = p.name.endswith(".disabled")
            self.mods.insert("", "end", iid=p.name, tags=("off",) if off else (),
                             values=(p.name.removesuffix(".disabled"), f"{p.stat().st_size / 1048576:.2f} MB",
                                     "Disabled" if off else "Enabled"))

    def browse_modrinth(self):
        if self.cur:
            ModrinthBrowser(self, self.cur)
        else:
            messagebox.showinfo("No instance", "Create an instance first.")

    def add_mod_files(self):
        if not self.cur:
            return
        files = filedialog.askopenfilenames(title="Add mod files",
                                            filetypes=[("Mod files", "*.jar"), ("All files", "*.*")])
        if files:
            dest = core.mods_dir(self.cur)
            dest.mkdir(parents=True, exist_ok=True)
            for f in files:
                shutil.copy2(f, dest)
            self.refresh_mods()

    def toggle_mods(self):
        if self.cur:
            for name in self.mods.selection():
                core.toggle_mod(core.mods_dir(self.cur) / name)
            self.refresh_mods()

    def remove_mods(self):
        sel = self.mods.selection()
        if self.cur and sel and messagebox.askyesno("Remove", f"Delete {len(sel)} file(s)?"):
            for name in sel:
                (core.mods_dir(self.cur) / name).unlink(missing_ok=True)
            self.refresh_mods()

    # ---- play ------------------------------------------------------------------------- #
    def play(self):
        if self.busy or not self.cur:
            return
        name = self.name_var.get().strip()
        if not re.fullmatch(r"[A-Za-z0-9_]{3,16}", name):
            messagebox.showerror("Player name", "Use 3-16 characters: letters, numbers or underscore.")
            return
        self.cfg["username"] = name
        core.save_config(self.cfg)
        self.busy, self.in_game, self.stopping = True, False, False
        self.ctx.cancel.clear()
        self.progress.indeterminate()
        self._sync_buttons()
        threading.Thread(target=self._play_worker, args=(dict(self.cur),), daemon=True).start()

    def _play_worker(self, inst: dict):
        try:
            proc = core.prepare_launch(inst, self.cfg, self.ctx)
            self.proc = proc
            inst["last_played"] = time.time()
            core.save_instance(inst)
            self.ui(self._game_started)
            for line in proc.stdout:  # type: ignore[union-attr]
                self.ctx.log(line.rstrip("\n"))
            code = proc.wait()
            self.ctx.log(f"[launcher] Game exited with code {code}")
            if code != 0 and not self.stopping:
                self.ui(self._crashed, code)
        except Cancelled:
            self.ctx.log("[launcher] Cancelled.")
        except Exception as e:  # noqa: BLE001
            self.ctx.log(f"[launcher] ERROR: {e}")
            self.ui(messagebox.showerror, "Launch failed", str(e))
        finally:
            self.proc = None
            self.ui(self._play_done)

    def _game_started(self):
        self.in_game = True
        self.progress.idle()
        self.status_var.set("Minecraft is running...")
        self._sync_buttons()

    def _play_done(self):
        self.busy = self.in_game = False
        self.progress.idle()
        self.status_var.set("Ready")
        self.refresh_instances(select=self.cur["id"] if self.cur else None)

    def _crashed(self, code):
        self.show_page("console")
        messagebox.showwarning("Minecraft closed unexpectedly",
                               f"The game exited with code {code}.\nThe last lines of the Console tab usually "
                               "explain why (often a mod for the wrong version, or too little memory).")

    def stop(self):
        self.stopping = True
        self.ctx.cancel.set()
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()

    # ---- misc ----------------------------------------------------------------------------- #
    def about(self):
        messagebox.showinfo(f"About {core.APP_NAME}",
                            f"{core.APP_NAME} {core.APP_VERSION}\n\nData folder:\n{core.ROOT}\n\n"
                            "Mods, resource packs, shaders and modpacks come from Modrinth.\n"
                            "Not affiliated with Mojang or Microsoft.")

    def on_close(self):
        if self.busy and self.proc and self.proc.poll() is None:
            if not messagebox.askyesno("Quit", "Minecraft is still running. Quit and close the game too?"):
                return
            self.proc.terminate()
        self.arcade.on_hide()
        core.save_config(self.cfg)
        self.destroy()


def main():
    if core.OS_NAME == "windows":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:  # noqa: BLE001
            pass
    core.ensure_dirs()
    try:
        App().mainloop()
    except Exception:  # noqa: BLE001
        # a windowed .exe/.app has no console, so make startup failures visible and reportable
        log = core.ROOT / "crash.log"
        try:
            log.write_text(traceback.format_exc(), encoding="utf-8")
            messagebox.showerror(core.APP_NAME, f"The launcher failed to start.\nDetails were saved to:\n{log}")
        except Exception:  # noqa: BLE001
            pass
        raise


if __name__ == "__main__":
    main()
