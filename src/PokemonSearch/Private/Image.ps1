function Invoke-LocalPokemonOcrInternal {
    param([Parameter(Mandatory)][string]$ImagePath)

    $settings = Get-PokemonSearchSettings
    $scriptPath = Join-Path (Split-Path $script:PokemonSearchModuleRoot -Parent | Split-Path -Parent) 'tools/identify_card.py'
    if (-not (Test-Path $scriptPath)) { return $null }

    $args = @($scriptPath, '--image', (Resolve-Path $ImagePath), '--json')
    if ($settings.TesseractPath) { $args += @('--tesseract', $settings.TesseractPath) }

    try {
        $output = & $settings.PythonPath @args 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $output) { return $null }
        $output | ConvertFrom-Json
    }
    catch { $null }
}

function Get-PokemonSearchTermsFromText {
    param([string]$Text)
    if (-not $Text) { return [pscustomobject]@{ Number=$null; NameHint=$null } }

    $number = $null
    if ($Text -match '(?im)\b(\d{1,3})\s*/\s*(\d{1,3})\b') { $number = $Matches[1] }

    $lines = $Text -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    $nameHint = $lines | Where-Object {
        $_ -match '^[A-Za-z][A-Za-z .''-]{2,30}(?:\s(?:ex|EX|V|VMAX|VSTAR|GX))?$' -and
        $_ -notmatch '^(Basic|Stage|Trainer|Energy|HP|Weakness|Resistance|Retreat)$'
    } | Select-Object -First 1

    [pscustomobject]@{ Number=$number; NameHint=$nameHint }
}
