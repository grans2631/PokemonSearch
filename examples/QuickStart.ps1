Import-Module "$PSScriptRoot/../src/PokemonSearch/PokemonSearch.psd1" -Force

# Free Pokemon TCG API key is recommended but anonymous requests also work.
# Set-PokemonSearchConfig -PokemonTcgApiKey 'YOUR_KEY'

Find-PokemonCard -Name 'Mewtwo ex' | Select-Object -First 10 Name,SetName,Number,Rarity,Id

# Once you have an ID:
# Get-PokemonCardPrice -Id 'sv4-151' -Provider PokemonTCG
# Get-PokemonBidRange -Id 'sv4-151' -Shipping 4.99

# Optional provider configuration:
# Set-PokemonSearchConfig -PriceChartingToken 'TOKEN'
# Set-PokemonSearchConfig -EbayClientId 'APP_ID' -EbayClientSecret 'CERT_ID'

# Image-assisted identification:
# Identify-PokemonCard -ImagePath '.\auction-card.jpg' -IncludePricing

# Collection:
# Import-PokemonCollection -Path '.\PokemonCards.csv'
# Get-PokemonCollectionValue
