import json, os, zipfile, io, sys
import tempfile
os.environ.setdefault('PUSHUUU_HOME', tempfile.mkdtemp())  # never touch real launcher data
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import pushuuu_core as c
c.ensure_dirs()
print("root:", c.ROOT, "| os:", c.OS_NAME, "| arch:", c.MACHINE)

# offline uuid == Java's UUID.nameUUIDFromBytes("OfflinePlayer:Notch")
u = c.offline_uuid("Notch"); print("uuid", u); assert u[14] == "3"

# rules
assert c.rules_allow(None)
assert c.rules_allow([{"action": "allow"}, {"action": "disallow", "os": {"name": "osx"}}]) == (c.OS_NAME != "osx")
assert c.rules_allow([{"action": "allow", "os": {"name": "linux"}}]) == (c.OS_NAME == "linux")
assert not c.rules_allow([{"action": "allow", "features": {"is_demo_user": True}}], {})
assert c.rules_allow([{"action": "allow", "features": {"has_custom_resolution": True}}], {"has_custom_resolution": True})

# maven + keys
assert c.maven_path("net.fabricmc:fabric-loader:0.15.7") == "net/fabricmc/fabric-loader/0.15.7/fabric-loader-0.15.7.jar"
assert c.maven_path("org.lwjgl:lwjgl:3.3.1:natives-linux") == "org/lwjgl/lwjgl/3.3.1/lwjgl-3.3.1-natives-linux.jar"
assert c.lib_key({"name": "org.lwjgl:lwjgl:3.3.1:natives-linux"}) == "org.lwjgl:lwjgl:natives-linux"

# neoforge mapping
m = c.neoforge_matcher("1.21.1"); assert m("21.1.50") and not m("21.0.5") and not m("21.11.1")
m = c.neoforge_matcher("1.21");   assert m("21.0.167") and not m("21.1.5")
m = c.neoforge_matcher("26.1");   assert m("26.1.0.10-beta") and not m("26.1.1.3")
m = c.neoforge_matcher("26.1.2"); assert m("26.1.2.76") and not m("26.1.0.1-beta")
m = c.neoforge_matcher("26.1-snapshot-1"); assert m("26.1.0.0-alpha.2+snapshot-1") and not m("26.1.0.0-alpha.2+snapshot-2")

# synthetic vanilla (modern format) + fabric-style child
vanilla = {"id": "1.20.1", "type": "release", "mainClass": "net.minecraft.client.main.Main", "assets": "5",
  "assetIndex": {"id": "5", "url": "x"}, "downloads": {"client": {"url": "u", "sha1": "s", "size": 1}},
  "javaVersion": {"component": "java-runtime-gamma", "majorVersion": 17},
  "libraries": [
    {"name": "com.mojang:logging:1.1.1", "downloads": {"artifact": {"path": "com/mojang/logging/1.1.1/logging-1.1.1.jar", "url": "http://x", "sha1": "a", "size": 3}}},
    {"name": "org.ow2.asm:asm:9.0", "downloads": {"artifact": {"path": "org/ow2/asm/asm/9.0/asm-9.0.jar", "url": "http://x", "size": 3}}},
    {"name": "org.lwjgl:lwjgl:3.3.1:natives-windows", "rules": [{"action": "allow", "os": {"name": "windows"}}], "downloads": {"artifact": {"path": "w.jar", "url": "http://w", "size": 1}}},
    {"name": "org.lwjgl:lwjgl:3.3.1:natives-linux", "rules": [{"action": "allow", "os": {"name": "linux"}}], "downloads": {"artifact": {"path": "l.jar", "url": "http://l", "size": 1}}},
  ],
  "arguments": {"game": ["--username", "${auth_player_name}", "--version", "${version_name}", "--gameDir", "${game_directory}",
        {"rules": [{"action": "allow", "features": {"has_custom_resolution": True}}], "value": ["--width", "${resolution_width}", "--height", "${resolution_height}"]},
        {"rules": [{"action": "allow", "features": {"is_demo_user": True}}], "value": "--demo"}],
     "jvm": [{"rules": [{"action": "allow", "os": {"name": "osx"}}], "value": ["-XstartOnFirstThread"]},
             "-Djava.library.path=${natives_directory}", "-cp", "${classpath}"]},
  "logging": {"client": {"argument": "-Dlog4j.configurationFile=${path}", "file": {"id": "client-1.12.xml", "url": "x"}}}}
fabric = {"id": "fabric-loader-0.15.7-1.20.1", "inheritsFrom": "1.20.1", "type": "release",
  "mainClass": "net.fabricmc.loader.impl.launch.knot.KnotClient",
  "arguments": {"game": [], "jvm": ["-DFabricMcEmu= net.minecraft.client.main.Main "]},
  "libraries": [{"name": "net.fabricmc:fabric-loader:0.15.7", "url": "https://maven.fabricmc.net/"},
                {"name": "org.ow2.asm:asm:9.6", "url": "https://maven.fabricmc.net/"}]}
for vid, meta in (("1.20.1", vanilla), ("fabric-loader-0.15.7-1.20.1", fabric)):
    c.write_json(c.version_json_path(vid), meta)

