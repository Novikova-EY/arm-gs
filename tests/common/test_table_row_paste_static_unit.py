# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_base_html_loads_table_row_paste() -> None:
    text = (ROOT / "app" / "templates" / "base.html").read_text(encoding="utf-8")
    assert "js/common/table_row_paste.js" in text


def test_table_row_paste_script_installs_document_handler() -> None:
    text = (ROOT / "app" / "static" / "js" / "common" / "table_row_paste.js").read_text(
        encoding="utf-8"
    )
    assert 'addEventListener("paste"' in text
    assert "initPowerDemandSummaryRowPaste" in text
    assert "initProspectivePlaceForecastRowPaste" in text
    assert "__armGsTableRowPasteActive" in text
