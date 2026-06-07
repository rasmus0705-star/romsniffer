@echo off
title RomSniffer - Opdaterer rom-priser
echo ================================
echo   RomSniffer - Opdaterer data
echo ================================
echo.

cd /d C:\Kodning\Rom-sniffer
call .venv\Scripts\activate

echo [1/2] Korer scraper og bygger rom_data.json...
python build_rom_data.py
if errorlevel 1 (
    echo.
    echo FEJL: Scraper fejlede!
    pause
    exit /b 1
)

echo.
echo [2/2] Pusher til GitHub...
git add rom_data.json
git commit -m "Daglig rom-data opdatering %date% %time:~0,5%"
git push

echo.
echo ================================
echo   Faerdig! Siden opdateres om 1-2 min
echo ================================
timeout /t 5