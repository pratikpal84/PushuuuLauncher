; Inno Setup script for the Windows installer.
; CI builds it with:  ISCC /DAppVersion=2.0.0 packaging\installer.iss   (output: dist\PushuuuLauncher-Setup-<version>.exe)
#ifndef AppVersion
  #define AppVersion "2.0.0"
#endif

[Setup]
AppId={{FEA71520-2CEE-407C-B0C9-2771CAFB7F20}
AppName=Pushuuu Launcher
AppVersion={#AppVersion}
AppPublisher=Pushuuu
DefaultDirName={autopf}\Pushuuu Launcher
DefaultGroupName=Pushuuu Launcher
DisableProgramGroupPage=yes
; installs per-user without admin rights by default; the dialog lets people choose "all users" instead
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=PushuuuLauncher-Setup-{#AppVersion}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\PushuuuLauncher.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\PushuuuLauncher\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Pushuuu Launcher"; Filename: "{app}\PushuuuLauncher.exe"
Name: "{autodesktop}\Pushuuu Launcher"; Filename: "{app}\PushuuuLauncher.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\PushuuuLauncher.exe"; Description: "Launch Pushuuu Launcher"; Flags: nowait postinstall skipifsilent
