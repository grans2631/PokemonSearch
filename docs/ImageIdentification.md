# Image-assisted card identification

`Identify-PokemonCard` combines multiple independent signals instead of relying on a single image guess.

1. **Local OCR (optional)** reads visible text and collector numbers such as `233/091`.
2. **eBay image search (optional)** returns visually similar active listings whose titles can contribute identification evidence.
3. **Pokemon TCG API matching** turns the extracted name/collector number into canonical card candidates.
4. Candidates are confidence-ranked and can include current TCGplayer market pricing.

## Local OCR setup

Install Python dependencies:

```powershell
python -m pip install -r .\tools\requirements.txt
```

Install the Tesseract OCR application separately. If it is not on PATH:

```powershell
Set-PokemonSearchConfig -TesseractPath 'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

Then:

```powershell
Identify-PokemonCard -ImagePath .\card.jpg -IncludePricing
```

If OCR cannot determine the card, hints can be supplied:

```powershell
Identify-PokemonCard -ImagePath .\card.jpg -NameHint 'Gardevoir ex' -NumberHint 233 -IncludePricing
```

The command returns `BestMatch`, `Candidates`, and `Evidence`; use the candidate list when confidence is low or multiple cards share the same collector number across sets.
