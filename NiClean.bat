@echo off
setlocal
REM Double-click to run NiClean on the current folder (where the .bat is located)

cd /d "%~dp0"
python niclean.py
pause