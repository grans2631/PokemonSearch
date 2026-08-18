function Find-PokemonCard {
    [CmdletBinding()]
    param(
        [Parameter(Position=0)][string]$Name,[string]$SetName,[string]$SetId,[string]$Number,[string]$Rarity,
        [ValidateRange(1,250)][int]$PageSize = 50,[switch]$BypassCache
    )
    if (-not ($Name -or $SetName -or $SetId -or $Number -or $Rarity)) { throw 'Provide at least one search field: Name, SetName, SetId, Number, or Rarity.' }

    $q = New-PokemonTcgSearchQuery -Name $Name -SetName $SetName -SetId $SetId -Number $Number -Rarity $Rarity
    try {
        $response = Invoke-PokemonTcgRequest -Endpoint 'cards' -Query @{ q=$q; pageSize=$PageSize } -BypassCache:$BypassCache
    }
    catch {
        if (-not $Name -or $Name -notmatch '\s') { throw }

        $nameClauses = @()
        foreach ($token in ($Name -split '\s+')) {
            if ($token) {
                $safeToken = $token.Replace('"','\"')
                $nameClauses += ('name:{0}' -f $safeToken)
            }
        }

        $otherClauses = New-PokemonTcgSearchQuery -SetName $SetName -SetId $SetId -Number $Number -Rarity $Rarity
        $fallbackQuery = ((@($nameClauses) + @($otherClauses)) | Where-Object { $_ }) -join ' '
        Write-Verbose "Primary Pokemon TCG query failed; retrying with tokenized name query: $fallbackQuery"
        $response = Invoke-PokemonTcgRequest -Endpoint 'cards' -Query @{ q=$fallbackQuery; pageSize=$PageSize } -BypassCache:$BypassCache
    }

    $cards = @($response.data | ForEach-Object { ConvertFrom-PokemonTcgCard -Card $_ })
    if ($Name) {
        $cards = @($cards | Where-Object { $_.Name -ieq $Name -or $_.Name -like "*$Name*" })
    }
    $cards
}

function Get-PokemonCard {
    [CmdletBinding(DefaultParameterSetName='Id')]
    param(
        [Parameter(Mandatory,ParameterSetName='Id',Position=0)][string]$Id,
        [Parameter(Mandatory,ParameterSetName='Search')][string]$Name,
        [Parameter(ParameterSetName='Search')][string]$SetName,[Parameter(ParameterSetName='Search')][string]$SetId,
        [Parameter(ParameterSetName='Search')][string]$Number,[switch]$BypassCache
    )
    if ($PSCmdlet.ParameterSetName -eq 'Id') {
        $response = Invoke-PokemonTcgRequest -Endpoint ("cards/$Id") -BypassCache:$BypassCache
        return ConvertFrom-PokemonTcgCard -Card $response.data
    }
    $matches = @(Find-PokemonCard -Name $Name -SetName $SetName -SetId $SetId -Number $Number -PageSize 20 -BypassCache:$BypassCache)
    if ($matches.Count -eq 0) { return $null }
    if ($matches.Count -gt 1 -and -not $Number) { Write-Warning "Multiple cards matched. Returning the first result; use Find-PokemonCard to inspect all matches or include -Number/-SetId." }
    $matches[0]
}

function Get-PokemonSet {
    [CmdletBinding()]
    param([string]$Name,[string]$Id,[ValidateRange(1,250)][int]$PageSize = 50,[switch]$BypassCache)
    if (-not ($Name -or $Id)) { throw 'Provide -Name or -Id.' }
    if ($Id) {
        $response = Invoke-PokemonTcgRequest -Endpoint ("sets/$Id") -BypassCache:$BypassCache
        return $response.data
    }
    $safe = $Name.Replace('"','\"')
    $response = Invoke-PokemonTcgRequest -Endpoint 'sets' -Query @{ q="name:`"$safe`""; pageSize=$PageSize } -BypassCache:$BypassCache
    @($response.data)
}
