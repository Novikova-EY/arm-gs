# -*- coding: utf-8 -*-
"""При удалении варианта периметра чистятся связанные строки PD/EC."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.power_demand.services import perimeter_variant_admin_services as pvas


def test_parameter_models_cover_pd_and_ec_with_mixin() -> None:
    models = pvas._parameter_models_with_perimeter_variant_code()
    names = {m.__name__ for m in models}
    assert "RussiaFederationDemandParameter" in names
    assert "RussiaFederationEnergyConsumptionParameter" in names
    assert "EnergyAreaEnergyConsumptionParameter" in names
    assert all(hasattr(m, "perimeter_variant_code") for m in models)


def test_purge_dependent_parameter_rows_deletes_by_code(monkeypatch) -> None:
    delete_calls: list[tuple[str, list[str]]] = []

    class FakeModel:
        __name__ = "FakePdModel"
        perimeter_variant_code = SimpleNamespace(in_=lambda codes: ("in", tuple(codes)))

        class query:
            @staticmethod
            def filter(criterion):
                q = MagicMock()
                q.delete = MagicMock(
                    side_effect=lambda synchronize_session=False: (
                        delete_calls.append((FakeModel.__name__, list(criterion[1]))),
                        3,
                    )[1]
                )
                return q

    class FakeEcModel:
        __name__ = "FakeEcModel"
        perimeter_variant_code = SimpleNamespace(in_=lambda codes: ("in", tuple(codes)))

        class query:
            @staticmethod
            def filter(criterion):
                q = MagicMock()
                q.delete = MagicMock(
                    side_effect=lambda synchronize_session=False: (
                        delete_calls.append((FakeEcModel.__name__, list(criterion[1]))),
                        1,
                    )[1]
                )
                return q

    monkeypatch.setattr(
        pvas,
        "_parameter_models_with_perimeter_variant_code",
        lambda: (FakeModel, FakeEcModel),
    )

    removed = pvas._purge_dependent_parameter_rows_for_variant_codes({"with_nt", "with_gaes"})

    assert removed == 4
    assert len(delete_calls) == 2
    assert {tuple(sorted(codes)) for _, codes in delete_calls} == {
        ("with_gaes", "with_nt")
    }


def test_purge_dependent_parameter_rows_noop_for_empty_codes(monkeypatch) -> None:
    called = False

    def _boom():
        nonlocal called
        called = True
        return ()

    monkeypatch.setattr(pvas, "_parameter_models_with_perimeter_variant_code", _boom)
    assert pvas._purge_dependent_parameter_rows_for_variant_codes(set()) == 0
    assert called is False


def test_rename_dependent_parameter_rows_updates_by_code(monkeypatch) -> None:
    update_calls: list[tuple[str, str, str]] = []

    class FakePdModel:
        perimeter_variant_code = "perimeter_variant_code"

        class query:
            @staticmethod
            def filter(criterion):
                q = MagicMock()

                def _update(values, synchronize_session=False):
                    update_calls.append(
                        (
                            FakePdModel.__name__,
                            "with_nt",
                            values[FakePdModel.perimeter_variant_code],
                        )
                    )
                    return 2

                q.update = _update
                return q

    class FakeEcModel:
        perimeter_variant_code = "perimeter_variant_code"

        class query:
            @staticmethod
            def filter(criterion):
                q = MagicMock()

                def _update(values, synchronize_session=False):
                    update_calls.append(
                        (
                            FakeEcModel.__name__,
                            "with_nt",
                            values[FakeEcModel.perimeter_variant_code],
                        )
                    )
                    return 1

                q.update = _update
                return q

    monkeypatch.setattr(
        pvas,
        "_parameter_models_with_perimeter_variant_code",
        lambda: (FakePdModel, FakeEcModel),
    )

    updated = pvas._rename_dependent_parameter_rows_for_variant_code("with_nt", "with_nt_v2")

    assert updated == 3
    assert update_calls == [
        ("FakePdModel", "with_nt", "with_nt_v2"),
        ("FakeEcModel", "with_nt", "with_nt_v2"),
    ]


def test_rename_dependent_parameter_rows_noop_when_codes_equal(monkeypatch) -> None:
    called = False

    def _boom():
        nonlocal called
        called = True
        return ()

    monkeypatch.setattr(pvas, "_parameter_models_with_perimeter_variant_code", _boom)
    assert pvas._rename_dependent_parameter_rows_for_variant_code("with_nt", "with_nt") == 0
    assert pvas._rename_dependent_parameter_rows_for_variant_code("", "x") == 0
    assert called is False


def test_save_variants_from_form_renames_parameter_codes(monkeypatch) -> None:
    renamed: list[tuple[str, str]] = []

    variant = SimpleNamespace(
        id=10,
        code="with_nt",
        label_suffix="old",
        effective_from_year=None,
        effective_to_year=None,
        display_order=1,
        note=None,
        database_version_id=None,
        modified_by=None,
    )

    class _Query:
        def get(self, rid):
            return variant if rid == 10 else None

        def filter(self, *_a, **_k):
            return self

        def all(self):
            return [variant]

    session = SimpleNamespace(
        delete=lambda row: None,
        commit=lambda: None,
        rollback=lambda: None,
        add=lambda row: None,
    )
    monkeypatch.setattr(pvas, "PerimeterVariant", SimpleNamespace(query=_Query(), code="code"))
    monkeypatch.setattr(
        pvas,
        "_rename_dependent_parameter_rows_for_variant_code",
        lambda old, new: renamed.append((old, new)) or 1,
    )
    monkeypatch.setattr(pvas.db, "session", session)
    monkeypatch.setattr(pvas, "_invalidate_perimeter_variant_dependent_caches", lambda: None)
    monkeypatch.setattr(pvas, "_username", lambda: "tester")

    form = MagicMock()
    form.getlist = MagicMock(
        side_effect=lambda key: {
            "variant_id[]": ["10"],
            "variant_code[]": ["with_nt_v2"],
            "variant_label[]": ["Подпись"],
            "variant_from_year[]": [""],
            "variant_to_year[]": [""],
            "variant_display_order[]": ["1"],
            "variant_note[]": [""],
            "variant_delete[]": [],
        }.get(key, [])
    )

    saved, deleted = pvas.save_variants_from_form(form)

    assert saved == 1
    assert deleted == 0
    assert renamed == [("with_nt", "with_nt_v2")]
    assert variant.code == "with_nt_v2"
    assert variant.label_suffix == "Подпись"


def test_save_variants_from_form_purges_before_commit(monkeypatch) -> None:
    purged: list[set[str]] = []
    deleted_ids: list[int] = []

    variant = SimpleNamespace(id=10, code="with_nt")

    class _Query:
        def get(self, did):
            return variant if did == 10 else None

        def filter(self, *_a, **_k):
            return self

        def all(self):
            return [variant]

    session = SimpleNamespace(
        delete=lambda row: deleted_ids.append(row.id),
        commit=lambda: None,
        rollback=lambda: None,
    )
    monkeypatch.setattr(pvas, "PerimeterVariant", SimpleNamespace(query=_Query(), code="code"))
    monkeypatch.setattr(
        pvas,
        "_purge_dependent_parameter_rows_for_variant_codes",
        lambda codes: purged.append(set(codes)) or 2,
    )
    monkeypatch.setattr(pvas.db, "session", session)
    monkeypatch.setattr(pvas, "_invalidate_perimeter_variant_dependent_caches", lambda: None)
    monkeypatch.setattr(pvas, "_username", lambda: "tester")

    form = MagicMock()
    form.getlist = MagicMock(
        side_effect=lambda key: {
            "variant_id[]": [],
            "variant_code[]": [],
            "variant_label[]": [],
            "variant_from_year[]": [],
            "variant_to_year[]": [],
            "variant_display_order[]": [],
            "variant_note[]": [],
            "variant_delete[]": ["10"],
        }.get(key, [])
    )

    saved, deleted = pvas.save_variants_from_form(form)

    assert saved == 0
    assert deleted == 1
    assert purged == [{"with_nt"}]
    assert deleted_ids == [10]
