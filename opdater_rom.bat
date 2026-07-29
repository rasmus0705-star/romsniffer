@echo off
title RomSniffer - Opdaterer rom-priser
echo ================================
echo   RomSniffer - Opdaterer data
echo ================================
echo.

cd /d C:\Kodning\Rom-sniffer
call .venv\Scripts\activate.bat

echo [1/1] Korer scraper, bygger sider og pusher til GitHub...
python build_rom_data.py %*
if errorlevel 1 (
    echo.
    echo FEJL: Build fejlede - se output ovenfor
    pause
    exit /b 1
)

echo.
echo ================================
echo   Faerdig! Siden opdateres om 1-2 min
echo ================================
pause
