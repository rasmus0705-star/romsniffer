# ============================================================
# RomSniffer — Deploy rom-sider + sitemap
# Kør fra: C:\Kodning\Rom-sniffer\
# ============================================================

$ErrorActionPreference = "Stop"
$utf8 = New-Object System.Text.UTF8Encoding($false)

Write-Host "`n=== RomSniffer: Deploy rom-sider ===" -ForegroundColor Cyan

# ── 1. Verificer vi er i rette mappe ──
if (-not (Test-Path "build_rom_data.py")) {
    Write-Host "FEJL: Kor dette script fra C:\Kodning\Rom-sniffer\" -ForegroundColor Red
    exit 1
}

# ── 2. Backup build_rom_data.py ──
Write-Host "`n[1/5] Backup af build_rom_data.py..." -ForegroundColor Yellow
Copy-Item build_rom_data.py build_rom_data.py.bak -Force
Write-Host "   -> build_rom_data.py.bak oprettet"

# ── 3. Patch build_rom_data.py — tilføj rom-sider + sitemap steps ──
Write-Host "`n[2/5] Patcher build_rom_data.py..." -ForegroundColor Yellow

$content = [System.IO.File]::ReadAllText("$PWD\build_rom_data.py", $utf8)

# 3a. Tilføj imports i toppen (efter eksisterende imports)
$oldImport = "from rom_matching import group_products"
$newImport = @"
from rom_matching import group_products
from generate_rom_pages import main as generate_rom_pages
from generate_sitemap import main as generate_sitemap
"@

if ($content -match "from generate_rom_pages") {
    Write-Host "   -> Imports allerede tilfojet, skipper"
} else {
    $content = $content.Replace($oldImport, $newImport)
    Write-Host "   -> Imports tilfojet"
}

# 3b. Tilføj generate-steps før git push (efter prishistorik-sektionen)
$oldGit = '    # ── Git push til GitHub'
$newSteps = @"
    # ── Generér statiske rom-sider ──
    generate_rom_pages()

    # ── Generér sitemap.xml ──
    generate_sitemap()

    # ── Git push til GitHub
"@

if ($content -match "Generér statiske rom-sider") {
    Write-Host "   -> Generate-steps allerede tilfojet, skipper"
} else {
    $content = $content.Replace($oldGit, $newSteps)
    Write-Host "   -> Generate-steps tilfojet for git push"
}

# 3c. Udvid git add til at inkludere rom/ og sitemap.xml
$oldGitAdd = 'subprocess.run(["git", "add", "rom_data.json", "price_history.json"], check=True)'
$newGitAdd = 'subprocess.run(["git", "add", "rom_data.json", "price_history.json", "sitemap.xml", "-A", "rom/"], check=True)'

if ($content -match "sitemap\.xml") {
    Write-Host "   -> git add allerede udvidet, skipper"
} else {
    $content = $content.Replace($oldGitAdd, $newGitAdd)
    Write-Host "   -> git add udvidet med rom/ og sitemap.xml"
}

[System.IO.File]::WriteAllText("$PWD\build_rom_data.py", $content, $utf8)
Write-Host "   -> build_rom_data.py gemt" -ForegroundColor Green

# ── 4. Patch opdater_rom.bat ──
Write-Host "`n[3/5] Patcher opdater_rom.bat..." -ForegroundColor Yellow
Copy-Item opdater_rom.bat opdater_rom.bat.bak -Force

$bat = [System.IO.File]::ReadAllText("$PWD\opdater_rom.bat", $utf8)
$oldBatGit = "git add rom_data.json"
$newBatGit = "git add rom_data.json price_history.json sitemap.xml`ngit add -A rom/"

if ($bat -match "sitemap\.xml") {
    Write-Host "   -> opdater_rom.bat allerede opdateret, skipper"
} else {
    $bat = $bat.Replace($oldBatGit, $newBatGit)
    [System.IO.File]::WriteAllText("$PWD\opdater_rom.bat", $bat, $utf8)
    Write-Host "   -> opdater_rom.bat opdateret med rom/ og sitemap.xml"
}

# ── 5. Dry-run: generer sider ──
Write-Host "`n[4/5] Dry-run: Genererer rom-sider fra eksisterende rom_data.json..." -ForegroundColor Yellow
python generate_rom_pages.py
python generate_sitemap.py

# ── 6. Verifikation ──
Write-Host "`n[5/5] Verifikation..." -ForegroundColor Yellow
$romDirs = (Get-ChildItem rom -Directory -ErrorAction SilentlyContinue).Count
$sitemapExists = Test-Path sitemap.xml
Write-Host "   Rom-mapper: $romDirs" -ForegroundColor Cyan
Write-Host "   sitemap.xml: $sitemapExists" -ForegroundColor Cyan

if ($romDirs -gt 0 -and $sitemapExists) {
    # Vis eksempel
    $firstDir = (Get-ChildItem rom -Directory | Select-Object -First 1).Name
    Write-Host "`n   Eksempel: rom/$firstDir/index.html" -ForegroundColor Green
    Write-Host "   Live URL:  https://romsniffer.dk/rom/$firstDir/"
    
    Write-Host "`n=== SUCCES ===" -ForegroundColor Green
    Write-Host "Klar til commit. Kor:" -ForegroundColor White
    Write-Host "   git add -A rom/ sitemap.xml build_rom_data.py opdater_rom.bat slugify_rom.py generate_rom_pages.py generate_sitemap.py" -ForegroundColor Gray
    Write-Host "   git commit -m 'Tilfoej 1028 statiske rom-sider + sitemap'" -ForegroundColor Gray
    Write-Host "   git push" -ForegroundColor Gray
} else {

    Write-Host "`n   ADVARSEL: Noget gik galt — tjek output ovenfor" -ForegroundColor Red
}