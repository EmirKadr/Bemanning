#define MyAppName "Bemanning"
#ifndef MyAppVersion
#define MyAppVersion "0.1.2"
#endif
#define MyAppExeName "Bemanning.exe"

[Setup]
AppId={{A8D49C55-F8B4-43F7-91B5-8EF9D409CA24}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Dole Nordic AB
AppPublisherURL=https://github.com/EmirKadr/Bemanning
AppSupportURL=https://github.com/EmirKadr/Bemanning/issues
AppUpdatesURL=https://github.com/EmirKadr/Bemanning/releases
DefaultDirName={localappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\..\release
OutputBaseFilename={#MyAppName}-{#MyAppVersion}-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
CloseApplications=yes
RestartApplications=no
UninstallDisplayName={#MyAppName}

[Languages]
Name: "swedish"; MessagesFile: "compiler:Languages\Swedish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\..\release\{#MyAppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