full = c.load_version("fabric-loader-0.15.7-1.20.1")
names = [l["name"] for l in full["libraries"]]
print("merged libs:", names)
assert "org.ow2.asm:asm:9.6" in names and "org.ow2.asm:asm:9.0" not in names     # child wins on duplicates
assert names[0].startswith("net.fabricmc")                                       # child libs first
assert full["mainClass"].endswith("KnotClient") and full["_jar_id"] == "1.20.1" and full["id"].startswith("fabric")
assert full["javaVersion"]["majorVersion"] == 17

cp, arts, nat = c.resolve_libs(full)
print("classpath entries:", [p.name for p in cp])
fab = [a for a in arts if "fabric-loader" in a["path"]][0]
assert fab["url"] == "https://maven.fabricmc.net/net/fabricmc/fabric-loader/0.15.7/fabric-loader-0.15.7.jar"
native_jars = [p.name for p in cp if p.name in ("w.jar", "l.jar")]
assert native_jars == (["l.jar"] if c.OS_NAME == "linux" else ["w.jar"] if c.OS_NAME == "windows" else [])

inst = c.new_instance("My Fabric", "1.20.1", "fabric", "0.15.7"); inst["version_id"] = full["id"]
cmd = c.build_command(inst, {"username": "Pushuuu"}, full, "/usr/bin/java", [str(p) for p in cp] + ["/x/1.20.1.jar"],
                      Path("/n"), c.ASSETS_DIR, "-Dlog4j.configurationFile=/l.xml")
print(" ".join(cmd)[:400])
assert cmd[0] == "/usr/bin/java" and cmd[1].startswith("-Xmx")
assert cmd.index("net.fabricmc.loader.impl.launch.knot.KnotClient") > cmd.index("-cp")
assert "--demo" not in cmd and "--width" in cmd and "-XstartOnFirstThread" not in cmd
assert cmd[cmd.index("--username") + 1] == "Pushuuu"
assert "-DFabricMcEmu= net.minecraft.client.main.Main " in cmd                    # kept as ONE argv entry

# legacy (minecraftArguments) format
legacy = {"id": "1.8.9", "type": "release", "mainClass": "net.minecraft.client.main.Main", "assets": "1.8",
  "minecraftArguments": "--username ${auth_player_name} --version ${version_name} --gameDir ${game_directory} --assetsDir ${assets_root} --assetIndex ${assets_index_name} --uuid ${auth_uuid} --accessToken ${auth_access_token} --userProperties ${user_properties} --userType ${user_type}",
  "libraries": [], "_jar_id": "1.8.9"}
cmd = c.build_command(inst, {"username": "Pushuuu"}, legacy, "java", ["/a.jar"], Path("/n"), c.ASSETS_DIR, None)
assert "-Djava.library.path=/n" in cmd and "${auth_player_name}" not in " ".join(cmd) and "--width" in cmd
print("legacy ok:", cmd[-8:])

# safe_join / zip-slip
for bad in ("../evil.txt", "a/../../evil.txt", "/etc/passwd"):
    try: c.safe_join(Path(os.environ["PUSHUUU_HOME"]) / "x", bad); raise SystemExit("zip-slip not blocked: " + bad)
    except ValueError: pass

# mrpack import: overrides extracted, bad host blocked, traversal blocked
def pack(files, overrides):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("modrinth.index.json", json.dumps({"game": "minecraft", "name": "T Pack", "formatVersion": 1,
            "dependencies": {"minecraft": "1.20.1", "fabric-loader": "0.15.7"}, "files": files}))
        for k, v in overrides.items(): z.writestr(k, v)
    p = Path(os.environ["PUSHUUU_HOME"]) / "t.mrpack"; p.write_bytes(b.getvalue()); return p
ctx = c.Ctx(on_log=lambda s: None)
ok = c.import_mrpack(pack([], {"overrides/config/a.toml": "x=1", "client-overrides/options.txt": "fov:90"}), ctx)
g = c.game_dir(ok); assert (g/"config"/"a.toml").read_text() == "x=1" and (g/"options.txt").exists()
assert ok["loader"] == "fabric" and ok["loader_version"] == "0.15.7" and ok["mc"] == "1.20.1"
n_before = len(c.load_instances())
try:
    c.import_mrpack(pack([{"path": "mods/x.jar", "hashes": {}, "downloads": ["https://evil.example/x.jar"]}], {}), ctx); raise SystemExit("bad host allowed")
except RuntimeError as e: print("blocked host:", str(e)[:70])
try:
    c.import_mrpack(pack([], {"overrides/../../escape.txt": "x"}), ctx); raise SystemExit("traversal allowed")
except ValueError as e: print("blocked traversal:", e)
assert len(c.load_instances()) == n_before, "failed import must clean up its instance"

# instances / mods
dup = c.duplicate_instance(ok); assert c.game_dir(dup).joinpath("options.txt").exists()
md = c.mods_dir(ok); md.mkdir(parents=True, exist_ok=True); (md/"a.jar").write_bytes(b"x")
assert [p.name for p in c.list_mods(ok)] == ["a.jar"]
p2 = c.toggle_mod(md/"a.jar"); assert p2.name == "a.jar.disabled"; assert c.toggle_mod(p2).name == "a.jar"
c.delete_instance(dup); assert c.slugify("CON") == "CON_" and c.slugify("a b/c") == "a-b-c"
print("ALL CORE TESTS PASSED")
