function Identify-PokemonCard {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory,Position=0)][string]$ImagePath,
        [string]$NameHint,
        [string]$NumberHint,
        [ValidateRange(1,50)][int]$EbayImageMatches = 10,
        [switch]$SkipLocalOcr,
        [switch]$SkipEbay,
        [switch]$IncludePricing
    )

    if (-not (Test-Path $ImagePath -PathType Leaf)) { throw "Image not found: $ImagePath" }

    $evidence = [System.Collections.Generic.List[object]]::new()
    $ocr = $null
    if (-not $SkipLocalOcr) {
        $ocr = Invoke-LocalPokemonOcrInternal -ImagePath $ImagePath
        if ($ocr) {
            $parsed = Get-PokemonSearchTermsFromText -Text $ocr.text
            if (-not $NameHint -and $parsed.NameHint) { $NameHint = $parsed.NameHint }
            if (-not $NumberHint -and $parsed.Number) { $NumberHint = $parsed.Number }
            $evidence.Add([pscustomobject]@{ Source='LocalOCR'; Text=$ocr.text; NameHint=$parsed.NameHint; NumberHint=$parsed.Number })
        }
    }

    $ebayTitles = @()
    if (-not $SkipEbay) {
        try {
            $ebay = Invoke-EbayImageSearchInternal -ImagePath $ImagePath -Limit $EbayImageMatches
            $ebayTitles = @($ebay.itemSummaries | ForEach-Object title)
            if ($ebayTitles.Count) {
                $evidence.Add([pscustomobject]@{ Source='eBayImageSearch'; Titles=$ebayTitles })
                if (-not $NumberHint) {
                    foreach ($title in $ebayTitles) {
                        if ($title -match '#?([0-9]{1,3})\s*/\s*([0-9]{1,3})') { $NumberHint=$Matches[1]; break }
                        if ($title -match '#([0-9]{1,3})\b') { $NumberHint=$Matches[1]; break }
                    }
                }
            }
        }
        catch { Write-Verbose "eBay image search unavailable: $($_.Exception.Message)" }
    }

    $candidateQuery = @{}
    if ($NameHint) { $candidateQuery.Name = $NameHint }
    if ($NumberHint) { $candidateQuery.Number = $NumberHint }

    if ($candidateQuery.Count -eq 0 -and $ebayTitles.Count) {
        $commonTitle = $ebayTitles[0] -replace '(?i)Pokemon|TCG|Card|Holo|Rare|NM|Mint|PSA|CGC|BGS',' '
        $tokens = @($commonTitle -split '[^A-Za-z0-9''-]+' | Where-Object { $_.Length -gt 2 })
        if ($tokens.Count) { $candidateQuery.Name = $tokens[0] }
    }

    if ($candidateQuery.Count -eq 0) {
        return [pscustomobject]@{
            Identified=$false; NameHint=$NameHint; NumberHint=$NumberHint; Evidence=@($evidence)
            Message='No searchable name or collector number could be extracted. Install the optional OCR dependencies, configure eBay, or provide -NameHint/-NumberHint.'
            Candidates=@()
        }
    }

    $candidates = if ($candidateQuery.Name -and $candidateQuery.Number) {
        @(Find-PokemonCard -Name $candidateQuery.Name -Number $candidateQuery.Number -PageSize 50)
    } elseif ($candidateQuery.Number) {
        @(Find-PokemonCard -Number $candidateQuery.Number -PageSize 50)
    } else {
        @(Find-PokemonCard -Name $candidateQuery.Name -PageSize 50)
    }

    $scored = foreach ($card in $candidates) {
        $score = 0
        $reasons = [System.Collections.Generic.List[string]]::new()
        if ($NumberHint -and [string]$card.Number -eq [string]$NumberHint) { $score += 60; $reasons.Add('collector number') }
        if ($NameHint -and $card.Name -like "*$NameHint*") { $score += 35; $reasons.Add('name hint') }
        foreach ($title in $ebayTitles) {
            if ($title -match [regex]::Escape($card.Name)) { $score += 5; $reasons.Add('eBay title'); break }
        }
        $price = if ($IncludePricing) { Get-PokemonPreferredVariantPrice -Card $card } else { $null }
        [pscustomobject]@{
            ConfidenceScore=[math]::Min($score,100); Name=$card.Name; SetName=$card.SetName; Number=$card.Number; Rarity=$card.Rarity
            CardId=$card.Id; Image=$card.ImageLarge; Market=if($price){$price.Market}else{$null}; Variant=if($price){$price.Variant}else{$null}
            MatchReasons=($reasons -join ', ')
        }
    }
    $scored = @($scored | Sort-Object @{Expression='ConfidenceScore';Descending=$true}, SetName)

    [pscustomobject]@{
        Identified=($scored.Count -gt 0); NameHint=$NameHint; NumberHint=$NumberHint
        BestMatch=if($scored.Count){$scored[0]}else{$null}; Evidence=@($evidence); Candidates=$scored
    }
}
