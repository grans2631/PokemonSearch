#!/usr/bin/env python3
"""Optional local OCR helper for PokemonSearch.

Requires Pillow and pytesseract. The Tesseract OCR executable itself must also be
installed. This helper is intentionally optional: the PowerShell module can use
manual hints and/or eBay image search when OCR is unavailable.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract likely Pokemon-card text from an image")
    parser.add_argument("--image", required=True, help="Path to the card image")
    parser.add_argument("--tesseract", help="Optional full path to tesseract executable")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    image_path = Path(args.image)
    if not image_path.is_file():
        print(f"Image not found: {image_path}", file=sys.stderr)
        return 2

    try:
        from PIL import Image, ImageEnhance, ImageOps
        import pytesseract
    except ImportError as exc:
        print(
            "Optional OCR dependencies are missing. Run: python -m pip install -r tools/requirements.txt",
            file=sys.stderr,
        )
        return 3

    if args.tesseract:
        pytesseract.pytesseract.tesseract_cmd = args.tesseract

    with Image.open(image_path) as img:
        rgb = img.convert("RGB")
        # Upscale and increase contrast to help with small auction screenshots.
        scale = 2 if max(rgb.size) < 2400 else 1
        if scale > 1:
            rgb = rgb.resize((rgb.width * scale, rgb.height * scale))
        gray = ImageOps.grayscale(rgb)
        gray = ImageEnhance.Contrast(gray).enhance(1.6)
        text = pytesseract.image_to_string(gray, config="--psm 6")

    collector = None
    match = re.search(r"\b(\d{1,3})\s*/\s*(\d{1,3})\b", text)
    if match:
        collector = {"number": match.group(1), "printed_total": match.group(2)}

    result = {
        "text": text.strip(),
        "collector_number": collector,
        "image": str(image_path.resolve()),
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(text.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
