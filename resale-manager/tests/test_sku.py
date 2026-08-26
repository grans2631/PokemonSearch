import pytest

from app.services.sku import build_bulk_sku, build_single_sku


def test_raw_single_sku():
    assert build_single_sku(set_code="POR", card_number="121/088", rarity="SIR", sequence=1) == "POR-121-SIR-001"


def test_japanese_single_sku():
    assert build_single_sku(set_code="POR", card_number="121/088", rarity="SIR", sequence=2, language="JP") == "POR-JP-121-SIR-002"


def test_graded_single_sku():
    assert build_single_sku(
        set_code="POR",
        card_number="121/088",
        rarity="SIR",
        sequence=1,
        grading_company="PSA",
        grade="10",
    ) == "POR-121-SIR-PSA10-001"


def test_bulk_sku():
    assert build_bulk_sku(set_code="POR", card_number="042/088", variant="RH", batch=1) == "POR-042-RH-B001"


def test_grader_and_grade_required_together():
    with pytest.raises(ValueError):
        build_single_sku(set_code="POR", card_number="121", rarity="SIR", sequence=1, grading_company="PSA")
