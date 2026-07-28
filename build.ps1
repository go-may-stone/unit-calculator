$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$entryPoint = Join-Path $projectRoot "unit_calculator.py"
$unitsFile = Join-Path $projectRoot "units.txt"

if (-not (Test-Path $pythonPath)) {
    throw "Virtual environment not found. Run 'py -m venv .venv' first."
}

if (-not (Test-Path $entryPoint)) {
    throw "unit_calculator.py not found. Implement the application first."
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
        throw "PyInstaller build failed."
    }

    $outputDirectory = Join-Path $projectRoot "dist\UnitCalculator"
    if (Test-Path $unitsFile) {
        Copy-Item $unitsFile (Join-Path $outputDirectory "units.txt") -Force
    }

    Write-Host "Build complete: $outputDirectory"
}
finally {
    Pop-Location
}
