$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$SshRemote = "git@github.com:hihats0/ai-music-video-engine.git"
$HttpsRemote = "https://github.com/hihats0/ai-music-video-engine.git"

function Step([string]$Text) { Write-Host "`n[ADIM] $Text" -ForegroundColor Cyan }
function Ok([string]$Text) { Write-Host "[OK] $Text" -ForegroundColor Green }
function Warn([string]$Text) { Write-Host "[UYARI] $Text" -ForegroundColor Yellow }
function Fail([string]$Text) { Write-Host "[HATA] $Text" -ForegroundColor Red }

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

function Copy-IfExists([string]$Source, [string]$Destination) {
    if (Test-Path $Source) {
        New-Item -ItemType Directory -Force -Path (Split-Path $Destination -Parent) | Out-Null
        Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force
    }
}

function Backup-Source([string]$Root, [string]$Backup) {
    New-Item -ItemType Directory -Force -Path $Backup | Out-Null
    $rootFiles = @(
        "AGENTS.md", "CLAUDE.md", "README.md", "README_FIRST.md",
        "requirements.txt", "clipctl.bat", "INSTALL_WINDOWS.bat",
        "CHECK_SYSTEM.bat", "START_ENGINE.bat", "STOP_ENGINE.bat",
        "2_ASAMA_KONTROL.bat", ".gitignore"
    )
    foreach ($name in $rootFiles) {
        Copy-IfExists (Join-Path $Root $name) (Join-Path $Backup $name)
    }
    foreach ($dir in @("clipctl", "configs", "agents", "docs", "tests", "installers", "models_manifest", "workflows")) {
        Copy-IfExists (Join-Path $Root $dir) (Join-Path $Backup $dir)
    }
    Copy-IfExists (Join-Path $Root "identities\_template") (Join-Path $Backup "identities\_template")
    Copy-IfExists (Join-Path $Root "projects\_template") (Join-Path $Backup "projects\_template")

    $comfyBackup = Join-Path $Backup "comfyui"
    New-Item -ItemType Directory -Force -Path $comfyBackup | Out-Null
    Get-ChildItem -LiteralPath (Join-Path $Root "comfyui") -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -in @(".bat", ".py", ".yaml", ".md") } |
        ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $comfyBackup -Force }
}

function Git([string]$Root, [string[]]$Arguments, [switch]$AllowFailure) {
    & git.exe -C $Root @Arguments
    $code = $LASTEXITCODE
    if (($code -ne 0) -and (-not $AllowFailure)) {
        throw "Git komutu basarisiz: git -C `"$Root`" $($Arguments -join ' ')"
    }
    return $code
}

try {
    Step "Git kontrol ediliyor"
    $git = Get-Command git.exe -ErrorAction SilentlyContinue
    if (-not $git) {
        throw "Git for Windows bulunamadi. https://git-scm.com/download/win adresinden kurup bu dosyayi tekrar calistir."
    }
    Ok "Git bulundu: $($git.Source)"

    Step "Ana motor klasoru seciliyor"
    $Root = Select-EngineRoot
    Ok "Motor klasoru: $Root"

    Step "Acik ComfyUI islemi kapatiliyor"
    $stop = Join-Path $Root "comfyui\stop_server.bat"
    if (Test-Path $stop) {
        & cmd.exe /c "`"$stop`"" | Out-Host
        Start-Sleep -Seconds 2
    }
    Ok "Surec kontrolu tamamlandi"

    Step "Yerel kaynak dosyalari yedekleniyor"
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $Backup = Join-Path $Root "recovery\github_connect_backup_$stamp"
    Backup-Source $Root $Backup
    Ok "Yedek: $Backup"

    Step "Yerel Git deposu hazirlaniyor"
    if (-not (Test-Path (Join-Path $Root ".git"))) {
        Git $Root @("init", "-b", "main") | Out-Null
        Ok "Yeni yerel Git deposu olusturuldu"
    } else {
        Ok "Mevcut .git klasoru bulundu"
    }
    Git $Root @("config", "core.longpaths", "true") | Out-Null

    $hasOrigin = (& git.exe -C $Root remote) -contains "origin"
    if ($hasOrigin) {
        $currentOrigin = (& git.exe -C $Root remote get-url origin).Trim()
        if (($currentOrigin -ne $SshRemote) -and ($currentOrigin -ne $HttpsRemote)) {
            throw "origin baska bir repoya bagli: $currentOrigin"
        }
    } else {
        Git $Root @("remote", "add", "origin", $SshRemote) | Out-Null
    }

    Step "GitHub kaynak kodu indiriliyor"
    $fetchCode = Git $Root @("fetch", "origin", "main") -AllowFailure
    if ($fetchCode -ne 0) {
        Warn "SSH baglantisi kullanilamadi. HTTPS ile tekrar deneniyor."
        Git $Root @("remote", "set-url", "origin", $HttpsRemote) | Out-Null
        Git $Root @("fetch", "origin", "main") | Out-Null
        Ok "HTTPS baglantisi kullanildi"
    } else {
        Ok "SSH baglantisi kullanildi"
    }

    Step "Kod dosyalari GitHub main dalina getiriliyor"
    Git $Root @("reset", "--hard", "origin/main") | Out-Null
    Git $Root @("branch", "--set-upstream-to=origin/main", "main") -AllowFailure | Out-Null

    Step "Yerel veriler dogrulaniyor"
    foreach ($path in @(
        (Join-Path $Root "comfyui\python_embeded\python.exe"),
        (Join-Path $Root "comfyui\runtime\main.py"),
        (Join-Path $Root "clipctl.bat"),
        (Join-Path $Root ".gitignore")
    )) {
        if (-not (Test-Path $path)) { throw "Baglanti sonrasi gerekli dosya bulunamadi: $path" }
    }
    Ok "ComfyUI runtime ve embedded Python yerinde"

    Step "Repo durumu"
    & git.exe -C $Root status --short
    & git.exe -C $Root log -1 --oneline

    Set-Content -LiteralPath (Join-Path $Root "GITHUB_CONNECTED.txt") -Encoding UTF8 -Value @(
        "Repository: hihats0/ai-music-video-engine",
        "Connected: $(Get-Date -Format o)",
        "Backup: $Backup",
        "Remote: $(& git.exe -C $Root remote get-url origin)"
    )

    Write-Host "`n============================================================" -ForegroundColor Green
    Write-Host "[OK] MEVCUT KLASOR GITHUB'A BAGLANDI" -ForegroundColor Green
    Write-Host "[OK] Repo: hihats0/ai-music-video-engine" -ForegroundColor Green
    Write-Host "[OK] ComfyUI, modeller, kimlikler ve ciktilar yerelde kaldi" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    exit 0
}
catch {
    Fail $_.Exception.Message
    Write-Host "`nYerel ComfyUI, model, kimlik ve proje dosyalarini silen bir komut calistirilmadi."
    exit 1
}
