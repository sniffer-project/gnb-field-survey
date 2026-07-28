"""Converted output mirrors the raw tree under data/processed/."""

from __future__ import annotations

from pathlib import Path

from gnb_survey.convert import processed_destination


def test_mirrors_the_raw_tree_into_processed():
    raw_root = Path("/p/data/raw")
    processed_root = Path("/p/data/processed")
    source = raw_root / "surveys" / "20260716" / "mappro" / "dd (Decimal).csv"

    result = processed_destination(source, raw_root, processed_root)

    assert result == (
        processed_root / "surveys" / "20260716" / "mappro" / "dd (Decimal)_mymaps.csv"
    )


def test_writes_beside_the_source_when_outside_the_raw_tree():
    raw_root = Path("/p/data/raw")
    processed_root = Path("/p/data/processed")
    source = Path("/somewhere/else/export.csv")

    result = processed_destination(source, raw_root, processed_root)

    assert result == Path("/somewhere/else/export_mymaps.csv")
