#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pushuuu Launcher - core logic (no GUI, no tkinter).

Handles: version manifest, installing game files (client, libraries, assets,
natives, logging config), Mojang's bundled Java runtimes, mod loaders
(Fabric / Quilt / Forge / NeoForge), Modrinth search + install, .mrpack
modpacks, instances and building the final launch command.

Everything here is importable and testable without a display.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote, urlparse

import requests

APP_NAME = "Pushuuu Launcher"
APP_VERSION = "2.0.0"
USER_AGENT = f"PushuuuLauncher/{APP_VERSION}"

# --------------------------------------------------------------------------- #
# Platform detection and folders
# --------------------------------------------------------------------------- #
if sys.platform.startswith("win"):
    OS_NAME = "windows"
elif sys.platform == "darwin":
    OS_NAME = "osx"
else:
    OS_NAME = "linux"

MACHINE = platform.machine().lower()
IS_ARM = MACHINE in ("arm64", "aarch64") or MACHINE.startswith("armv")
IS_64 = sys.maxsize > 2 ** 32
NO_WINDOW = {"creationflags": subprocess.CREATE_NO_WINDOW} if OS_NAME == "windows" else {}


def _data_root() -> Path:
    """Where everything lives. PUSHUUU_HOME or --portable override the default."""
    if os.environ.get("PUSHUUU_HOME"):
        return Path(os.environ["PUSHUUU_HOME"]).expanduser()
    if "--portable" in sys.argv:
        base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
        return base / "pushuuu_data"
    if OS_NAME == "windows":
        return Path(os.environ.get("APPDATA", str(Path.home()))) / "PushuuuLauncher"
    if OS_NAME == "osx":
        return Path.home() / "Library" / "Application Support" / "PushuuuLauncher"
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))) / "PushuuuLauncher"


ROOT = _data_root()
SHARED = ROOT / "shared"                  # versions / libraries / assets / runtime shared by all instances
VERSIONS_DIR = SHARED / "versions"
LIBS_DIR = SHARED / "libraries"
ASSETS_DIR = SHARED / "assets"
RUNTIME_DIR = SHARED / "runtime"
INSTANCES_DIR = ROOT / "instances"
CACHE_DIR = ROOT / "cache"
CONFIG_FILE = ROOT / "config.json"


def ensure_dirs() -> None:
    for d in (VERSIONS_DIR, LIBS_DIR, ASSETS_DIR, RUNTIME_DIR, INSTANCES_DIR, CACHE_DIR):
        d.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
# Small utilities
# --------------------------------------------------------------------------- #
class Cancelled(Exception):
    """Raised when the user cancels a running job."""


class Ctx:
    """Bridge between worker code and whatever UI is listening (or stdout)."""

    def __init__(self, on_status=None, on_progress=None, on_log=None):
        self.on_status = on_status or (lambda text: None)
        self.on_progress = on_progress or (lambda label, done, total: None)
        self.on_log = on_log or print
        self.cancel = threading.Event()

    def log(self, line: str) -> None:
        self.on_log(line)

    def status(self, text: str) -> None:
        self.on_status(text)
        self.on_log(f"[launcher] {text}")

    def progress(self, label: str, done: int, total: int) -> None:
        self.on_progress(label, done, total)

    def check(self) -> None:
        if self.cancel.is_set():
            raise Cancelled()


def read_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path: Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def safe_join(base: Path, rel: str) -> Path:
    """Join `rel` onto `base`, refusing anything that escapes `base` (zip-slip etc.)."""
    base = Path(base).resolve()
    p = (base / rel).resolve()
    if p != base and base not in p.parents:
        raise ValueError(f"Refusing unsafe path: {rel}")
    return p


