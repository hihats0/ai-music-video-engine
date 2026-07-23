$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ComfyRoot = $PSScriptRoot
$Runtime = Join-Path $ComfyRoot "runtime"
$Link = Join-Path $ComfyRoot "ComfyUI"
$RuntimeMain = Join-Path $Runtime "main.py"
$RuntimePackage = Join-Path $Runtime "comfy\options.py"
$LinkMain = Join-Path $Link "main.py"
$LinkPackage = Join-Path $Link "comfy\options.py"

if (-not (Test-Path -LiteralPath $RuntimeMain)) {
    throw "ComfyUI runtime main.py bulunamadi: $RuntimeMain"
}
if (-not (Test-Path -LiteralPath $RuntimePackage)) {
    throw "ComfyUI runtime comfy/options.py bulunamadi: $RuntimePackage"
}

if ((Test-Path -LiteralPath $LinkMain) -and (Test-Path -LiteralPath $LinkPackage)) {
    Write-Host "[OK] ComfyUI portable klasor baglantisi hazir."
    exit 0
}

$item = Get-Item -LiteralPath $Link -Force -ErrorAction SilentlyContinue
if ($null -ne $item) {
    $isReparsePoint = ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0
    if (-not $isReparsePoint) {
        throw "comfyui\ComfyUI normal bir klasor ve gecersiz. Guvenlik icin otomatik silinmedi: $Link"
    }
    & cmd.exe /d /c "rmdir `"$Link`""
    if ($LASTEXITCODE -ne 0) {
        throw "Eski veya kirik ComfyUI junction kaldirilamadi. Kod: $LASTEXITCODE"
    }
}

& cmd.exe /d /c "mklink /J `"$Link`" `"$Runtime`""
if ($LASTEXITCODE -ne 0) {
    throw "ComfyUI junction olusturulamadi. Kod: $LASTEXITCODE"
}

if (-not (Test-Path -LiteralPath $LinkMain) -or -not (Test-Path -LiteralPath $LinkPackage)) {
    throw "ComfyUI junction olustu ancak portable kaynak dosyalari gorunmuyor."
}

Write-Host "[OK] ComfyUI portable baglantisi yeniden kuruldu: ComfyUI -> runtime"
exit 0
