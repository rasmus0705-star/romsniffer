@echo off
title RomSniffer - Fejlrettelse
cd /d C:\Kodning\Rom-sniffer
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else if exist C:\Kodning\beer-sniffer\.venv\Scripts\activate.bat (
    call C:\Kodning\beer-sniffer\.venv\Scripts\activate.bat
) else (
    call C:\Kodning\beer-sniffer\venv\Scripts\activate.bat
)
python ret_fejl.py
