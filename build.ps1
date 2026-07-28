$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$entryPoint = Join-Path $projectRoot "unit_calculator.py"
$unitsFile = Join-Path $projectRoot "units.txt"

if (-not (Test-Path $pythonPath)) {
    throw "仮想環境がありません。先に 'py -m venv .venv' を実行してください。"
}

if (-not (Test-Path $entryPoint)) {
    throw "unit_calculator.py がありません。先にアプリを実装してください。"
}

Push-Location $projectRoot
try {
    & $pythonPath -m PyInstaller `
        --noconfirm `
        --clean `
        --windowed `
        --onedir `
        --name "UnitCalculator" `
        $entryPoint

    if ($LASTEXITCODE -ne 0) {
        throw "PyInstallerによるビルドに失敗しました。"
    }

    $outputDirectory = Join-Path $projectRoot "dist\UnitCalculator"
    if (Test-Path $unitsFile) {
        Copy-Item $unitsFile (Join-Path $outputDirectory "units.txt") -Force
    }

    Write-Host "作成完了: $outputDirectory"
}
finally {
    Pop-Location
}
