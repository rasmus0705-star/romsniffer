@echo off
title RomSniffer - Opdaterer rom-priser
echo ================================
echo   RomSniffer - Opdaterer data
echo ================================
echo.

cd /d C:\Kodning\Rom-sniffer
call .venv\Scripts\activate.bat

echo [1/2] Korer scraper, bygger sider og pusher til GitHub...
python build_rom_data.py %*
if errorlevel 1 (
    echo.
    echo ⚠  Forste forsog fejlede - venter 60 sek og prover igen...
    timeout /t 60 /nobreak >nul
    echo [2/2] Andet forsog...
    python build_rom_data.py %*
    if errorlevel 1 (
        echo.
        echo ================================
        echo   FEJL: Build fejlede to gange
        echo ================================
        echo.
        echo Proev manuelt med: python build_rom_data.py --force
        echo.
        pause
        exit /b 1
    )
)

echo.
echo ================================
echo   Faerdig! Siden opdateres om 1-2 min
echo ================================
timeout /t 5