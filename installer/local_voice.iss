; Inno Setup script for Local Voice.
; Builds a per-user installer (no admin rights required) that copies the
; app, then runs setup_env.ps1 to create a dedicated Python venv and
; install dependencies (see installer/setup_env.ps1 for why: CUDA/native
; extensions inside a frozen PyInstaller bundle are fragile with this exact
; dependency stack, so this reuses the plain-venv approach already proven
; to work rather than a riskier from-scratch repackaging).
;
; Build with: ISCC installer\local_voice.iss  (from the repo root)

#define MyAppName "Local Voice"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "rosemontni"
#define MyAppURL "https://github.com/rosemontni/localvoice"

[Setup]
AppId={{B4B2A6C1-6B9E-4C7A-9B0E-6A6E6C8E9F21}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={localappdata}\Programs\LocalVoice
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=LocalVoice-Setup-{#MyAppVersion}
SetupIconFile=..\assets\icon.ico
Compression=lzma2
SolidCompression=yes
LicenseFile=..\LICENSE
WizardStyle=modern
ArchitecturesAllowed=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "..\src\*"; DestDir: "{app}\src"; Excludes: "__pycache__,*.pyc"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\scripts\*"; DestDir: "{app}\scripts"; Excludes: "test_en.wav"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\assets\icon.ico"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "setup_env.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "requirements.txt"; DestDir: "{app}\installer"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\venv\Scripts\pythonw.exe"; Parameters: """{app}\scripts\run_tray.py"""; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\venv\Scripts\pythonw.exe"; Parameters: """{app}\scripts\run_tray.py"""; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon.ico"; Tasks: desktopicon
Name: "{autoprograms}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\installer\setup_env.ps1"" -InstallDir ""{app}"""; StatusMsg: "Setting up the Python environment (several minutes, ~2 GB download the first time)..."; Flags: waituntilterminated
Filename: "{app}\venv\Scripts\pythonw.exe"; Parameters: """{app}\scripts\run_tray.py"""; Description: "Launch {#MyAppName} now"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\venv"
Type: filesandordirs; Name: "{app}\python3.12"
