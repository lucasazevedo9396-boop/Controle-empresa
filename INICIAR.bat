@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 abrir_pulso.py
) else (
  python abrir_pulso.py
)
pause
