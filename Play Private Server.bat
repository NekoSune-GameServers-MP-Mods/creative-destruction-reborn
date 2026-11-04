@echo off
setlocal
title Creative Destruction Reborn - Online Client
cd /d "%~dp0"

if not exist "%~dp0client.exe" (
    echo ERROR: client.exe was not found in this folder.
    echo Install the Reborn client files next to your existing Creative Destruction client.exe.
    pause
    exit /b 1
)
if not exist "%~dp0reborn\client-config.json" (
    echo ERROR: reborn\client-config.json is missing.
    pause
    exit /b 1
)
if not exist "%~dp0Documents\nonpatch_user_data.dat" (
    echo ERROR: Reborn client modification is not installed.
    echo First run the existing Reborn installer. Your original files are backed up.
    pause
    exit /b 1
)
if exist "%~dp0RebornLauncher.exe" (
    start "" /wait "%~dp0RebornLauncher.exe"
    exit /b %errorlevel%
)
echo.
echo GUI executable is not installed. Falling back to the Python launcher.
echo Download the latest Windows GUI artifact to avoid the console.
echo.
echo Connecting to the configured Reborn server...
echo Account login is required. This launcher starts the local secure bridge and game.
echo Do NOT launch the old offline server at the same time.
echo.
where py >nul 2>&1
if %errorlevel%==0 (
    py -3 "%~dp0reborn\tools\steam_launcher.py"
) else (
    python "%~dp0reborn\tools\steam_launcher.py"
)
if errorlevel 1 (
    echo.
    echo Launch failed. Review the message above.
    pause
    exit /b 1
)
exit /b 0
