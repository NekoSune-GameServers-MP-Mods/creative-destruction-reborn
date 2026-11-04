@echo off
cd /d "%~dp0"
python "%~dp0reborn\tools\patch_server.py" --game-dir "%~dp0" --restore
pause
