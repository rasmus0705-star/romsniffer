@echo off
setlocal
title RomSniffer - Opdaterer rom-priser
cd /d "%~dp0"
set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY if exist "venv\Scripts\python.exe" set "PY=venv\Scripts\python.exe"
if not defined PY if exist "C:\Kodning\beer-sniffer\venv\Scripts\python.exe" set "PY=C:\Kodning\beer-sniffer\venv\Scripts\python.exe"
if not defined PY if exist "C:\Kodning\beer-sniffer\.venv\Scripts\python.exe" set "PY=C:\Kodning\beer-sniffer\.venv\Scripts\python.exe"
if not defined PY (
    echo FEJL: Fandt ingen Python.
    pause
    exit /b 1
)
echo Python: %PY%
if defined ROM_NO_PUSH echo OBS: ROM_NO_PUSH er sat - pusher IKKE.
"%PY%" build_rom_data.py %*
if errorlevel 1 (
    echo Forsoeg 1 fejlede - venter 60 sek...
    timeout /t 60 /nobreak >nul
    "%PY%" build_rom_data.py %*
    if errorlevel 1 (
        echo FEJL: Build fejlede to gange
        pause
        exit /b 1
    )
)
echo Faerdig - siden opdateres om 1-2 min
timeout /t 5