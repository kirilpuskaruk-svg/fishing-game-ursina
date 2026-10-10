; ===============================================
; Inno Setup Script for Fishing Game FPS (Low Fish)
; ===============================================

#define MyAppName "Low Fish"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Low Fish Studios"
#define MyAppURL "https://github.com/kirilpuskaruk-svg/fishing-game-ursina"
#define MyAppExeName "FishingGame.exe"
#define MySourceDir "D:\FishingGameFPS\dist\FishingGame"
#define MyIconFile "D:\FishingGameFPS\assets\game_icon.ico"
#define MyReleaseDir "D:\FishingGameFPS\release"

[Setup]
AppId={{E9A1B2C3-D4E5-F6A7-B8C9-D0E1F2A3B4C5}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={sd}\Low Fish
DefaultGroupName={#MyAppName}
DirExistsWarning=no
AlwaysShowDirOnReadyPage=yes
AllowNoIcons=yes
UsePreviousAppDir=no
PrivilegesRequired=lowest
OutputDir={#MyReleaseDir}
OutputBaseFilename=MyGame-Setup
SetupIconFile={#MyIconFile}
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
VersionInfoVersion={#MyAppVersion}
VersionInfoDescription={#MyAppName} Installer
VersionInfoCompany={#MyAppPublisher}

[Languages]
Name: "ukrainian"; MessagesFile: "compiler:Languages\Ukrainian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Створити ярлик на робочому столі"; GroupDescription: "Додаткові значки:"; Flags: checkedonce

[Files]
; Основний виконуваний файл
Source: "{#MySourceDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Всі DLL Panda3D/Ursina
Source: "{#MySourceDir}\*.dll"; DestDir: "{app}"; Flags: ignoreversion

; Конфігурація Panda3D
Source: "{#MySourceDir}\etc\*"; DestDir: "{app}\etc"; Flags: ignoreversion recursesubdirs createallsubdirs

; Внутрішній каталог PyInstaller з Python runtime
Source: "{#MySourceDir}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

; Папка з 3D-ресурсами (моделі, текстури, іконки)
Source: "{#MySourceDir}\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs

; Інформаційні файли
Source: "{#MyReleaseDir}\README_INSTALL.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#MyReleaseDir}\CHANGELOG.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Ярлик у меню «Пуск»
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Видалити {#MyAppName}"; Filename: "{uninstallexe}"
; Ярлик на робочому столі
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Запустити {#MyAppName} зараз"; Flags: nowait postinstall skipifsilent; WorkingDir: "{app}"
