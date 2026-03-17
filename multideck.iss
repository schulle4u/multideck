; MultiDeck Audio Player - InnoSetup Installer Script
; Requires Inno Setup 6.x

#define AppName "MultiDeck Audio Player"
#define AppVersion "0.4.1"
#define AppPublisher "Steffen Schultz"
#define AppExeName "MultiDeck.exe"
#define SourceDir "dist\MultiDeck"

[Setup]
AppId={{A3F2B1C4-9D7E-4F8A-B2C3-D1E5F6A7B8C9}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://m45.dev
AppSupportURL=https://github.com/schulle4u/multideck/issues
AppUpdatesURL=https://github.com/schulle4u/multideck/releases

; 64-bit only
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Allow user to choose between all-users and current-user install
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Install paths depending on install mode
DefaultDirName={autopf}\MultiDeck Audio Player
DefaultGroupName={#AppName}

; Installer output
OutputDir=dist
OutputBaseFilename=multideck_win64_{#AppVersion}_Setup
Compression=lzma2/ultra64
SolidCompression=yes
LZMANumBlockThreads=4

; Visual settings
WizardStyle=modern
WizardResizable=yes
ShowLanguageDialog=auto

; Version info
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Installer
VersionInfoCopyright=MIT License

; Misc
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startmenuicon"; Description: "Eintrag im Startmenü erstellen"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Main executable
Source: "{#SourceDir}\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Runtime files
Source: "{#SourceDir}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

; Documentation
Source: "{#SourceDir}\docs\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs createallsubdirs

; Locale / translations
Source: "{#SourceDir}\locale\*"; DestDir: "{app}\locale"; Flags: ignoreversion recursesubdirs createallsubdirs

; Example config (only if not already present)
Source: "{#SourceDir}\config.ini.example"; DestDir: "{app}"; Flags: ignoreversion

; License
Source: "{#SourceDir}\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start menu shortcut (only for all-users install: Common Programs; for per-user: user Programs)
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: startmenuicon
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove the log file created by the application on uninstall
Type: files; Name: "{app}\multideck.log"
