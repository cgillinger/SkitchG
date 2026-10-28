; Inno Setup script for SkitchG. Build from the repo root after PyInstaller:
;   iscc /DAppVersion=0.42 packaging\windows\skitchg.iss
#ifndef AppVersion
  #define AppVersion "0.0"
#endif

[Setup]
AppId={{6F1B6B0E-3C0B-4C55-9B52-5C7A1D2E4A10}
AppName=SkitchG
AppVersion={#AppVersion}
AppPublisher=SkitchG
DefaultDirName={autopf}\SkitchG
DefaultGroupName=SkitchG
UninstallDisplayIcon={app}\SkitchG.exe
SetupIconFile=..\..\build\draw.ico
OutputDir=..\..\dist-installer
OutputBaseFilename=SkitchG-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "autostart"; Description: "Start screenshot helper at login"; GroupDescription: "Screenshots:"

[Files]
Source: "..\..\dist\SkitchG\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\SkitchG"; Filename: "{app}\SkitchG.exe"
Name: "{group}\SkitchG screenshot helper"; Filename: "{app}\SkitchG.exe"; Parameters: "--tray"

[Registry]
; Screenshot helper at login (per user; HKA follows the install mode)
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "SkitchG"; ValueData: """{app}\SkitchG.exe"" --tray"; Flags: uninsdeletevalue; Tasks: autostart

; "Open with SkitchG" for common image types
Root: HKA; Subkey: "Software\Classes\Applications\SkitchG.exe"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "SkitchG"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\SkitchG.exe\shell\open\command"; ValueType: string; ValueData: """{app}\SkitchG.exe"" ""%1"""
Root: HKA; Subkey: "Software\Classes\Applications\SkitchG.exe\SupportedTypes"; ValueType: string; ValueName: ".png"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\SkitchG.exe\SupportedTypes"; ValueType: string; ValueName: ".jpg"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\SkitchG.exe\SupportedTypes"; ValueType: string; ValueName: ".jpeg"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\SkitchG.exe\SupportedTypes"; ValueType: string; ValueName: ".webp"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\SkitchG.exe\SupportedTypes"; ValueType: string; ValueName: ".bmp"; ValueData: ""

[Run]
Filename: "{app}\SkitchG.exe"; Parameters: "--tray"; Description: "Start the screenshot helper"; Flags: nowait postinstall skipifsilent
