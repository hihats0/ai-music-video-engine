$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step([string]$Text) { Write-Host "`n[ADIM] $Text" -ForegroundColor Cyan }
function Write-Ok([string]$Text) { Write-Host "[OK] $Text" -ForegroundColor Green }
function Write-Warn([string]$Text) { Write-Host "[UYARI] $Text" -ForegroundColor Yellow }
function Write-Fail([string]$Text) { Write-Host "[HATA] $Text" -ForegroundColor Red }

function Select-EngineRoot {
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = "AI_MUSIC_VIDEO_ENGINE ana klasorunu sec. Icerisinde clipctl.bat bulunmali."
    $dialog.ShowNewFolderButton = $false
    if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
        throw "Klasor secimi iptal edildi."
    }
    $root = $dialog.SelectedPath
    if (-not (Test-Path (Join-Path $root "clipctl.bat"))) {
        throw "Yanlis klasor secildi. Secilen klasorde clipctl.bat bulunamadi: $root"
    }
    return (Resolve-Path $root).Path
}

function Stop-Comfy([string]$Root) {
    $stopBat = Join-Path $Root "comfyui\stop_server.bat"
    if (Test-Path $stopBat) {
        & cmd.exe /c "`"$stopBat`"" | Out-Host
        Start-Sleep -Seconds 3
    }
}

function Ensure-Junction([string]$Root) {
    $link = Join-Path $Root "comfyui\ComfyUI"
    $target = Join-Path $Root "comfyui\runtime"

    if (-not (Test-Path (Join-Path $target "main.py"))) {
        throw "runtime\main.py bulunamadi: $target"
    }
    if (-not (Test-Path (Join-Path $target "comfy\options.py"))) {
        throw "runtime\comfy\options.py bulunamadi. v0.2.1 onarimi eksik kalmis olabilir."
    }

    if (Test-Path $link) {
        $item = Get-Item -LiteralPath $link -Force
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            Remove-Item -LiteralPath $link -Force
        } else {
            $backupName = "ComfyUI_existing_" + (Get-Date -Format "yyyyMMdd_HHmmss")
            Rename-Item -LiteralPath $link -NewName $backupName
            Write-Warn "Mevcut normal ComfyUI klasoru $backupName olarak saklandi."
        }
    }

    & cmd.exe /c "mklink /J `"$link`" `"$target`""
    if ($LASTEXITCODE -ne 0) {
        throw "ComfyUI junction olusturulamadi."
    }

    if (-not (Test-Path (Join-Path $link "comfy\options.py"))) {
        throw "Junction olustu ancak comfy\options.py gorunmuyor."
    }
}

function Copy-Patch([string]$Root, [string]$PackageRoot) {
    $patch = Join-Path $PackageRoot "patch"
    Copy-Item -LiteralPath (Join-Path $patch "comfyui\run_server.bat") -Destination (Join-Path $Root "comfyui\run_server.bat") -Force
    Copy-Item -LiteralPath (Join-Path $patch "comfyui\start_headless.bat") -Destination (Join-Path $Root "comfyui\start_headless.bat") -Force
    Copy-Item -LiteralPath (Join-Path $patch "comfyui\start_interface.bat") -Destination (Join-Path $Root "comfyui\start_interface.bat") -Force
    Copy-Item -LiteralPath (Join-Path $patch "comfyui\stop_server.py") -Destination (Join-Path $Root "comfyui\stop_server.py") -Force
    Copy-Item -LiteralPath (Join-Path $patch "comfyui\wait_for_server.py") -Destination (Join-Path $Root "comfyui\wait_for_server.py") -Force
    Copy-Item -LiteralPath (Join-Path $patch "tests\test_stage2.py") -Destination (Join-Path $Root "tests\test_stage2.py") -Force
    Copy-Item -LiteralPath (Join-Path $patch "2_ASAMA_KONTROL.bat") -Destination (Join-Path $Root "2_ASAMA_KONTROL.bat") -Force
}

function Test-Api([int]$TimeoutSeconds) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8188/system_stats" -TimeoutSec 5
            if ($response.StatusCode -eq 200) { return $true }
        } catch {
            Start-Sleep -Seconds 5
        }
        Write-Host "[BILGI] ComfyUI aciliyor..."
    }
    return $false
}

