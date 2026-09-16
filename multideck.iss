; MultiDeck Audio Player - InnoSetup Installer Script
; Requires Inno Setup 7.x

#define AppName "MultiDeck Audio Player"
#define AppVersion "0.8.0"
#define AppPublisher "Steffen Schultz"
#define AppExeName "MultiDeck.exe"
#define AppCliName "multideck-cli.exe"
#define SourceDir "dist\MultiDeck"

[Setup]
AppId={{A3F2B1C4-9D7E-4F8A-B2C3-D1E5F6A7B8C9}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} v{#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://m45.dev
AppSupportURL=https://github.com/schulle4u/multideck/issues
AppUpdatesURL=https://github.com/schulle4u/multideck/releases
LicenseFile={#SourceDir}\LICENSE

; 64-bit only
SetupArchitecture=x64
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
OutputBaseFilename=multideck_win64_v{#AppVersion}_Setup
Compression=lzma2/ultra64
SolidCompression=yes
LZMANumBlockThreads=4

; Visual settings
WizardStyle=modern dynamic
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
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait skipifsilent; Check: ShouldLaunchProgram

[InstallDelete]
; Remove bundled runtime files from previous versions before copying the new build.
; This prevents stale PyInstaller dependency files from accumulating in _internal.
Type: filesandordirs; Name: "{app}\_internal"

[UninstallDelete]
; Remove the log file created by the application on uninstall
Type: files; Name: "{app}\multideck.log"

[Code]
var
  OptionsPage: TWizardPage;
  DesktopIconCombo: TNewComboBox;
  StartMenuIconCombo: TNewComboBox;
  LaunchProgramCombo: TNewComboBox;
  FFmpegCombo: TNewComboBox;
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
    (FFmpegCombo <> nil) and
    (FFmpegCombo.ItemIndex = 0);
end;

function ShouldLaunchProgram: Boolean;
begin
  Result :=
    (LaunchProgramCombo = nil) or
    (LaunchProgramCombo.ItemIndex = 0);
end;

procedure AddYesNoOption(
  Page: TWizardPage;
  const Prompt: string;
  DefaultYes: Boolean;
  var Combo: TNewComboBox;
  var NextTop: Integer);
var
  PromptLabel: TNewStaticText;
begin
  { Create the combo box before its label. Windows exposes child controls in
    reverse creation order, and screen readers use that order to associate a
    static label with the following input control. }
  Combo := TNewComboBox.Create(Page);
  Combo.Parent := Page.Surface;
  Combo.Left := 0;
  Combo.Width := ScaleX(180);
  Combo.Style := csDropDownList;
  Combo.DropDownCount := 2;

  if IsGerman then
  begin
    Combo.Items.Add('Ja');
    Combo.Items.Add('Nein');
  end
  else
  begin
    Combo.Items.Add('Yes');
    Combo.Items.Add('No');
  end;

  if DefaultYes then
    Combo.ItemIndex := 0
  else
    Combo.ItemIndex := 1;

  PromptLabel := TNewStaticText.Create(Page);
  PromptLabel.Parent := Page.Surface;
  PromptLabel.Left := 0;
  PromptLabel.Top := NextTop;
  PromptLabel.Width := Page.SurfaceWidth;
  PromptLabel.AutoSize := False;
  PromptLabel.WordWrap := True;
  PromptLabel.Caption := Prompt;
  PromptLabel.AdjustHeight;
  PromptLabel.FocusControl := Combo;

  Combo.Top := PromptLabel.Top + PromptLabel.Height + ScaleY(4);
  NextTop := Combo.Top + Combo.Height + ScaleY(12);
end;

procedure ApplySelectedTasks;
begin
  if DesktopIconCombo.ItemIndex = 0 then
    WizardSelectTasks('desktopicon')
  else
    WizardSelectTasks('!desktopicon');

  if StartMenuIconCombo.ItemIndex = 0 then
    WizardSelectTasks('startmenuicon')
  else
    WizardSelectTasks('!startmenuicon');
end;

procedure InitializeWizard;
var
  PageCaption: string;
  PageDescription: string;
  NextTop: Integer;
begin
  FFmpegFound := FindOnPath('ffmpeg.exe');
  WingetFound := FindOnPath('winget.exe');

  if IsGerman then
  begin
    PageCaption := 'Zusätzliche Optionen';
    PageDescription :=
      'Wählen Sie für jede Option Ja oder Nein. ' +
      'Mit der Tabulatortaste wechseln Sie zwischen den Auswahllisten.';
  end
  else
  begin
    PageCaption := 'Additional Options';
    PageDescription :=
      'Choose Yes or No for each option. ' +
      'Use the Tab key to move between the selection lists.';
  end;

  OptionsPage := CreateCustomPage(wpSelectTasks, PageCaption, PageDescription);
  NextTop := 0;

  if IsGerman then
  begin
    AddYesNoOption(
      OptionsPage, 'Desktop-Symbol erstellen:',
      WizardIsTaskSelected('desktopicon'), DesktopIconCombo, NextTop);
    AddYesNoOption(
      OptionsPage, 'Eintrag im Startmenü erstellen:',
      WizardIsTaskSelected('startmenuicon'), StartMenuIconCombo, NextTop);
    AddYesNoOption(
      OptionsPage, 'MultiDeck nach der Installation starten:',
      True, LaunchProgramCombo, NextTop);
  end
  else
  begin
    AddYesNoOption(
      OptionsPage, 'Create a desktop icon:',
      WizardIsTaskSelected('desktopicon'), DesktopIconCombo, NextTop);
    AddYesNoOption(
      OptionsPage, 'Create a Start Menu entry:',
      WizardIsTaskSelected('startmenuicon'), StartMenuIconCombo, NextTop);
    AddYesNoOption(
      OptionsPage, 'Launch MultiDeck after installation:',
      True, LaunchProgramCombo, NextTop);
  end;

  if (not FFmpegFound) and WingetFound then
  begin
    if IsGerman then
      AddYesNoOption(
        OptionsPage,
        'FFmpeg wurde nicht gefunden. FFmpeg über winget installieren:',
        False, FFmpegCombo, NextTop)
    else
      AddYesNoOption(
        OptionsPage,
        'FFmpeg was not found. Install FFmpeg via winget:',
        False, FFmpegCombo, NextTop);
  end;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  { The standard task page uses check boxes. Its selections are exposed on
    OptionsPage as accessible Yes/No combo boxes instead. }
  Result := PageID = wpSelectTasks;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;

  if (OptionsPage <> nil) and (CurPageID = OptionsPage.ID) then
    ApplySelectedTasks;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if (CurPageID = wpReady) and (not FFmpegFound) and (not WingetFound) then
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
