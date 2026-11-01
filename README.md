# Pushuuu Launcher

A Minecraft: Java Edition launcher with a gaming-style interface, every game version, one-click mod loaders,
a built-in Modrinth store, and a little arcade (Snake and Pong) for when downloads take a while.

## Download

| Your system | Download | Install |
|---|---|---|
| **Windows** | `PushuuuLauncher-Setup-x.y.z.exe` | Double-click, Next, Finish. No admin rights needed. Prefer no install? Use `PushuuuLauncher-Portable.exe`. |
| **macOS** | `...-macOS-AppleSilicon.dmg` (M1 or newer) or `...-macOS-Intel.dmg` | Open the .dmg, drag the app onto *Applications*. First launch: right-click the app, choose *Open*. |
| **Linux** | `...AppImage` (works on almost every distro) | Right-click > Properties > allow executing (or `chmod +x file.AppImage`), then double-click. If nothing happens, install `libfuse2` (Ubuntu 24.04: `libfuse2t64`). |
| **Linux (Ubuntu / Debian / Mint)** | `pushuuu-launcher_x.y.z_amd64.deb` | Double-click it, or `sudo apt install ./pushuuu-launcher_*.deb`. It then appears in your app menu. |
| **Android** | see [`android/README.md`](android/README.md) | The desktop app can't run on Android - that file explains the options. |

## Features
- **Every version**: releases, snapshots, old betas and old alphas, with toggle buttons and search (includes the new year-based versions like 26.1).
- **Instances**: separate worlds, mods, memory, JVM args and window size for each one. Duplicate, rename, delete.
- **Mod loaders**: Fabric, Quilt, Forge and NeoForge installed for you.
- **Modrinth built in**: search and install mods (with required dependencies), resource packs, shaders and whole modpacks. Import `.mrpack` files, add local `.jar` mods, enable / disable / remove them.
- **No Java install needed**: downloads the same Java build Mojang ships for each version.
- **Arcade tab**: Snake and Pong with saved high scores. The progress bar stays visible in the footer while you play, and the game pauses itself when you leave the tab.
- Parallel checksum-verified downloads, offline start for installed versions, live colour-coded console, crash hint.
- Offline accounts (singleplayer, LAN, offline-mode servers). See *Known limits*.

## Run from source
Python 3.9+, then `pip install -r requirements.txt`. On Linux also `sudo apt install python3-tk`.

    python pushuuu_launcher.py            # data in your user folder
    python pushuuu_launcher.py --portable # data next to the program

## Tests
No display needed. They cover the launcher logic, both games, and the GUI logic (against a fake Tk):

    python tests/test_core.py && python tests/test_games.py && python tests/gui_smoke.py

## Project layout
| File | Purpose |
|---|---|
| `pushuuu_launcher.py` | Window, pages and dialogs |
| `pushuuu_ui.py` | Theme, fonts, DPI scaling, custom neon widgets |
| `pushuuu_arcade.py` / `pushuuu_games.py` | Arcade page / game rules |
| `pushuuu_core.py` | Versions, downloads, Java, loaders, Modrinth, launching |
| `packaging/` | Icons, Inno Setup script, `.deb` / `.AppImage` / `.dmg` builders |
| `.github/workflows/release.yml` | Builds and publishes everything |

Data lives in `%APPDATA%\PushuuuLauncher` (Windows), `~/Library/Application Support/PushuuuLauncher` (macOS) or
`~/.local/share/PushuuuLauncher` (Linux). Override with the `PUSHUUU_HOME` environment variable. Uninstalling the app
leaves your worlds untouched.

## Known limits
- **No Microsoft / Mojang login yet.** Online-mode servers reject offline accounts. Mojang requires each launcher to
  register its own Azure app and be approved before it may use their login API, so that step has to come from you.
- Old versions (1.12 and earlier) on Apple Silicon may lack native libraries for that CPU.
- Forge / NeoForge first launch runs their installer and can take a few minutes.
- Linux builds are x86_64. The macOS Intel build is an optional job and may be skipped by GitHub.
- Not affiliated with Mojang or Microsoft. Minecraft is a trademark of Mojang Studios.
