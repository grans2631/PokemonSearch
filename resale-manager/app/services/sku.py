from __future__ import annotations

import re


def _token(value: str) -> str:
    value = value.upper().strip()
    value = re.sub(r"[^A-Z0-9]+", "", value)
    if not value:
        raise ValueError("SKU component cannot be empty after normalization")
    return value


def normalize_card_number(card_number: str) -> str:
    # Keep the printed numerator for concise physical SKUs: 121/088 -> 121.
    numerator = card_number.split("/", 1)[0]
    return _token(numerator)


def build_single_sku(
    *,
    set_code: str,
    card_number: str,
    rarity: str,
    sequence: int,
    language: str = "EN",
    grading_company: str | None = None,
    grade: str | None = None,
) -> str:
    if sequence < 1 or sequence > 999:
        raise ValueError("sequence must be between 1 and 999")

    parts = [_token(set_code)]
    language_token = _token(language)
    if language_token != "EN":
        parts.append(language_token)

    parts.extend([normalize_card_number(card_number), _token(rarity)])

    if grading_company or grade:
        if not grading_company or not grade:
            raise ValueError("grading_company and grade must be supplied together")
        parts.append(f"{_token(grading_company)}{_token(grade)}")

    parts.append(f"{sequence:03d}")
    return "-".join(parts)


def build_bulk_sku(
    *,
    set_code: str,
    card_number: str,
    variant: str,
    batch: int,
    language: str = "EN",
) -> str:
    if batch < 1 or batch > 999:
        raise ValueError("batch must be between 1 and 999")

    parts = [_token(set_code)]
    language_token = _token(language)
    if language_token != "EN":
        parts.append(language_token)
    parts.extend([normalize_card_number(card_number), _token(variant), f"B{batch:03d}"])
    return "-".join(parts)
