BeforeAll {
    $modulePath = Join-Path $PSScriptRoot '../src/PokemonSearch/PokemonSearch.psd1'
    Import-Module $modulePath -Force
}

Describe 'PokemonSearch module' {
    It 'exports the expected commands' {
        foreach ($name in @(
            'Find-PokemonCard','Get-PokemonCard','Get-PokemonCardPrice','Get-PokemonBidRange',
            'Get-PokemonSet','Get-PokemonSetChecklist','Get-PokemonEbayListing','Identify-PokemonCard',
            'Import-PokemonCollection','Add-PokemonCollectionCard','Get-PokemonCollectionValue',
            'Update-PokemonPriceHistory','Get-PokemonPriceHistory','Add-PokemonWatchCard','Remove-PokemonWatchCard','Get-PokemonWatchlist'
        )) {
            Get-Command $name -ErrorAction Stop | Should -Not -BeNullOrEmpty
        }
    }

    It 'exports pcard as an alias' {
        (Get-Alias pcard).Definition | Should -Be 'Find-PokemonCard'
    }

    It 'does not reveal secrets by default' {
        $config = Get-PokemonSearchConfig
        $config.PokemonTcgApiKey | Should -BeOfType [bool]
        $config.PriceChartingToken | Should -BeOfType [bool]
    }
}