def sha1_of(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def total_ram_mb() -> int:
    try:
        if OS_NAME == "linux":
            with open("/proc/meminfo", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemTotal"):
                        return int(line.split()[1]) // 1024
        elif OS_NAME == "osx":
            return int(subprocess.check_output(["sysctl", "-n", "hw.memsize"])) // (1024 * 1024)
        elif OS_NAME == "windows":
            import ctypes

            class MEMSTATUS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]

            st = MEMSTATUS()
            st.dwLength = ctypes.sizeof(st)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
            return int(st.ullTotalPhys // (1024 * 1024))
    except Exception:
        pass
    return 8192


def open_folder(path: Path) -> None:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    if OS_NAME == "windows":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif OS_NAME == "osx":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
http = requests.Session()
http.headers["User-Agent"] = USER_AGENT


def _retryable(exc: Exception) -> bool:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code >= 500 or exc.response.status_code == 429
    return True


def get_json(url: str, params=None, retries: int = 3, timeout: int = 20):
    last: Exception | None = None
    for i in range(retries):
        try:
            r = http.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            last = e
            if not _retryable(e):
                break
            time.sleep(0.6 * (i + 1))
    raise RuntimeError(f"Request failed: {url} ({last})")


def download(url: str, dest: Path, sha1: str | None = None, size: int | None = None, retries: int = 3) -> None:
    """Download atomically. Skips when the file already exists (and matches `size` if given)."""
    dest = Path(dest)
    if dest.exists() and (size is None or dest.stat().st_size == size):
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    last: Exception | None = None
    for i in range(retries):
        try:
            with http.get(url, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 16):
                        f.write(chunk)
            if sha1 and sha1_of(tmp).lower() != sha1.lower():
                raise OSError(f"checksum mismatch for {dest.name}")
            os.replace(tmp, dest)
            return
        except (requests.RequestException, OSError) as e:
            last = e
            time.sleep(1 + i)
    raise RuntimeError(f"Download failed: {url} ({last})")


def run_parallel(items, worker, ctx: Ctx, label: str, workers: int = 12, fatal: bool = True) -> int:
    """Run `worker(item)` on a thread pool, reporting progress. Returns failure count."""
    total = len(items)
    if not total:
        return 0
    done = failed = 0
    first_err: Exception | None = None
    ex = ThreadPoolExecutor(max_workers=workers)
    try:
        futures = [ex.submit(worker, it) for it in items]
        for fut in as_completed(futures):
            ctx.check()
            done += 1
            try:
                fut.result()
            except Exception as e:  # noqa: BLE001
                failed += 1
                first_err = first_err or e
            ctx.progress(label, done, total)
    except Cancelled:
        ex.shutdown(wait=False, cancel_futures=True)
        raise
    ex.shutdown(wait=True)
    if failed:
        msg = f"{failed} of {total} downloads failed ({first_err})"
        if fatal:
            raise RuntimeError(msg)
        ctx.log(f"[launcher] WARNING: {msg}")
    return failed


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
DEFAULT_JVM = ("-XX:+UnlockExperimentalVMOptions -XX:+UseG1GC -XX:G1NewSizePercent=20 "
               "-XX:G1ReservePercent=20 -XX:MaxGCPauseMillis=50 -XX:G1HeapRegionSize=32M")
VERSION_TYPES = ("release", "snapshot", "old_beta", "old_alpha")


def load_config() -> dict:
    cfg = {"username": "Player", "last_instance": None,
           "show": {"release": True, "snapshot": False, "old_beta": False, "old_alpha": False}}
    saved = read_json(CONFIG_FILE, {}) or {}
    cfg.update({k: v for k, v in saved.items() if k != "show"})
    cfg["show"].update(saved.get("show", {}))
    return cfg


def save_config(cfg: dict) -> None:
    write_json(CONFIG_FILE, cfg)


def offline_uuid(name: str) -> str:
    """Same UUID the game/servers derive for offline-mode players."""
    h = bytearray(hashlib.md5(("OfflinePlayer:" + name).encode("utf-8")).digest())
    h[6] = (h[6] & 0x0F) | 0x30
    h[8] = (h[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(h)))


# --------------------------------------------------------------------------- #
# Mojang version manifest and version JSON
# --------------------------------------------------------------------------- #
MANIFEST_URLS = [
    "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json",
    "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json",
]


def get_manifest() -> dict:
    """Fetch the full version list (every release, snapshot, beta and alpha). Cached for offline use."""
    cache = CACHE_DIR / "version_manifest.json"
    for url in MANIFEST_URLS:
        try:
            data = get_json(url, retries=2, timeout=10)
            write_json(cache, data)
            data["offline"] = False
            return data
        except Exception:  # noqa: BLE001
            continue
    data = read_json(cache)
    if data:
        data["offline"] = True
        return data
    return {"latest": {}, "versions": [], "offline": True}


def installed_vanilla_versions() -> list[dict]:
    out = []
    if VERSIONS_DIR.exists():
        for d in VERSIONS_DIR.iterdir():
            meta = read_json(d / f"{d.name}.json")
            if meta and "inheritsFrom" not in meta:
                out.append({"id": meta.get("id", d.name), "type": meta.get("type", "release"),
                            "releaseTime": meta.get("releaseTime", "")})
    return sorted(out, key=lambda v: v["releaseTime"], reverse=True)


def version_json_path(vid: str) -> Path:
    return VERSIONS_DIR / vid / f"{vid}.json"


def ensure_vanilla_json(vid: str, ctx: Ctx) -> None:
    p = version_json_path(vid)
    if p.exists():
        return
    ctx.status(f"Fetching metadata for Minecraft {vid}")
    entry = next((v for v in get_manifest()["versions"] if v["id"] == vid), None)
    if not entry:
        raise RuntimeError(f"Minecraft {vid} was not found in Mojang's manifest (are you offline?)")
    download(entry["url"], p, sha1=entry.get("sha1"))


# ---- rules ---------------------------------------------------------------- #
def _os_matches(rule_os: dict | None) -> bool:
    if not rule_os:
        return True
    if "name" in rule_os and rule_os["name"] != OS_NAME:
        return False
    if "arch" in rule_os:
        a = rule_os["arch"]
        if a == "x86":
            ok = (not IS_64) and not IS_ARM
        elif a in ("arm64", "aarch64"):
            ok = IS_ARM
        else:
            ok = a == MACHINE
        if not ok:
            return False
    if "version" in rule_os:
        try:
            if not re.search(rule_os["version"], platform.version()):
                return False
        except re.error:
            pass
    return True


def rules_allow(rules: list | None, features: dict | None = None) -> bool:
    if not rules:
        return True
    features = features or {}
    allowed = False
    for r in rules:
        ok = _os_matches(r.get("os"))
        if ok and "features" in r:
            ok = all(features.get(k, False) == v for k, v in r["features"].items())
        if ok:
            allowed = r.get("action") == "allow"
    return allowed


# ---- libraries ------------------------------------------------------------ #
def maven_path(name: str) -> str:
    ext = "jar"
    if "@" in name:
        name, ext = name.split("@", 1)
    parts = name.split(":")
    group, artifact, version = parts[0], parts[1], parts[2]
    classifier = parts[3] if len(parts) > 3 else None
    fname = f"{artifact}-{version}" + (f"-{classifier}" if classifier else "") + f".{ext}"
    return f"{group.replace('.', '/')}/{artifact}/{version}/{fname}"


def lib_key(lib: dict) -> str:
    parts = lib["name"].split("@")[0].split(":")
    return f"{parts[0]}:{parts[1]}:{parts[3] if len(parts) > 3 else ''}"


def merge_versions(parent: dict, child: dict) -> dict:
    """Apply `inheritsFrom`: child libs first (they win on duplicates), arguments concatenated."""
    out = dict(parent)
    for k, v in child.items():
        if k not in ("libraries", "arguments", "inheritsFrom"):
            out[k] = v
    seen, libs = set(), []
    for lib in list(child.get("libraries", [])) + list(parent.get("libraries", [])):
        k = lib_key(lib)
        if k not in seen:
            seen.add(k)
            libs.append(lib)
    out["libraries"] = libs
    pa, ca = parent.get("arguments"), child.get("arguments")
    if pa or ca:
        out["arguments"] = {k: list((pa or {}).get(k, [])) + list((ca or {}).get(k, [])) for k in ("game", "jvm")}
    out["_jar_id"] = child.get("jar") or parent.get("_jar_id") or parent.get("id")
    out["id"] = child["id"]
    return out


def load_version(vid: str, _depth: int = 0) -> dict:
    meta = json.loads(version_json_path(vid).read_text(encoding="utf-8"))
    if "inheritsFrom" in meta and _depth < 5:
        return merge_versions(load_version(meta["inheritsFrom"], _depth + 1), meta)
    meta["_jar_id"] = meta.get("jar") or vid
    return meta


def native_classifier(lib: dict) -> str | None:
    n = lib.get("natives")
    if not n or OS_NAME not in n:
        return None
    return n[OS_NAME].replace("${arch}", "64" if IS_64 else "32")


def resolve_libs(full: dict):
    """-> (classpath entries, artifacts to download, natives to extract)"""
    cp: list[Path] = []
    arts: list[dict] = []
    natives: list[dict] = []
    for lib in full.get("libraries", []):
        if not rules_allow(lib.get("rules")):
            continue
        d = lib.get("downloads")
        art = None
        if d and "artifact" in d:
            art = d["artifact"]
        elif not d and "name" in lib:  # maven-style entry (Fabric, Quilt, old Forge)
            p = maven_path(lib["name"])
            base = lib.get("url", "https://libraries.minecraft.net/")
            art = {"path": p, "url": base.rstrip("/") + "/" + p, "sha1": None, "size": None}
        if art:
            cp.append(LIBS_DIR / art["path"])
            arts.append(art)
        cls = native_classifier(lib)
        if cls and d and cls in d.get("classifiers", {}):
            n = d["classifiers"][cls]
            natives.append({**n, "exclude": lib.get("extract", {}).get("exclude", [])})
            arts.append(n)
    return cp, arts, natives


# --------------------------------------------------------------------------- #
# Installing game files
# --------------------------------------------------------------------------- #
def install_client_jar(full: dict, ctx: Ctx) -> Path:
    jid = full["_jar_id"]
    jar = VERSIONS_DIR / jid / f"{jid}.jar"
    dl = full.get("downloads", {}).get("client")
    if dl:
        ctx.status("Checking game files")
        download(dl["url"], jar, sha1=dl.get("sha1"), size=dl.get("size"))
    elif not jar.exists():
        raise RuntimeError(f"Client jar for {jid} is missing")
    return jar


def install_libraries(arts: list[dict], ctx: Ctx) -> None:
    todo, seen = [], set()
    for a in arts:
        if a["path"] in seen:
            continue
        seen.add(a["path"])
        dest = LIBS_DIR / a["path"]
        if dest.exists() and (not a.get("size") or dest.stat().st_size == a["size"]):
            continue
        if not a.get("url"):
            ctx.log(f"[launcher] library has no download URL and is missing: {a['path']}")
            continue
        todo.append(a)
    if todo:
        ctx.status(f"Downloading {len(todo)} libraries")
    run_parallel(todo, lambda a: download(a["url"], LIBS_DIR / a["path"], a.get("sha1"), a.get("size")),
                 ctx, "Libraries", workers=8)


def extract_natives(natives: list[dict], natives_dir: Path) -> None:
    natives_dir.mkdir(parents=True, exist_ok=True)
    marker = natives_dir / ".done"
    if marker.exists():
        return
    for n in natives:
        jar = LIBS_DIR / n["path"]
        if not jar.exists():
            continue
        with zipfile.ZipFile(jar) as z:
            for info in z.infolist():
                if info.is_dir() or any(info.filename.startswith(e) for e in n.get("exclude", [])):
                    continue
                target = safe_join(natives_dir, info.filename)
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
    marker.write_text("ok")


def install_assets(full: dict, game_dir: Path, ctx: Ctx) -> Path:
    """Download the asset index + objects. Returns the folder to use as ${game_assets}."""
    ai = full.get("assetIndex")
    if not ai:
        return ASSETS_DIR
    idx_path = ASSETS_DIR / "indexes" / f"{ai['id']}.json"
    download(ai["url"], idx_path, sha1=ai.get("sha1"), size=ai.get("size"))
    index = json.loads(idx_path.read_text(encoding="utf-8"))
    objects = index["objects"]

    todo = {}
    for info in objects.values():
        h = info["hash"]
        p = ASSETS_DIR / "objects" / h[:2] / h
        if h not in todo and (not p.exists() or p.stat().st_size != info["size"]):
            todo[h] = info
    if todo:
        ctx.status(f"Downloading {len(todo)} assets (sounds, languages, textures)")

    def worker(h):
        download(f"https://resources.download.minecraft.net/{h[:2]}/{h}", ASSETS_DIR / "objects" / h[:2] / h,
                 sha1=h, size=todo[h]["size"])

    run_parallel(list(todo), worker, ctx, "Assets", workers=16, fatal=False)

    game_assets = ASSETS_DIR
    if index.get("virtual") or index.get("map_to_resources"):
        game_assets = ASSETS_DIR / "virtual" / ai["id"]
        for name, info in objects.items():
            src = ASSETS_DIR / "objects" / info["hash"][:2] / info["hash"]
            targets = [safe_join(game_assets, name)]
            if index.get("map_to_resources"):
                targets.append(safe_join(game_dir / "resources", name))
            for t in targets:
                if src.exists() and not t.exists():
                    t.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src, t)
    return game_assets


def install_logging(full: dict) -> str | None:
    """Mojang's log4j config (this also hardens older versions against Log4Shell)."""
    lg = (full.get("logging") or {}).get("client")
    if not lg:
        return None
    f = lg["file"]
    path = ASSETS_DIR / "log_configs" / f["id"]
    try:
        download(f["url"], path, sha1=f.get("sha1"), size=f.get("size"))
    except RuntimeError:
        return None
    return lg["argument"].replace("${path}", str(path))


# --------------------------------------------------------------------------- #
# Java
# --------------------------------------------------------------------------- #
RUNTIME_INDEX = ("https://launchermeta.mojang.com/v1/products/java-runtime/"
                 "2ec0cc96c44e5a76b9c8b7c39df7210883d12871/all.json")


def runtime_platform() -> str | None:
    if OS_NAME == "windows":
        return "windows-arm64" if IS_ARM else ("windows-x64" if IS_64 else "windows-x86")
    if OS_NAME == "osx":
        return "mac-os-arm64" if IS_ARM else "mac-os"
    if IS_ARM:
        return None  # Mojang ships no Linux ARM runtimes - use system Java
    return "linux" if IS_64 else "linux-i386"


def _java_exe() -> str:
    return "java.exe" if OS_NAME == "windows" else "java"


def find_java_in(root: Path) -> Path | None:
    if not root.exists():
        return None
    for p in root.rglob(_java_exe()):
        if p.parent.name == "bin" and p.is_file():
            return p
    return None


def install_mojang_runtime(component: str, ctx: Ctx) -> Path | None:
    """Download the same Java build the official launcher uses for this game version."""
    plat = runtime_platform()
    if not plat:
        return None
    root = RUNTIME_DIR / plat / component
    if (root / ".installed").exists():
        found = find_java_in(root)
        if found:
            return found
    try:
        idx = get_json(RUNTIME_INDEX)
        entries = idx.get(plat, {}).get(component) or []
        if not entries:
            return None
        files = get_json(entries[0]["manifest"]["url"])["files"]
    except RuntimeError as e:
        ctx.log(f"[launcher] could not fetch Java runtime list: {e}")
        return None

    ctx.status(f"Downloading Java runtime ({component})")
    jobs, links = [], []
    for rel, info in files.items():
        target = safe_join(root, rel)
        kind = info.get("type")
        if kind == "directory":
            target.mkdir(parents=True, exist_ok=True)
        elif kind == "file":
            raw = info["downloads"]["raw"]
            jobs.append((raw["url"], target, raw.get("sha1"), raw.get("size"), info.get("executable", False)))
        elif kind == "link":
            links.append((target, info["target"]))

    def worker(job):
        url, dest, sha1, size, executable = job
        download(url, dest, sha1, size)
        if executable and OS_NAME != "windows":
            dest.chmod(dest.stat().st_mode | 0o111)

    run_parallel(jobs, worker, ctx, "Java runtime", workers=16)
    if OS_NAME != "windows":
        for target, to in links:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_symlink() or target.exists():
                target.unlink()
            os.symlink(to, target)
    (root / ".installed").write_text(str(time.time()))
    return find_java_in(root)


def find_system_java() -> str | None:
    cands = []
    jh = os.environ.get("JAVA_HOME")
    if jh:
        cands.append(Path(jh) / "bin" / _java_exe())
    w = shutil.which("java")
    if w:
        cands.append(Path(w))
    for c in cands:
        if c.exists():
            return str(c)
    return None


def resolve_java(inst: dict, full: dict, ctx: Ctx) -> str:
    custom = (inst.get("java_path") or "").strip()
    if custom:
        if Path(custom).exists():
            return custom
        ctx.log(f"[launcher] custom Java path not found, ignoring: {custom}")
    jv = full.get("javaVersion") or {"component": "jre-legacy", "majorVersion": 8}
    j = install_mojang_runtime(jv["component"], ctx)
    if j:
        return str(j)
    sj = find_system_java()
    if sj:
        ctx.log(f"[launcher] Using system Java ({sj}). This game wants Java {jv['majorVersion']}.")
        return sj
    raise RuntimeError(f"No Java found. Install Java {jv['majorVersion']} or set a Java path in the instance settings.")


# --------------------------------------------------------------------------- #
# Mod loaders
# --------------------------------------------------------------------------- #
LOADERS = ["vanilla", "fabric", "quilt", "forge", "neoforge"]
LOADER_NAMES = {"vanilla": "Vanilla", "fabric": "Fabric", "quilt": "Quilt", "forge": "Forge", "neoforge": "NeoForge"}
LOADER_COMPAT = {"fabric": ["fabric"], "quilt": ["quilt", "fabric"], "forge": ["forge"], "neoforge": ["neoforge"]}
FABRIC_META = "https://meta.fabricmc.net/v2"
QUILT_META = "https://meta.quiltmc.org/v3"
FORGE_META = "https://maven.minecraftforge.net/net/minecraftforge/forge/maven-metadata.xml"
NEOFORGE_API = "https://maven.neoforged.net/api/maven/versions/releases/net/neoforged/neoforge"


def neoforge_matcher(mc: str):
    """NeoForge versions encode the MC version: 1.21.1 -> 21.1.x, 26.1 -> 26.1.0.x, 26.1.2 -> 26.1.2.x"""
    if "-snapshot-" in mc:
        base, _, n = mc.partition("-snapshot-")
        return lambda v: v.startswith(base + ".0.") and v.endswith(f"+snapshot-{n}")
    if "-" in mc:
        return lambda v: False  # pre-releases / RCs have no NeoForge builds
    p = mc.split(".")
    if p[0] == "1" and len(p) >= 2:
        prefix = f"{p[1]}.{p[2] if len(p) > 2 else 0}."
    elif len(p) == 2:
        prefix = f"{p[0]}.{p[1]}.0."
    else:
        prefix = ".".join(p[:3]) + "."
    return lambda v: v.startswith(prefix)


def list_loader_versions(loader: str, mc: str) -> list[str]:
    """Loader builds available for a Minecraft version, newest first."""
    if loader in ("fabric", "quilt"):
        base = FABRIC_META if loader == "fabric" else QUILT_META
        data = get_json(f"{base}/versions/loader/{quote(mc, safe='')}")
        vs = [d["loader"]["version"] for d in data]
        stable = [v for v in vs if not re.search(r"alpha|beta|rc|pre", v, re.I)]
        return stable or vs
    if loader == "forge":
        r = http.get(FORGE_META, timeout=20)
        r.raise_for_status()
        vs = re.findall(r"<version>([^<]+)</version>", r.text)
        return [v for v in reversed(vs) if v.startswith(mc + "-")]
    if loader == "neoforge":
        vs = get_json(NEOFORGE_API).get("versions", [])
        match = neoforge_matcher(mc)
        return [v for v in reversed(vs) if match(v)]
    return []


def _find_loader_dir(core: str) -> str | None:
    if not VERSIONS_DIR.exists():
        return None
    dirs = sorted(VERSIONS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for d in dirs:
        if core in d.name and "forge" in d.name.lower() and (d / f"{d.name}.json").exists():
            return d.name
    return None


def _run_forge_installer(loader: str, mc: str, lver: str, ctx: Ctx) -> str:
    if loader == "forge":
        url = f"https://maven.minecraftforge.net/net/minecraftforge/forge/{lver}/forge-{lver}-installer.jar"
        core = lver.split("-")[1] if "-" in lver else lver
    else:
        url = f"https://maven.neoforged.net/releases/net/neoforged/neoforge/{lver}/neoforge-{lver}-installer.jar"
        core = lver
    existing = _find_loader_dir(core)
    if existing:
        return existing

    vfull = load_version(mc)
    install_client_jar(vfull, ctx)
    installer = CACHE_DIR / "installers" / f"{loader}-{lver}-installer.jar"
    ctx.status(f"Downloading {LOADER_NAMES[loader]} {lver} installer")
    download(url, installer)
    profiles = SHARED / "launcher_profiles.json"  # the installers insist on this file existing
    if not profiles.exists():
        write_json(profiles, {"profiles": {}, "settings": {}, "version": 3})

    java = resolve_java({}, vfull, ctx)
    ctx.status(f"Running the {LOADER_NAMES[loader]} installer (this can take a few minutes)")
    proc = subprocess.Popen([java, "-jar", str(installer), "--installClient", str(SHARED)], cwd=str(SHARED),
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", **NO_WINDOW)
    for line in proc.stdout:  # type: ignore[union-attr]
        ctx.check()
        ctx.log(line.rstrip())
    if proc.wait() != 0:
        raise RuntimeError(f"The {LOADER_NAMES[loader]} installer failed - see the Console tab.")
    vid = _find_loader_dir(core)
    if not vid:
        raise RuntimeError(f"{LOADER_NAMES[loader]} installed but its version folder was not found.")
    return vid


def install_loader(loader: str, mc: str, lver: str, ctx: Ctx) -> str:
    """Install a loader for a Minecraft version and return the version id to launch."""
    ensure_vanilla_json(mc, ctx)
    if loader == "vanilla":
        return mc
    if loader in ("fabric", "quilt"):
        base = FABRIC_META if loader == "fabric" else QUILT_META
        ctx.status(f"Installing {LOADER_NAMES[loader]} {lver}")
        prof = get_json(f"{base}/versions/loader/{quote(mc, safe='')}/{quote(lver, safe='')}/profile/json")
        write_json(version_json_path(prof["id"]), prof)
        return prof["id"]
    return _run_forge_installer(loader, mc, lver, ctx)


# --------------------------------------------------------------------------- #
# Instances
# --------------------------------------------------------------------------- #
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def slugify(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip()).strip("-.") or "instance"
    return s + "_" if s.upper() in _RESERVED else s


def instance_dir(iid: str) -> Path:
    return INSTANCES_DIR / iid


def game_dir(inst: dict) -> Path:
    return INSTANCES_DIR / inst["id"] / "minecraft"


def describe_instance(inst: dict) -> str:
    s = f"Minecraft {inst['mc']}"
    if inst["loader"] != "vanilla":
        s += f" · {LOADER_NAMES[inst['loader']]} {inst.get('loader_version', '')}".rstrip()
    return f"{s} · {inst.get('ram_mb', 2048)} MB"


def load_instances() -> list[dict]:
    out = []
    if INSTANCES_DIR.exists():
        for f in INSTANCES_DIR.glob("*/instance.json"):
            data = read_json(f)
            if data and "id" in data and "mc" in data:
                out.append(data)
    return sorted(out, key=lambda i: (-(i.get("last_played") or 0), i["name"].lower()))


def save_instance(inst: dict) -> None:
    write_json(instance_dir(inst["id"]) / "instance.json", inst)


def new_instance(name: str, mc: str, loader: str = "vanilla", loader_version: str = "") -> dict:
    name = name.strip() or (f"{LOADER_NAMES[loader]} {mc}" if loader != "vanilla" else f"Minecraft {mc}")
    base = slugify(name)
    iid, n = base, 2
    while instance_dir(iid).exists():
        iid, n = f"{base}-{n}", n + 1
    ram = 4096 if loader != "vanilla" else 2048
    ram = max(1024, min(ram, (total_ram_mb() // 2) // 256 * 256))
    inst = {"id": iid, "name": name, "mc": mc, "loader": loader, "loader_version": loader_version,
            "version_id": mc if loader == "vanilla" else "", "ram_mb": ram, "jvm_args": DEFAULT_JVM,
            "java_path": "", "width": 854, "height": 480, "created": time.time(), "last_played": 0}
    game_dir(inst).mkdir(parents=True, exist_ok=True)
    save_instance(inst)
    return inst


def duplicate_instance(inst: dict) -> dict:
    new = new_instance(inst["name"] + " copy", inst["mc"], inst["loader"], inst.get("loader_version", ""))
    shutil.rmtree(game_dir(new))
    shutil.copytree(game_dir(inst), game_dir(new))
    for k in ("version_id", "ram_mb", "jvm_args", "java_path", "width", "height"):
        new[k] = inst.get(k, new[k])
    save_instance(new)
    return new


def delete_instance(inst: dict) -> None:
    shutil.rmtree(instance_dir(inst["id"]), ignore_errors=True)


# ---- mods on disk --------------------------------------------------------- #
def mods_dir(inst: dict) -> Path:
    return game_dir(inst) / "mods"


def list_mods(inst: dict) -> list[Path]:
    d = mods_dir(inst)
    if not d.exists():
        return []
    files = [p for p in d.iterdir() if p.is_file() and (p.suffix == ".jar" or p.name.endswith(".jar.disabled"))]
    return sorted(files, key=lambda p: p.name.lower())


def toggle_mod(path: Path) -> Path:
    if path.name.endswith(".disabled"):
        new = path.with_name(path.name[: -len(".disabled")])
    else:
        new = path.with_name(path.name + ".disabled")
    path.rename(new)
    return new


# --------------------------------------------------------------------------- #
# Modrinth (mods, resource packs, shaders, modpacks)
# --------------------------------------------------------------------------- #
MODRINTH = "https://api.modrinth.com/v2"
PROJECT_SUBDIR = {"mod": "mods", "resourcepack": "resourcepacks", "shader": "shaderpacks"}
MRPACK_HOSTS = {"cdn.modrinth.com", "github.com", "raw.githubusercontent.com", "gitlab.com"}


def modrinth_search(query: str, ptype: str, mc: str | None, loader: str | None,
                    offset: int = 0, limit: int = 30) -> list[dict]:
    facets = [[f"project_type:{ptype}"]]
    if mc:
        facets.append([f"versions:{mc}"])
    if loader and ptype in ("mod", "modpack") and loader in LOADER_COMPAT:
        facets.append([f"categories:{c}" for c in LOADER_COMPAT[loader]])
    params = {"query": query, "facets": json.dumps(facets), "limit": limit, "offset": offset,
              "index": "relevance" if query else "downloads"}
    return get_json(f"{MODRINTH}/search", params=params).get("hits", [])


def modrinth_pick_version(project_id: str, mc: str | None, loaders: list[str] | None) -> dict | None:
    params = {}
    if mc:
        params["game_versions"] = json.dumps([mc])
    if loaders:
        params["loaders"] = json.dumps(loaders)
    versions = get_json(f"{MODRINTH}/project/{quote(project_id, safe='')}/version", params=params)
    for kind in ("release", "beta", "alpha"):
        for v in versions:
            if v.get("version_type") == kind:
                return v
    return versions[0] if versions else None


def _primary_file(version: dict) -> dict:
    return next((f for f in version["files"] if f.get("primary")), version["files"][0])


def modrinth_install(project_id: str, ptype: str, inst: dict, ctx: Ctx, _seen: set | None = None) -> list[str]:
    """Install a mod / resource pack / shader (plus required dependencies for mods)."""
    seen = _seen if _seen is not None else set()
    if project_id in seen:
        return []
    seen.add(project_id)
    loaders = LOADER_COMPAT.get(inst["loader"]) if ptype == "mod" else None
    v = modrinth_pick_version(project_id, inst["mc"], loaders)
    if not v:
        raise RuntimeError(f"No version compatible with Minecraft {inst['mc']}"
                           + (f" / {LOADER_NAMES[inst['loader']]}" if ptype == "mod" else ""))
    f = _primary_file(v)
    dest = safe_join(game_dir(inst) / PROJECT_SUBDIR[ptype], f["filename"])
    ctx.status(f"Downloading {f['filename']}")
    download(f["url"], dest, sha1=f.get("hashes", {}).get("sha1"), size=f.get("size"))
    installed = [f["filename"]]
    if ptype == "mod":
        for dep in v.get("dependencies", []):
            if dep.get("dependency_type") == "required" and dep.get("project_id"):
                installed += modrinth_install(dep["project_id"], "mod", inst, ctx, seen)
    return installed


def modrinth_install_modpack(project_id: str, ctx: Ctx) -> dict:
    v = modrinth_pick_version(project_id, None, None)
    if not v:
        raise RuntimeError("This modpack has no downloadable versions.")
    f = _primary_file(v)
    path = CACHE_DIR / "modpacks" / f["filename"]
    ctx.status(f"Downloading modpack {f['filename']}")
    download(f["url"], path, sha1=f.get("hashes", {}).get("sha1"), size=f.get("size"))
    return import_mrpack(path, ctx)


_MRPACK_LOADERS = {"fabric-loader": "fabric", "quilt-loader": "quilt", "forge": "forge", "neoforge": "neoforge"}


def import_mrpack(path: Path, ctx: Ctx) -> dict:
    """Create a new instance from a Modrinth .mrpack file."""
    with zipfile.ZipFile(path) as z:
        try:
            index = json.loads(z.read("modrinth.index.json"))
        except KeyError:
            raise RuntimeError("Not a valid .mrpack (modrinth.index.json missing)") from None
        if index.get("game") != "minecraft":
            raise RuntimeError("This pack is not for Minecraft.")
        deps = index.get("dependencies", {})
        mc = deps.get("minecraft")
        if not mc:
            raise RuntimeError("Pack does not specify a Minecraft version.")
        loader, lver = "vanilla", ""
        for key, name in _MRPACK_LOADERS.items():
            if key in deps:
                loader, lver = name, deps[key]
        if loader == "forge":
            match = [v for v in list_loader_versions("forge", mc) if v.split("-")[1:2] == [lver]]
            lver = match[0] if match else f"{mc}-{lver}"
        inst = new_instance(index.get("name", "Imported pack"), mc, loader, lver)
        gdir = game_dir(inst)
        try:
            files = [f for f in index.get("files", []) if f.get("env", {}).get("client") != "unsupported"]

            def worker(f):
                url = f["downloads"][0]
                if urlparse(url).hostname not in MRPACK_HOSTS:
                    raise RuntimeError(f"Blocked download host in modpack: {url}")
                download(url, safe_join(gdir, f["path"]), sha1=f.get("hashes", {}).get("sha1"), size=f.get("fileSize"))

            ctx.status(f"Downloading {len(files)} pack files")
            run_parallel(files, worker, ctx, "Pack files", workers=8)
            for prefix in ("overrides/", "client-overrides/"):
                for info in z.infolist():
                    if info.filename.startswith(prefix) and not info.is_dir():
                        target = safe_join(gdir, info.filename[len(prefix):])
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with z.open(info) as src, open(target, "wb") as dst:
                            shutil.copyfileobj(src, dst)
        except BaseException:
            delete_instance(inst)
            raise
    return inst


# --------------------------------------------------------------------------- #
# Launching
# --------------------------------------------------------------------------- #
def _sub(s: str, ph: dict) -> str:
    return re.sub(r"\$\{(\w+)\}", lambda m: str(ph.get(m.group(1), m.group(0))), s)


def expand_args(items: list, ph: dict, features: dict) -> list[str]:
    out: list[str] = []
    for it in items:
        if isinstance(it, str):
            out.append(_sub(it, ph))
        elif rules_allow(it.get("rules"), features):
            v = it["value"]
            out.extend(_sub(x, ph) for x in ([v] if isinstance(v, str) else v))
    return out


def build_command(inst: dict, cfg: dict, full: dict, java: str, classpath: list[str],
                  natives_dir: Path, game_assets: Path, log_arg: str | None) -> list[str]:
    name = cfg.get("username") or "Player"
    cp = os.pathsep.join(dict.fromkeys(classpath))
    width, height = int(inst.get("width", 854)), int(inst.get("height", 480))
    ph = {
        "auth_player_name": name, "auth_uuid": offline_uuid(name), "auth_access_token": "0",
        "auth_session": "0", "auth_xuid": "0", "clientid": "0", "user_type": "legacy",
        "user_properties": "{}", "version_name": full["id"], "version_type": full.get("type", "release"),
        "game_directory": str(game_dir(inst)), "assets_root": str(ASSETS_DIR), "game_assets": str(game_assets),
        "assets_index_name": full.get("assets") or (full.get("assetIndex") or {}).get("id", "legacy"),
        "natives_directory": str(natives_dir), "launcher_name": "PushuuuLauncher",
        "launcher_version": APP_VERSION, "classpath": cp, "classpath_separator": os.pathsep,
        "library_directory": str(LIBS_DIR), "resolution_width": width, "resolution_height": height,
    }
    features = {"has_custom_resolution": True}
    if "arguments" in full:
        jvm = expand_args(full["arguments"].get("jvm", []), ph, features)
        game = expand_args(full["arguments"].get("game", []), ph, features)
    else:  # pre-1.13 format
        jvm = [f"-Djava.library.path={natives_dir}", "-Dminecraft.launcher.brand=PushuuuLauncher",
               f"-Dminecraft.launcher.version={APP_VERSION}", "-cp", cp]
        game = [_sub(a, ph) for a in full.get("minecraftArguments", "").split()]
        if "--width" not in game:
            game += ["--width", str(width), "--height", str(height)]
    if cp not in jvm:
        jvm += ["-cp", cp]

    ram = int(inst.get("ram_mb") or 2048)
    cmd = [java, f"-Xmx{ram}M", f"-Xms{min(512, ram)}M"]
    cmd += shlex.split(inst.get("jvm_args") or "", posix=(OS_NAME != "windows"))
    if log_arg:
        cmd.append(log_arg)
    return cmd + jvm + [full["mainClass"]] + game


def spawn_game(cmd: list[str], cwd: Path) -> subprocess.Popen:
    return subprocess.Popen(cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", bufsize=1, **NO_WINDOW)


def prepare_launch(inst: dict, cfg: dict, ctx: Ctx) -> subprocess.Popen:
    """Install whatever is missing for this instance, then start the game. Returns the process."""
    name = cfg.get("username", "")
    if not re.fullmatch(r"[A-Za-z0-9_]{3,16}", name):
        raise RuntimeError("Player name must be 3-16 characters: letters, numbers or underscore.")

    ctx.status(f"Preparing {inst['name']}")
    ensure_vanilla_json(inst["mc"], ctx)
    if inst["loader"] == "vanilla":
        inst["version_id"] = inst["mc"]
    elif not inst.get("version_id") or not version_json_path(inst["version_id"]).exists():
        inst["version_id"] = install_loader(inst["loader"], inst["mc"], inst["loader_version"], ctx)
        save_instance(inst)
    ctx.check()

    full = load_version(inst["version_id"])
    gdir = game_dir(inst)
    gdir.mkdir(parents=True, exist_ok=True)
    cp, arts, natives = resolve_libs(full)
    jar = install_client_jar(full, ctx)
    ctx.check()
    install_libraries(arts, ctx)
    ctx.check()
    game_assets = install_assets(full, gdir, ctx)
    ctx.check()
    log_arg = install_logging(full)
    natives_dir = VERSIONS_DIR / inst["version_id"] / "natives"
    extract_natives(natives, natives_dir)
    java = resolve_java(inst, full, ctx)
    ctx.check()

    cmd = build_command(inst, cfg, full, java, [str(p) for p in cp] + [str(jar)], natives_dir, game_assets, log_arg)
    ctx.status("Launching Minecraft")
    ctx.log("[launcher] " + " ".join(shlex.quote(c) for c in cmd))
    return spawn_game(cmd, gdir)
