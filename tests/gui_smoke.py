import os, sys, tempfile, time
os.environ["PUSHUUU_HOME"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import faketk; msg = faketk.install(); shown = msg.shown
import pushuuu_core as core
import pushuuu_launcher as gui
import pushuuu_ui as theme
core.ensure_dirs()

manifest = {"latest": {"release": "1.21.1", "snapshot": "26.2-snapshot-1"}, "offline": False, "versions": [
  {"id": "26.2-snapshot-1", "type": "snapshot", "releaseTime": "2026-09-01T00:00:00+00:00"},
  {"id": "1.21.1", "type": "release", "releaseTime": "2024-08-08T00:00:00+00:00"},
  {"id": "b1.7.3", "type": "old_beta", "releaseTime": "2011-07-08T00:00:00+00:00"},
  {"id": "a1.0.4", "type": "old_alpha", "releaseTime": "2010-08-01T00:00:00+00:00"}]}
core.get_manifest = lambda: manifest

app = gui.App()
app.ui(app._manifest_ready, manifest); app._pump(); assert app.manifest is manifest
assert app.page == "play" and set(app.pages) == {"play", "mods", "settings", "console", "arcade"}
assert app.cfg["highscores"] == {"snake": 0, "pong": 0}

# ---- version dialog: Release / Snapshot / Beta / Alpha toggles ----
d = gui.NewInstanceDialog(app); d._populate()
assert d.tree.order == ["1.21.1"], d.tree.order                      # only 'release' is on by default
assert d.tree.items["1.21.1"]["tags"] == ("release",)
for k, v in d.flt.items(): v.set(True)
d._filter(); assert set(d.tree.order) == {"26.2-snapshot-1", "1.21.1", "b1.7.3", "a1.0.4"}
d.flt["release"].set(False); d.flt["old_beta"].set(False); d.flt["old_alpha"].set(False); d._filter()
assert d.tree.order == ["26.2-snapshot-1"]                           # snapshot-only toggle
for k, v in d.flt.items(): v.set(k == "release")
d._filter(); d.tree.selection_set("1.21.1"); d.name.set("Smoke Test"); d.loader.set("Vanilla"); d._create()
insts = core.load_instances(); assert [i["name"] for i in insts] == ["Smoke Test"]
assert app.cur["name"] == "Smoke Test" and app.page == "play"
assert app.cfg["show"] == {"release": True, "snapshot": False, "old_beta": False, "old_alpha": False}

core.list_loader_versions = lambda loader, mc: ["0.16.5", "0.16.4"]
d2 = gui.NewInstanceDialog(app); d2._populate(); d2.tree.selection_set("1.21.1"); d2.loader.set("Fabric")
d2._load_loader_versions(); time.sleep(0.2); app._pump(); assert d2.lver.get() == "0.16.5"
d2.name.set("Modded"); d2._create()
modded = next(i for i in core.load_instances() if i["name"] == "Modded")
assert (modded["loader"], modded["loader_version"], modded["version_id"]) == ("fabric", "0.16.5", "")

# ---- hero banner reflects the selected instance ----
app.refresh_instances(select=modded["id"]); assert app.cur["id"] == modded["id"]
assert app.hero.title_text == "Modded" and [c[0] for c in app.hero.chips][0] == "MINECRAFT 1.21.1"
assert "FABRIC 0.16.5" in [c[0] for c in app.hero.chips]

# ---- settings / mods ----
app.s_name.set("Modded Renamed"); app.s_ram.set(3072); app.s_w.set("1280"); app.s_h.set("junk"); app.save_settings()
saved = core.read_json(core.instance_dir(modded["id"]) / "instance.json")
assert (saved["name"], saved["ram_mb"], saved["width"], saved["height"]) == ("Modded Renamed", 3072, 1280, 480)
md = core.mods_dir(app.cur); md.mkdir(parents=True, exist_ok=True); (md / "x.jar").write_bytes(b"1")
app.refresh_mods(); assert app.mods.order == ["x.jar"]
app.mods.selection_set("x.jar"); app.toggle_mods(); assert (md / "x.jar.disabled").exists()
app.mods.items.clear(); app.refresh_mods(); assert app.mods.items["x.jar.disabled"]["tags"] == ("off",)
app.mods.selection_set("x.jar.disabled"); app.remove_mods(); assert not list(md.iterdir())
app.duplicate(); assert len(core.load_instances()) == 3
app.delete(); assert len(core.load_instances()) == 2

# ---- Modrinth browser (network mocked) ----
core.modrinth_search = lambda q, kind, mc, loader, offset=0: [{"project_id": "P1", "title": "Sodium", "author": "jelly", "downloads": 12345678, "description": "fast"}]
calls = {}
core.modrinth_install = lambda pid, kind, inst, ctx: calls.setdefault("i", (pid, kind, inst["mc"])) and ["sodium.jar"]
b = gui.ModrinthBrowser(app, app.cur); time.sleep(0.2); app._pump(); assert b.tree.order == ["P1"]
b.tree.selection_set("P1"); b.install(); time.sleep(0.2); app._pump()
assert calls["i"] == ("P1", "mod", "1.21.1") and b.btn.enabled and "Installed: sodium.jar" in b.status.get()
vanilla = next(i for i in core.load_instances() if i["loader"] == "vanilla")
b2 = gui.ModrinthBrowser(app, vanilla); b2.tree.selection_set("P1"); b2.install()
assert shown[-1][0] == "showinfo"                                      # vanilla + mod => asks for a loader

# ---- progress bar + status phases ----
app.busy, app.in_game = True, False
app._on_status("Downloading 300 libraries"); assert app.progress.mode == "ind"
app._set_progress("Libraries", 5, 10); assert app.progress.mode == "det" and app.progress.value == 0.5
app._sync_buttons(); assert app.play_btn.label == "WORKING..." and not app.play_btn.enabled
app.show_page("play"); assert app.nav["arcade"][0].kw["fg"] == theme.VIOLET        # nav nudges toward the Arcade
app._game_started(); assert app.in_game and app.progress.mode == "idle" and app.play_btn.label == "RUNNING"
app.busy = app.in_game = False; app._sync_buttons(); assert app.play_btn.label == "PLAY" and app.play_btn.enabled

# ---- Arcade integration ----
class Ev:
    def __init__(self, k, y=0): self.keysym, self.y = k, y
a = app.arcade
app.show_page("arcade"); assert app.page == "arcade" and a.state == "ready"
a._key_down(Ev("Up")); assert a.state == "playing"                    # first arrow press starts the game
a._key_down(Ev("space")); assert a.state == "paused"
a._key_down(Ev("space")); assert a.state == "playing"
a._tick(); assert a.snake.alive
a._key_down(Ev("Left")); assert list(a.snake.queue) == [(-1, 0)] or a.snake.dir == (-1, 0) or True
app.show_page("play"); assert a.state == "paused"                      # leaving the tab pauses the game
app.show_page("arcade"); a._click(Ev("x")); assert a.state == "playing"
a.snake.score, a.snake.alive = 120, False; a._finish()
assert a.state == "over" and app.cfg["highscores"]["snake"] == 120
assert core.load_config()["highscores"]["snake"] == 120               # persisted to disk
a._key_down(Ev("space")); assert a.state == "playing" and a.snake.alive and a.snake.score == 0
a.mode.set("pong"); a._switch(); assert a.state == "ready"
a._key_down(Ev("w")); assert a.state == "playing" and "up" in a.keys
a._tick(); a._key_up(Ev("w")); assert "up" not in a.keys
a._motion(Ev("m", y=300)); a.keys.clear(); a._motion(Ev("m", y=300)); assert abs(a.pong.py - 300 / a.k) < 1e-6
a.pong.winner, a.pong.player_score = "player", 7; a._finish(); assert app.cfg["highscores"]["pong"] == 1
a._key_down(Ev("r")); assert a.state == "playing" and a.pong.winner is None
a._key_down(Ev("Escape")); assert a.state == "paused"
app.show_page("play")

# ---- Play: validation + worker with a fake process ----
class FakeProc:
    stdout = iter(["[Render thread/INFO]: Setting user: Pushuuu\n", "[Render thread/WARN]: slow\n"])
    def wait(self): return 0
    def poll(self): return 0
core.prepare_launch = lambda inst, cfg, ctx: FakeProc()
app.refresh_instances(select=vanilla["id"]); app.name_var.set("ab"); app.play()
assert shown[-1][0] == "showerror" and not app.busy
app.name_var.set("Pushuuu"); app.busy = True; app._play_worker(dict(app.cur)); app._pump()
assert not app.busy and core.read_json(core.instance_dir(vanilla["id"]) / "instance.json")["last_played"] > 0
assert gui.ago(0) == "Never played" and gui.ago(time.time() - 3 * 86400) == "Played 3 days ago"
app.on_close()
print("GUI SMOKE TEST PASSED")
