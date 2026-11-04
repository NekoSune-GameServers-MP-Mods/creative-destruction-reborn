@echo off
cd /d "%~dp0"
set /p CDR_IP=Enter your private VPN server IPv4 (e.g. Tailscale 100.x.x.x):
python "%~dp0reborn\tools\patch_server.py" --game-dir "%~dp0" --server-ip "%CDR_IP%"
pause