try {
    $PackageRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

    Write-Step "Ana motor klasoru seciliyor"
    $Root = Select-EngineRoot
    Write-Ok "Motor klasoru: $Root"

    Write-Step "Mevcut ComfyUI sureci kapatiliyor"
    Stop-Comfy $Root
    Write-Ok "Surec kontrolu tamamlandi"

    Write-Step "Degistirilecek dosyalar yedekleniyor"
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backup = Join-Path $Root "recovery\stage2_2_backup_$stamp"
    New-Item -ItemType Directory -Force -Path (Join-Path $backup "comfyui") | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $backup "tests") | Out-Null

    $backupFiles = @(
        "comfyui\run_server.bat",
        "comfyui\start_headless.bat",
        "comfyui\start_interface.bat",
        "comfyui\stop_server.py",
        "comfyui\wait_for_server.py",
        "tests\test_stage2.py",
        "2_ASAMA_KONTROL.bat"
    )
    foreach ($relative in $backupFiles) {
        $source = Join-Path $Root $relative
        if (Test-Path $source) {
            $destination = Join-Path $backup $relative
            New-Item -ItemType Directory -Force -Path (Split-Path $destination -Parent) | Out-Null
            Copy-Item -LiteralPath $source -Destination $destination -Force
        }
    }
    Write-Ok "Yedek: $backup"

    Write-Step "Portable ComfyUI klasor baglantisi duzeltiliyor"
    Ensure-Junction $Root
    Write-Ok "comfyui\ComfyUI -> comfyui\runtime"

    Write-Step "v0.2.2 baslatma ve kontrol dosyalari uygulaniyor"
    Copy-Patch $Root $PackageRoot
    Write-Ok "Dosyalar uygulandi"

    Write-Step "Dosya yapisi testi"
    $venvPython = Join-Path $Root ".venv\Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        throw "1. ASAMA Python ortami bulunamadi: $venvPython"
    }
    & $venvPython (Join-Path $Root "tests\test_stage2.py")
    if ($LASTEXITCODE -ne 0) {
        throw "v0.2.2 dosya testi basarisiz."
    }

    Write-Step "ComfyUI kalici baslatma testi"
    & cmd.exe /c "`"$Root\comfyui\start_headless.bat`""
    if ($LASTEXITCODE -ne 0) {
        throw "start_headless.bat basarisiz."
    }

    if (-not (Test-Api 600)) {
        $log = Join-Path $Root "logs\comfyui\server.log"
        if (Test-Path $log) {
            Write-Host "`n===== server.log son 80 satir =====" -ForegroundColor Yellow
            Get-Content -LiteralPath $log -Tail 80
            Write-Host "===== log sonu =====`n" -ForegroundColor Yellow
        }
        throw "ComfyUI API 10 dakika icinde yanit vermedi."
    }

    & $venvPython (Join-Path $Root "comfyui\healthcheck.py")
    if ($LASTEXITCODE -ne 0) {
        throw "ComfyUI API saglik kontrolu basarisiz."
    }

    Set-Content -LiteralPath (Join-Path $Root "STAGE_2_COMPLETE_v0.2.2.txt") -Encoding UTF8 -Value @(
        "2. ASAMA v0.2.2 tamamlandi",
        "Completed: $(Get-Date -Format o)",
        "Endpoint: http://127.0.0.1:8188",
        "ComfyUI link: comfyui\ComfyUI -> comfyui\runtime",
        "Backup: $backup"
    )

    Write-Host "`n============================================================" -ForegroundColor Green
    Write-Host "[OK] 2. ASAMA v0.2.2 TAMAMEN HAZIR" -ForegroundColor Green
    Write-Host "[OK] ComfyUI: http://127.0.0.1:8188" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    exit 0
}
catch {
    Write-Fail $_.Exception.Message
    Write-Host "`nProje ve model dosyalarin silinmedi."
    exit 1
}
