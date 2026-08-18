@{
    RootModule = 'PokemonSearch.psm1'
    ModuleVersion = '0.1.1'
    GUID = '5a91db0c-46aa-4bea-9b4e-fda0952af6e2'
    Author = 'Josh Gransbury'
    CompanyName = 'Community'
    Copyright = '(c) 2026. All rights reserved.'
    Description = 'PowerShell toolkit for searching, identifying, pricing, bidding on, and tracking Pokemon trading cards.'
    PowerShellVersion = '5.1'
    FunctionsToExport = @(
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
    )
    AliasesToExport = @('pcard')
    CmdletsToExport = @()
    VariablesToExport = @()
    PrivateData = @{
        PSData = @{
            Tags = @('Pokemon','TCG','Cards','Pricing','Collection','PowerShell')
            ProjectUri = 'https://github.com/grans2631/PokemonSearch'
            LicenseUri = 'https://github.com/grans2631/PokemonSearch/blob/main/LICENSE'
        }
    }
}
