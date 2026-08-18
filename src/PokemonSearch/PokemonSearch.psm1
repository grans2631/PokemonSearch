$ErrorActionPreference = 'Stop'

$script:PokemonSearchModuleRoot = $PSScriptRoot
$script:PokemonSearchRuntimeConfig = $null
$script:EbayAccessTokenCache = $null

Get-ChildItem -Path (Join-Path $PSScriptRoot 'Private') -Filter '*.ps1' -File | Sort-Object Name | ForEach-Object {
    . $_.FullName
}

Get-ChildItem -Path (Join-Path $PSScriptRoot 'Public') -Filter '*.ps1' -File | Sort-Object Name | ForEach-Object {
    . $_.FullName
}

Set-Alias -Name pcard -Value Find-PokemonCard -Scope Script

Export-ModuleMember -Function @(
    'Get-PokemonSearchConfig',
    'Set-PokemonSearchConfig',
    'Find-PokemonCard',
    'Get-PokemonCard',
    'Get-PokemonCardPrice',
    'Get-PokemonBidRange',
    'Get-PokemonSet',
    'Get-PokemonSetChecklist',
    'Get-PokemonEbayListing',
    'Identify-PokemonCard',
    'Import-PokemonCollection',
    'Add-PokemonCollectionCard',
    'Get-PokemonCollectionValue',
    'Update-PokemonPriceHistory',
    'Get-PokemonPriceHistory',
    'Add-PokemonWatchCard',
    'Remove-PokemonWatchCard',
    'Get-PokemonWatchlist'
) -Alias @('pcard')
