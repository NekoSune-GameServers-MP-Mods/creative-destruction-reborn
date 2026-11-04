@echo off
rem Start the patched Creative Destruction client WITHOUT launching a second local server.
cd /d "%~dp0"
if not exist "%~dp0client.exe" (
    echo Missing client.exe. Copy this launcher into your legally-owned game directory.
    pause
    exit /b 1
)
if not exist "%~dp0Documents\nonpatch_user_data.dat" (
    echo Missing endpoint config. Run the mod installer and then Patch Server - Set Endpoint.bat.
    pause
    exit /b 1
)
echo Starting game client using the patched endpoint. VPN must already be connected.
start "" "%~dp0client.exe"
