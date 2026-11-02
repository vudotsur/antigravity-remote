@echo off
REM Encerra o Antigravity Remote Host no Windows
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_remote.ps1"
pause
