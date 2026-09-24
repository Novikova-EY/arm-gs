# -*- coding: utf-8 -*-
from decimal import Decimal
from types import SimpleNamespace

from app.fuel.services.calculation.distribution.distribution_stage_services import (
    restriction_live_payload,
)


def test_restriction_live_payload_serializes_rows_and_k():
    row = SimpleNamespace(
        id=11,
        emin=Decimal("6313"),
        emax=None,
        ecur=Decimal("6313.05"),
        h=Decimal("4100.1"),
        ecurdis=Decimal("5000"),
        hdis=Decimal("4000"),
        etp=Decimal("100"),
        kobl=Decimal("0.988"),
    )
    payload = restriction_live_payload(
        event="pass",
        outer=2,
        outer_max=14,
        k=Decimal("1.03168640124219"),
        kn=Decimal("1.0847"),
        sum_e=Decimal("61029.86"),
        e_target=Decimal("61030"),
        rows=[row],
    )
    assert payload["type"] == "pass"
    assert payload["outer"] == 2
    assert payload["rows"][0]["id"] == 11
    assert payload["rows"][0]["emax"]["text"] == "—"
    assert payload["rows"][0]["kobl"]["raw"] == "0.988"
    assert payload["totals"]["ecur"]["raw"] == "6313.05"
    assert payload["totals"]["etp"]["raw"] == "100"


def test_restriction_energy_totals_sums_all_rows():
    from app.fuel.services.calculation.distribution.distribution_stage_services import (
        restriction_energy_totals,
    )

    rows = [
        SimpleNamespace(ecur=Decimal("6313"), ecurdis=Decimal("6313"), etp=Decimal("4642")),
        SimpleNamespace(ecur=Decimal("10053"), ecurdis=Decimal("10053"), etp=Decimal("2263")),
        SimpleNamespace(ecur=Decimal("5099"), ecurdis=Decimal("5099"), etp=Decimal("328")),
        SimpleNamespace(ecur=Decimal("39565"), ecurdis=Decimal("39565"), etp=Decimal("19695")),
    ]
    totals = restriction_energy_totals(rows)
    assert totals["ecur"] == Decimal("61030")
    assert totals["ecurdis"] == Decimal("61030")
    assert totals["etp"] == Decimal("26928")
