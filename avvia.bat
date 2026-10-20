@echo off
rem PSYSUONO - avvio da sorgente in schermo intero (risoluzione nativa del monitor).
cd /d "%~dp0"
py -3 "%~dp0main.py" %*
if errorlevel 1 py "%~dp0main.py" %*
pause
