@echo off
rem ============================================
rem  One-click video maker
rem  Double-click this file to make videos.
rem ============================================
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\make_videos.ps1"
echo.
pause
