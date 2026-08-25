[CmdletBinding()]
param(
    [string]$Version = "1.0.0"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$iconPath = Join-Path $projectRoot "installer\assets\caixa-basilica.ico"
$distPath = Join-Path $projectRoot "dist"
$isccCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

Push-Location $projectRoot
try {
    & uv run python installer\create_app_icon.py $iconPath
    if ($LASTEXITCODE -ne 0) { throw "Não foi possível gerar o ícone do programa." }

    & uv run --with-requirements requirements.txt --with pyinstaller pyinstaller --noconfirm --clean --windowed --onefile --name CaixaBasilica --icon $iconPath --collect-data matplotlib --collect-binaries matplotlib --hidden-import matplotlib.backends.backend_tkagg main.py
    if ($LASTEXITCODE -ne 0) { throw "Não foi possível gerar o executável do programa." }

    if (-not $iscc) {
        throw "Inno Setup 6 não encontrado. Instale-o e execute este script novamente."
    }

    & $iscc "/DMyAppVersion=$Version" "/DMyAppSource=$distPath" installer\CaixaBasilica.iss
    if ($LASTEXITCODE -ne 0) { throw "Não foi possível gerar o instalador." }
}
finally {
    Pop-Location
}
