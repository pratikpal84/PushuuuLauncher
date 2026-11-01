# Android

**There is no Android version of this launcher, and a `.apk` can't be produced from this code.**
This launcher is Python/Tkinter. Android runs neither Tkinter nor a desktop Java runtime, and Minecraft: Java Edition
needs a desktop-style JVM plus an OpenGL translation layer. A launcher that merely *looked* like this on Android
couldn't start the game. That runtime is the hard part of every Android Minecraft launcher, and it is native
Android/C code.

## Your options

**1. Install a maintained Android launcher (fastest).**
The original PojavLauncher repository was archived in September 2025, and its archive notice points to maintained
successors such as **Amethyst-Android**. Search for the project on GitHub, download the APK from its *Releases*
page, and check that it supports the Minecraft version you want. Always download from the project's own page.

**2. Build your own branded APK from one of those open-source projects.**
That is how you get a `.apk` with your own name and icon:
1. Fork the project on GitHub.
2. Change the app name, package id and icons.
3. Follow the project's README to build it (these projects ship GitHub Actions that produce the APK).
4. Respect the licence. PojavLauncher is LGPL-3.0, so keep the notices and publish your changes. Check the
   licence of the exact fork you pick.

This is a real Android/NDK project, so expect it to be a bigger job than the desktop builds.

**3. Bedrock Edition** is the version that runs natively on Android. It is a different game and doesn't use Java mods.

## Honest note
Unlike the Windows / macOS / Linux builds, I haven't built or tested any Android software. If you pick a fork and
send me its GitHub link, I can help with the rebranding steps.
