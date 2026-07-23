$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogDir = Join-Path $Root "logs\bootstrap"
$LogFile = Join-Path $LogDir "update_$Stamp.log"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Step([string]$Text) { Write-Host "`n[ADIM] $Text" -ForegroundColor Cyan }
function Good([string]$Text) { Write-Host "[OK] $Text" -ForegroundColor Green }
function Fail([string]$Text) { Write-Host "[HATA] $Text" -ForegroundColor Red }

Start-Transcript -LiteralPath $LogFile -Force | Out-Null
try {
    Set-Location $Root

    Step "Git deposu kontrol ediliyor"
    if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) {
        throw "Git for Windows bulunamadı. Git'i kurup bu dosyayı yeniden çalıştır."
    }
    if (-not (Test-Path (Join-Path $Root ".git"))) {
        throw "Bu klasör GitHub reposuna bağlı değil. GITHUBA_BAGLA_v0.2.2 paketini önce uygula."
    }
    $Branch = (& git.exe -C $Root branch --show-current).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $Branch) {
        throw "Aktif Git dalı belirlenemedi."
    }
    Good "Aktif dal: $Branch"

    Step "GitHub güncellemeleri alınıyor"
    & git.exe -C $Root status --short
    & git.exe -C $Root pull --ff-only
    if ($LASTEXITCODE -ne 0) {
        throw "git pull başarısız. Yerel değişiklik veya bağlantı sorunu olabilir."
    }
    Good "Kod güncel"

    Step "Python ortamı kontrol ediliyor"
    $Python = Join-Path $Root ".venv\Scripts\python.exe"
    if (-not (Test-Path $Python)) {
        $SystemPython = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($SystemPython) {
            & py.exe -3 -m venv (Join-Path $Root ".venv")
        } elseif (Get-Command python.exe -ErrorAction SilentlyContinue) {
            & python.exe -m venv (Join-Path $Root ".venv")
        } else {
            throw "Python bulunamadı."
        }
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $Python)) {
            throw "Python sanal ortamı oluşturulamadı."
        }
    }
    & $Python -m pip install --disable-pip-version-check --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "pip güncellenemedi." }
    & $Python -m pip install --disable-pip-version-check -r (Join-Path $Root "requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "Python bağımlılıkları kurulamadı." }
    Good "Python ortamı hazır"

    Step "Tüm üretim aşamaları kuruluyor"
    & cmd.exe /c "`"$Root\clipctl.bat`" goal install"
    if ($LASTEXITCODE -ne 0) {
        throw "GOAL kurulumu başarısız. Üstteki hata kodu ve tanı paketi yolunu kullan."
    }

    Step "Final durum kontrolü"
    & cmd.exe /c "`"$Root\clipctl.bat`" goal status"
    if ($LASTEXITCODE -ne 0) {
        throw "Final GOAL kontrolü geçmedi."
    }

    Write-Host "`n============================================================" -ForegroundColor Green
    Write-Host "[OK] TÜM AŞAMALAR GÜNCEL VE ÜRETİME HAZIR" -ForegroundColor Green
    Write-Host "[LOG] $LogFile" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    exit 0
}
catch {
    Fail $_.Exception.Message
    Write-Host "[BOOTSTRAP LOG] $LogFile" -ForegroundColor Yellow
    $Clipctl = Join-Path $Root "clipctl.bat"
    if (Test-Path $Clipctl) {
        try {
            & cmd.exe /c "`"$Clipctl`" diagnose collect"
        } catch {
            Write-Host "[UYARI] Ek tanı paketi oluşturulamadı: $($_.Exception.Message)"
        }
    }
    exit 1
}
finally {
    Stop-Transcript | Out-Null
}
