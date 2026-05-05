; MultiDeck Audio Player - InnoSetup Installer Script
; Requires Inno Setup 6.x

#define AppName "MultiDeck Audio Player"
#define AppVersion "0.7.1"
#define AppPublisher "Steffen Schultz"
#define AppExeName "MultiDeck.exe"
#define AppCliName "multideck-cli.exe"
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
LicenseFile={#SourceDir}\LICENSE

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
WizardStyle=modern dynamic
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

; Commandline interface
Source: "{#SourceDir}\{#AppCliName}"; DestDir: "{app}"; Flags: ignoreversion

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

[Code]
var
  FFmpegPage: TInputOptionWizardPage;
  FFmpegFound: Boolean;
  WingetFound: Boolean;

function IsGerman: Boolean;
begin
  Result := ActiveLanguage = 'german';
end;

function FindOnPath(const CommandName: string): Boolean;
var
  ResultCode: Integer;
begin
  Result :=
    Exec(
      ExpandConstant('{cmd}'),
      '/C where ' + AddQuotes(CommandName),
      '',
      SW_HIDE,
      ewWaitUntilTerminated,
      ResultCode
    ) and (ResultCode = 0);
end;

function FFmpegInstallRequested: Boolean;
begin
  Result :=
    (FFmpegPage <> nil) and
    FFmpegPage.Values[0];
end;

procedure InitializeWizard;
var
  Description: string;
  SubCaption: string;
begin
  FFmpegFound := FindOnPath('ffmpeg.exe');
  WingetFound := FindOnPath('winget.exe');

  if IsGerman then
  begin
    Description :=
      'MultiDeck nutzt FFmpeg als externe Abhängigkeit. ' +
      'FFmpeg wurde im aktuellen Systempfad nicht gefunden.';
    SubCaption :=
      'Durch das Aktivieren dieser Option versucht das Setup am Ende ' +
      'der Installation FFmpeg über winget zu installieren ' +
      '(Paket: Gyan.FFmpeg).';
  end
  else
  begin
    Description :=
      'MultiDeck uses FFmpeg as an external dependency. ' +
      'FFmpeg was not found in the current system path.';
    SubCaption :=
      'If you enable this option, Setup will try to install FFmpeg ' +
      'via winget at the end of the installation ' +
      '(package: Gyan.FFmpeg).';
  end;

  FFmpegPage :=
    CreateInputOptionPage(
      wpSelectTasks,
      'FFmpeg',
      Description,
      SubCaption,
      False,
      False
    );

  if IsGerman then
    FFmpegPage.Add('FFmpeg über winget installieren')
  else
    FFmpegPage.Add('Install FFmpeg via winget');
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;

  if (FFmpegPage <> nil) and (PageID = FFmpegPage.ID) then
    Result := FFmpegFound or (not WingetFound);
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if (FFmpegPage <> nil) and (CurPageID = wpReady) and (not FFmpegFound) and (not WingetFound) then
  begin
    if IsGerman then
      SuppressibleMsgBox(
        'FFmpeg wurde nicht im Systempfad gefunden, aber winget ist auf diesem System nicht verfügbar. ' +
        'FFmpeg kann deshalb nicht automatisch installiert werden.',
        mbInformation,
        MB_OK,
        IDOK
      )
    else
      SuppressibleMsgBox(
        'FFmpeg was not found in the system path, but winget is not available on this system. ' +
        'Setup cannot install FFmpeg automatically.',
        mbInformation,
        MB_OK,
        IDOK
      );
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  InstallArgs: string;
begin
  if (CurStep <> ssPostInstall) or (not FFmpegInstallRequested) then
    exit;

  InstallArgs :=
    '/C winget install --id Gyan.FFmpeg --exact --accept-package-agreements ' +
    '--accept-source-agreements';

  if not Exec(ExpandConstant('{cmd}'), InstallArgs, '', SW_SHOW, ewWaitUntilTerminated, ResultCode) then
  begin
    if IsGerman then
      SuppressibleMsgBox(
        'Der Aufruf von winget zum Installieren von FFmpeg konnte nicht gestartet werden.',
        mbError,
        MB_OK,
        IDOK
      )
    else
      SuppressibleMsgBox(
        'Setup could not start winget to install FFmpeg.',
        mbError,
        MB_OK,
        IDOK
      );
    exit;
  end;

  if ResultCode <> 0 then
  begin
    if IsGerman then
      SuppressibleMsgBox(
        'Die Installation von FFmpeg über winget wurde nicht erfolgreich abgeschlossen. ' +
        'Bitte prüfe die Konsolenausgabe oder führe "winget install Gyan.FFmpeg" später manuell aus.',
        mbError,
        MB_OK,
        IDOK
      )
    else
      SuppressibleMsgBox(
        'The winget installation of FFmpeg did not complete successfully. ' +
        'Please check the console output or run "winget install Gyan.FFmpeg" manually later.',
        mbError,
        MB_OK,
        IDOK
      );
  end
  else if IsGerman then
    SuppressibleMsgBox(
      'FFmpeg wurde über winget installiert. Je nach System kann eine neue Sitzung oder ein Neustart erforderlich sein, ' +
      'bevor der Befehl "ffmpeg" im Pfad verfügbar ist.',
      mbInformation,
      MB_OK,
      IDOK
    )
  else
    SuppressibleMsgBox(
      'FFmpeg was installed via winget. Depending on the system, a new session or restart may be required ' +
      'before the "ffmpeg" command is available in PATH.',
      mbInformation,
      MB_OK,
      IDOK
    );
end;
