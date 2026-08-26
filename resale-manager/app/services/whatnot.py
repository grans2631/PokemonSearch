"""Whatnot CSV integration boundary.

The chosen business workflow is Whatnot-live-first, then eBay for unsold items.
The v0.2 implementation should export selected show inventory and reconcile the
Whatnot show report CSV back into inventory/sales records.
"""

from pathlib import Path


class WhatnotCsvService:
    def export_show(self, *, show_id: int, destination: Path) -> Path:
        raise NotImplementedError("Whatnot CSV export is planned for v0.2")

    def import_show_results(self, *, show_id: int, source: Path) -> dict[str, int]:
        raise NotImplementedError("Whatnot show-result import is planned for v0.2")
