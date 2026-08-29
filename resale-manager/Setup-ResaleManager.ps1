[CmdletBinding()]
param(
    [switch]$SeedDemo,
    [switch]$Start,
    [switch]$SkipUpgradePip
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host "Pokemon Resale Manager v0.6 setup"
Write-Host "Project: $ProjectRoot"

function Resolve-PythonCommand {
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        try {
            & $py.Source -3.12 -c "import sys; assert sys.version_info >= (3,12)" 2>$null
            if ($LASTEXITCODE -eq 0) {
                return @($py.Source, '-3.12')
            }
        } catch {}
    }

    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) {
        & $python.Source -c "import sys; assert sys.version_info >= (3,12)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            return @($python.Source)
        }
    }

    throw "Python 3.12+ was not found. Install Python 3.12 or newer and rerun this script."
}

$PythonCommand = @(Resolve-PythonCommand)
$PythonExe = $PythonCommand[0]
$PythonArgs = @()
if ($PythonCommand.Count -gt 1) { $PythonArgs = $PythonCommand[1..($PythonCommand.Count - 1)] }

$VenvPath = Join-Path $ProjectRoot '.venv'
$VenvPython = Join-Path $VenvPath 'Scripts\python.exe'

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating Python virtual environment..."
    & $PythonExe @PythonArgs -m venv $VenvPath
    if ($LASTEXITCODE -ne 0) { throw "Virtual environment creation failed." }
}

if (-not $SkipUpgradePip) {
    Write-Host "Updating pip..."
    & $VenvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
}

Write-Host "Installing application dependencies..."
& $VenvPython -m pip install -r (Join-Path $ProjectRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }

$EnvPath = Join-Path $ProjectRoot '.env'
$EnvExamplePath = Join-Path $ProjectRoot '.env.example'
if (-not (Test-Path $EnvPath)) {
    Copy-Item $EnvExamplePath $EnvPath
    Write-Host "Created .env from .env.example."
} else {
    Write-Host ".env already exists; leaving it unchanged."
}

$DataDir = Join-Path $ProjectRoot 'data'
if (-not (Test-Path $DataDir)) {
    New-Item -Path $DataDir -ItemType Directory | Out-Null
}

Write-Host "Applying Alembic database migrations..."
& $VenvPython -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw "Alembic migration failed." }

Write-Host "Verifying database schema..."
& $VenvPython (Join-Path $ProjectRoot 'scripts\verify_db.py')
if ($LASTEXITCODE -ne 0) { throw "Database verification failed." }

if ($SeedDemo) {
    Write-Host "Loading optional demo data..."
    & $VenvPython -m app.seed
    if ($LASTEXITCODE -ne 0) { throw "Demo seed failed." }
}

$DbPath = Join-Path $DataDir 'pokemon_resale_manager.db'
Write-Host ""
Write-Host "Setup complete."
Write-Host "Database: $DbPath"
Write-Host "Configuration: $EnvPath"
Write-Host ""
Write-Host "To start later:"
Write-Host "  .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

if ($Start) {
    Write-Host "Starting Pokemon Resale Manager at http://127.0.0.1:8000 ..."
    & $VenvPython -m uvicorn app.main:app --host 127.0.0.1 --port 8000
}
