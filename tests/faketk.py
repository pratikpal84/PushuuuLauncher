"""A fake tkinter good enough to run the launcher's Python logic headlessly, plus a PIL-backed Canvas
emulator so the custom-drawn widgets (buttons, progress, hero, logo, games) can be rendered to PNG."""
import sys, types
from PIL import Image, ImageDraw, ImageFont

REG = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
MONO = "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf"
_cache = {}
def pil_font(family, size, weight):
    px = max(6, int(round(abs(size) * 96 / 72)))
    path = MONO if "mono" in (family or "").lower() or family == "Courier" else (BOLD if weight == "bold" else REG)
    key = (path, px)
    if key not in _cache: _cache[key] = ImageFont.truetype(path, px)
    return _cache[key]

class TclError(Exception): pass
class Var:
    def __init__(self, master=None, value=None, **k): self.v = value if value is not None else ""
    def get(self): return self.v
    def set(self, v): self.v = v
    def trace_add(self, *a): pass
class TkInterp:
    def call(self, *a): return "x11"

class Widget:
    def __init__(self, *a, **k):
        self.kw = dict(k); self.items = {}; self.sel = (); self.order = []; self._val = 0; self.tk = TkInterp()
        self.master = a[0] if a else None
    def __getattr__(self, n):
        if n.startswith("__"): raise AttributeError(n)
        return lambda *a, **k: None
    def configure(self, *a, **k): self.kw.update(k)
    config = configure
    def insert(self, parent, idx, iid=None, **k): self.items[iid] = k; self.order.append(iid)
    def delete(self, *ids): self.items.clear(); self.order.clear()
    def get_children(self, *a): return tuple(self.order)
    def exists(self, iid): return iid in self.items
    def selection(self): return self.sel
    def selection_set(self, iid): self.sel = (iid,)
    def set(self, *a):
        if len(a) == 2: return self.items[a[0]]["values"][0]
        self._val = a[0]
    def get(self, *a): return self._val
    def index(self, *a): return "1.0"
    def winfo_exists(self): return True
    def winfo_width(self): return 300
    def winfo_height(self): return 12
    def winfo_screenwidth(self): return 1920
    def winfo_screenheight(self): return 1080
    def winfo_fpixels(self, s): return 96.0
    def state(self, *a): pass
    def after(self, ms, fn=None, *a): return "job"
class Tk(Widget):
    def mainloop(self): pass
    def report_callback_exception(self, *a): raise
class Toplevel(Widget): pass

class Canvas(Widget):
    """Draws onto a PIL image. Only the calls the launcher uses are implemented."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.cw, self.chh = int(k.get("width", 300)), int(k.get("height", 150))
        self.bgc = k.get("bg", "#000000"); self._reset()
    def _reset(self):
        self.img = Image.new("RGB", (self.cw, self.chh), self.bgc); self.d = ImageDraw.Draw(self.img, "RGBA")
    def resize_to(self, w, h): self.cw, self.chh = int(w), int(h); self._reset()
    def winfo_width(self): return self.cw
    def winfo_height(self): return self.chh
    def configure(self, *a, **k):
        super().configure(*a, **k)
        if "width" in k or "height" in k: pass
    config = configure
    def delete(self, *a): self._reset()
    @staticmethod
    def _c(c): return None if c in ("", None) else c
    def create_rectangle(self, x1, y1, x2, y2, fill="", outline="black", width=1, **k):
        self.d.rectangle((x1, y1, x2 - 1, y2 - 1), fill=self._c(fill), outline=self._c(outline), width=int(width))
    def create_oval(self, x1, y1, x2, y2, fill="", outline="black", width=1, **k):
        self.d.ellipse((x1, y1, x2 - 1, y2 - 1), fill=self._c(fill), outline=self._c(outline))
    def create_line(self, x1, y1, x2, y2, fill="black", width=1, **k): self.d.line((x1, y1, x2, y2), fill=fill, width=int(width))
    def create_polygon(self, pts, smooth=False, fill="", outline="", width=1, **k):
        p = [(pts[i], pts[i + 1]) for i in range(0, len(pts), 2)]
        if smooth:                                    # Tk's smoothing == quadratic B-spline == Chaikin corner cutting
            for _ in range(4):
                q = []
                for i in range(len(p)):
                    a, b = p[i], p[(i + 1) % len(p)]
                    q += [(0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]), (0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1])]
                p = q
        self.d.polygon(p, fill=self._c(fill), outline=self._c(outline))
    def create_text(self, x, y, text="", fill="white", font=None, anchor="center", **k):
        f = pil_font(getattr(font, "family", None), getattr(font, "size", 10), getattr(font, "weight", "normal"))
        self.d.text((x, y), text, fill=fill, font=f, anchor={"center": "mm", "w": "lm"}.get(anchor, "mm"))
    def create_image(self, *a, **k): pass

def mk(name, base=Widget): return type(name, (base,), {})

class Font:
    def __init__(self, root=None, family="Sans", size=10, weight="normal", **k): self.family, self.size, self.weight = family, size, weight
    def measure(self, text): return int(pil_font(self.family, self.size, self.weight).getlength(text))
    def actual(self, k): return "Liberation Sans"

def install():
    tk = types.ModuleType("tkinter")
    tk.Tk, tk.Toplevel, tk.TclError, tk.Canvas = Tk, Toplevel, TclError, Canvas
    tk.StringVar = tk.IntVar = tk.BooleanVar = Var
    for n in ("Menu", "PhotoImage", "Frame", "Label", "Text", "Misc"): setattr(tk, n, mk(n))
    ttk = types.ModuleType("tkinter.ttk")
    for n in ("Frame", "Label", "Button", "Entry", "Combobox", "Treeview", "Scrollbar", "Progressbar", "Notebook",
              "Scale", "Checkbutton", "Radiobutton", "Style"): setattr(ttk, n, mk(n))
    font = types.ModuleType("tkinter.font")
    font.Font = Font; font.nametofont = lambda n: Font(); font.families = lambda root=None: ["Liberation Sans"]
    msg = types.ModuleType("tkinter.messagebox"); shown = []
    for n in ("showinfo", "showwarning", "showerror"): setattr(msg, n, lambda *a, _n=n, **k: shown.append((_n, a[:2])))
    msg.askyesno = lambda *a, **k: True; msg.shown = shown
    fd = types.ModuleType("tkinter.filedialog"); fd.askopenfilename = lambda **k: ""; fd.askopenfilenames = lambda **k: ()
    tk.ttk, tk.font, tk.messagebox, tk.filedialog = ttk, font, msg, fd
    for name, mod in (("tkinter", tk), ("tkinter.ttk", ttk), ("tkinter.font", font),
                      ("tkinter.messagebox", msg), ("tkinter.filedialog", fd)): sys.modules[name] = mod
    return msg
