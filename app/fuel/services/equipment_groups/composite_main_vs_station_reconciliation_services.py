# -*- coding: utf-8 -*-
"""
Сверка кластеров составности (comp/main) с бакетами по Generation Station.

Нужна перед окончательным отказом от суррогата grouping_station:
показывает, где дети с одним MAIN сидят на разных Station и наоборот.

Создание родителей (режим C / phase A):
только для MAIN, на которые уже ссылаются дети в АРМ; по каждой
database_version_id; атрибуты из Excel «Имена_станций», привязка к Station
от детей той же версии.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
from app.fuel.services.equipment_groups.composite_station_semantics import (
    _as_int,
    is_composite_child_group,
    is_composite_parent_group,
    is_main_empty,
)


@dataclass
class CompositeVsStationReport:
    parents_with_children: int = 0
    children_total: int = 0
    orphan_children_no_parent: int = 0
    clusters_split_across_stations: list[dict] = field(default_factory=list)
    stations_with_multi_eg_no_main: list[dict] = field(default_factory=list)
    missing_parent_shells: list[dict] = field(default_factory=list)
    message: str = ""

    def to_flash_lines(self) -> list[str]:
        lines = [
            "Сверка составности (comp/main) vs Station:",
            (
                f"Родителей с детьми: {self.parents_with_children}, "
                f"детей: {self.children_total}, "
                f"сирот (MAIN без родителя в БД): {self.orphan_children_no_parent}."
            ),
            (
                f"Кластеров MAIN, разъехавшихся по разным Station: "
                f"{len(self.clusters_split_across_stations)}; "
                f"Station с ≥2 EG без MAIN: {len(self.stations_with_multi_eg_no_main)}; "
                f"отсутствующих оболочек родителей: {len(self.missing_parent_shells)}."
            ),
        ]
        for row in self.clusters_split_across_stations[:8]:
            lines.append(
                f"  MAIN={row['main']}: station_ids={row['station_ids']} "
                f"eg_ids={row['eg_ids']}"
            )
        for row in self.stations_with_multi_eg_no_main[:8]:
            lines.append(
                f"  Station id={row['station_id']}: eg_ids={row['eg_ids']} "
                f"(нет comp/main — бывший суррогат группировки)"
            )
        for row in self.missing_parent_shells[:8]:
            lines.append(
                f"  Нет EG-родителя numb={row['numb']}, детей={row['child_count']}"
            )
        return lines


@dataclass
class ParentShellsResult:
    created_or_planned: int = 0
    unique_parent_numbs: int = 0
    planned_numbs: set[int] = field(default_factory=set)
    samples: list[dict] = field(default_factory=list)
    skipped_no_station: list[dict] = field(default_factory=list)
    created_without_station: int = 0
    warnings: list[str] = field(default_factory=list)


def _station_ids_for_eg(eg_id: int, sess: Session) -> set[int]:
    rows = (
        sess.query(EquipmentGroupSetStation.station_id)
        .join(
            EquipmentGroupSet,
            EquipmentGroupSet.equipment_group_set_station_id
            == EquipmentGroupSetStation.id,
        )
        .filter(EquipmentGroupSet.equipment_group_id == eg_id)
        .filter(EquipmentGroupSetStation.station_id.isnot(None))
        .all()
    )
    return {int(r[0]) for r in rows if r[0] is not None}


def report_composite_vs_station_clusters(
    session: Session | None = None,
    *,
    database_version_id: int | None = None,
) -> CompositeVsStationReport:
    sess = session or db.session
    q = sess.query(EquipmentGroup)
    if database_version_id is not None:
        q = q.filter(
            (EquipmentGroup.database_version_id == database_version_id)
            | (EquipmentGroup.database_version_id.is_(None))
        )
    groups: list[EquipmentGroup] = q.all()

    by_numb: dict[int, list[EquipmentGroup]] = defaultdict(list)
    children_by_main: dict[int, list[EquipmentGroup]] = defaultdict(list)
    for eg in groups:
        numb = _as_int(eg.numb)
        if numb is not None:
            by_numb[numb].append(eg)
        if is_composite_child_group(eg):
            children_by_main[_as_int(eg.main)].append(eg)

    report = CompositeVsStationReport()
    report.children_total = sum(len(v) for v in children_by_main.values())

    for main, kids in children_by_main.items():
        if main is None:
            continue
        parents = [
            g for g in (by_numb.get(main) or []) if is_composite_parent_group(g)
        ]
        if not parents:
            # Любая EG с этим numb без main тоже кандидат в оболочку
            parents = [
                g
                for g in (by_numb.get(main) or [])
                if _as_int(getattr(g, "main", None)) in (None, 0)
            ]
        if parents:
            report.parents_with_children += 1
        else:
            report.orphan_children_no_parent += len(kids)
            report.missing_parent_shells.append(
                {"numb": main, "child_count": len(kids)}
            )

        station_ids: set[int] = set()
        eg_ids: list[int] = []
        for eg in kids + parents:
            eg_ids.append(eg.id)
            station_ids |= _station_ids_for_eg(eg.id, sess)
        if len(station_ids) > 1:
            report.clusters_split_across_stations.append(
                {
                    "main": main,
                    "station_ids": sorted(station_ids),
                    "eg_ids": eg_ids,
                }
            )

    # Station с несколькими EG без MAIN — наследие grouping_station.
    station_to_egs: dict[int, list[EquipmentGroup]] = defaultdict(list)
    for eg in groups:
        if is_composite_child_group(eg) or is_composite_parent_group(eg):
            continue
        for sid in _station_ids_for_eg(eg.id, sess):
            station_to_egs[sid].append(eg)
    for sid, egs in station_to_egs.items():
        uniq = {e.id: e for e in egs}
        if len(uniq) >= 2:
            report.stations_with_multi_eg_no_main.append(
                {"station_id": sid, "eg_ids": sorted(uniq.keys())}
            )

    report.message = " | ".join(report.to_flash_lines())
    return report


def _normalize_main(value: Any) -> int | None:
    v = _as_int(value)
    if v is None or v == 0:
        return None
    return v


def _effective_flags(
    eg: EquipmentGroup,
    pending_flag_updates: dict[int, dict[str, int | None]] | None,
) -> dict[str, int | None]:
    if pending_flag_updates and eg.id in pending_flag_updates:
        raw = pending_flag_updates[eg.id]
        return {
            "comp": _as_int(raw.get("comp")),
            "main": _normalize_main(raw.get("main")),
            "niv": _as_int(raw.get("niv")),
        }
    return {
        "comp": _as_int(getattr(eg, "comp", None)),
        "main": _normalize_main(getattr(eg, "main", None)),
        "niv": _as_int(getattr(eg, "niv", None)),
    }


def _parent_display_name(donor: EquipmentGroup, meta: dict[str, Any], sess: Session) -> str:
    """Имя родителя: Excel → Station.name → усечённое имя ребёнка."""
    excel_name = (meta.get("name") or "").strip()
    if excel_name:
        return excel_name[:255]
    from app.fuel.services.equipment_groups.equipment_group_edit_services import (
        _get_station_id_for_equipment_group,
    )
    from app.generation.models.station.station_model import Station

    sid = _get_station_id_for_equipment_group(donor.id)
    if sid:
        st = sess.get(Station, sid) if hasattr(sess, "get") else Station.query.get(sid)
        if st and (st.name or "").strip():
            return (st.name or "").strip()[:255]
    raw = (donor.name_ext or donor.name or "").strip()
    for sep in ("(", "（"):
        if sep in raw:
            raw = raw.split(sep, 1)[0].strip()
    return (raw or f"станция numb={donor.main}")[:255]


def _pick_station_donor_for_kids(
    kids: list[EquipmentGroup],
) -> tuple[int | None, EquipmentGroup | None, str]:
    """
    Station и донор среди детей.
    Возвращает (station_id, donor_eg, status) где status: ok|multi_station|no_station.
    """
    from app.fuel.services.equipment_groups.equipment_group_edit_services import (
        _get_station_id_for_equipment_group,
    )

    counts: Counter[int] = Counter()
    donor_by_sid: dict[int, EquipmentGroup] = {}
    for eg in kids:
        sid = _get_station_id_for_equipment_group(eg.id)
        if sid:
            counts[sid] += 1
            donor_by_sid.setdefault(int(sid), eg)
    if not counts:
        return None, None, "no_station"
    best_sid, _ = counts.most_common(1)[0]
    status = "multi_station" if len(counts) > 1 else "ok"
    return best_sid, donor_by_sid[best_sid], status


def _resolve_station_for_parent(
    kids: list[EquipmentGroup],
    all_siblings: list[EquipmentGroup],
    target_ver: int | None,
) -> tuple[int | None, EquipmentGroup | None, str]:
    """
    Station для родителя целевой версии:
    1) голоса детей этой версии;
    2) иначе сиблинги других версий + resolve station по external_code;
    3) иначе no_station (родителя всё равно можно создать «висящим»).
    """
    from app.fuel.services.equipment_groups.equipment_group_edit_services import (
        _resolve_grouping_station_id_for_db_version,
    )

    sid, donor, status = _pick_station_donor_for_kids(kids)
    if sid and donor is not None:
        resolved = _resolve_grouping_station_id_for_db_version(sid, target_ver)
        if resolved:
            return resolved, donor, status
        # станция детей уже в нужной версии или resolve не нашёл копию —
        # оставляем якорь (лучше, чем ничего)
        return sid, donor, status

    sid2, donor2, status2 = _pick_station_donor_for_kids(all_siblings)
    if not sid2 or donor2 is None:
        return None, (kids[0] if kids else None), "no_station"

    resolved = _resolve_grouping_station_id_for_db_version(sid2, target_ver)
    if resolved:
        return resolved, donor2, "sibling_fallback"
    # копии станции в target_ver нет — всё же даём якорь с пометкой
    return sid2, donor2, "sibling_fallback_other_ver"


def _meta_or_donor(meta: dict[str, Any], key: str, donor_value: Any) -> Any:
    if key in meta and meta.get(key) is not None:
        return meta.get(key)
    return donor_value


def _distinct_eg_version_ids(sess: Session) -> list[int | None]:
    rows = sess.query(EquipmentGroup.database_version_id).distinct().all()
    vers = [r[0] for r in rows]
    # стабильный порядок: сначала NULL, потом по id
    return sorted(vers, key=lambda v: (v is not None, v or 0))


def _find_station_id_by_name(
    sess: Session, name: str, version_id: int | None
) -> int | None:
    if not (name or "").strip():
        return None
    from app.common.services.database_version_filter import filter_by_explicit_db_version
    from app.generation.models.station.station_model import Station

    needle = name.strip()
    q = filter_by_explicit_db_version(Station.query, Station, version_id)
    # точное имя, затем startswith
    found = q.filter(Station.name == needle).first()
    if found:
        return int(found.id)
    found = q.filter(Station.name.ilike(needle)).first()
    if found:
        return int(found.id)
    found = q.filter(Station.name.ilike(needle + "%")).first()
    if found:
        return int(found.id)
    return None


def _default_type_id_for_version(sess: Session, version_id: int | None) -> int | None:
    """Любой equipment_group_type_id, уже используемый в этой версии."""
    q = sess.query(EquipmentGroupSetStation.equipment_group_type_id).filter(
        EquipmentGroupSetStation.equipment_group_type_id.isnot(None)
    )
    if version_id is None:
        q = q.filter(EquipmentGroupSetStation.database_version_id.is_(None))
    else:
        q = q.filter(EquipmentGroupSetStation.database_version_id == version_id)
    row = q.first()
    if row and row[0] is not None:
        return int(row[0])
    row = (
        sess.query(EquipmentGroupSetStation.equipment_group_type_id)
        .filter(EquipmentGroupSetStation.equipment_group_type_id.isnot(None))
        .first()
    )
    return int(row[0]) if row and row[0] is not None else None


def _build_parent_eg(
    *,
    name: str,
    numb: int,
    ver: int | None,
    meta: dict[str, Any],
    donor: EquipmentGroup | None,
    comp: int | None = 1,
    main: int | None = None,
) -> EquipmentGroup:
    main_n = _normalize_main(main if main is not None else meta.get("main"))
    eg = EquipmentGroup(
        name=str(name)[:255],
        name_ext=str(name)[:255],
        numb=numb,
        comp=_as_int(comp if comp is not None else meta.get("comp")),
        main=main_n,
        niv=_as_int(meta.get("niv")),
        d=_as_int(_meta_or_donor(meta, "d", getattr(donor, "d", None) if donor else None)),
        r=_as_int(_meta_or_donor(meta, "r", getattr(donor, "r", None) if donor else None)),
        forem=_as_int(
            _meta_or_donor(meta, "forem", getattr(donor, "forem", None) if donor else None)
        ),
        obl=_as_int(_meta_or_donor(meta, "obl", getattr(donor, "obl", None) if donor else None)),
        dep=_as_int(_meta_or_donor(meta, "dep", getattr(donor, "dep", None) if donor else None)),
        oes=_as_int(_meta_or_donor(meta, "oes", getattr(donor, "oes", None) if donor else None)),
        er=_as_int(_meta_or_donor(meta, "er", getattr(donor, "er", None) if donor else None)),
        fo=_as_int(_meta_or_donor(meta, "fo", getattr(donor, "fo", None) if donor else None)),
        vedomstvo=_as_int(
            _meta_or_donor(
                meta, "vedomstvo", getattr(donor, "vedomstvo", None) if donor else None
            )
        ),
        tm=(
            meta.get("tm")
            if meta.get("tm") is not None
            else (getattr(donor, "tm", None) if donor else None)
        ),
        addr=(
            meta.get("addr")
            if meta.get("addr") is not None
            else (getattr(donor, "addr", None) if donor else None)
        ),
        note=(
            meta.get("note")
            if meta.get("note") is not None
            else (getattr(donor, "note", None) if donor else None)
        ),
        codegor=_as_int(
            _meta_or_donor(
                meta, "codegor", getattr(donor, "codegor", None) if donor else None
            )
        ),
        be=_as_int(_meta_or_donor(meta, "be", getattr(donor, "be", None) if donor else None)),
        gk=_as_int(_meta_or_donor(meta, "gk", getattr(donor, "gk", None) if donor else None)),
        gkf=_as_int(
            _meta_or_donor(meta, "gkf", getattr(donor, "gkf", None) if donor else None)
        ),
        regional_district_id=getattr(donor, "regional_district_id", None) if donor else None,
        regional_energy_system_id=(
            getattr(donor, "regional_energy_system_id", None) if donor else None
        ),
        database_version_id=ver,
    )
    for attr, maxlen in (("ordnumb", 255), ("n1", 255), ("n2", 255), ("p1", 255), ("p2", 255)):
        raw = meta.get(attr)
        if raw is None or (isinstance(raw, float) and raw != raw):
            continue
        text = str(raw).strip()
        if text:
            setattr(eg, attr, text[:maxlen])
    return eg


def create_missing_parent_shells_from_children(
    session: Session | None = None,
    *,
    dry_run: bool = True,
    database_version_id: int | None = None,
    excel_parents: dict[str, dict[str, Any]] | None = None,
    pending_flag_updates: dict[int, dict[str, int | None]] | None = None,
    require_station: bool = False,
) -> ParentShellsResult:
    """
    Phase A: создаёт EG-родителей там, где дети в АРМ ссылаются по MAIN,
    а numb родителя для этой database_version_id отсутствует.

    Station: дети этой версии → сиблинги других версий (resolve по external_code).
    Если станции нет — создаём «висящего» родителя (require_station=False по умолчанию).
    """
    sess = session or db.session
    excel_parents = excel_parents or {}
    pending_flag_updates = pending_flag_updates or {}
    result = ParentShellsResult()

    q = sess.query(EquipmentGroup)
    if database_version_id is not None:
        q = q.filter(EquipmentGroup.database_version_id == database_version_id)
    groups = q.all()

    existing_parent_keys: set[tuple[int, int | None]] = set()
    children_by_main_ver: dict[tuple[int, int | None], list[EquipmentGroup]] = defaultdict(
        list
    )
    children_by_main: dict[int, list[EquipmentGroup]] = defaultdict(list)

    for eg in groups:
        numb = _as_int(eg.numb)
        ver = getattr(eg, "database_version_id", None)
        flags = _effective_flags(eg, pending_flag_updates)
        main = flags["main"]

        if numb is not None and is_main_empty(main):
            existing_parent_keys.add((numb, ver))

        if main is not None and main > 0:
            children_by_main_ver[(main, ver)].append(eg)
            children_by_main[main].append(eg)

    unique_numbs: set[int] = set()

    for (main, ver), kids in sorted(
        children_by_main_ver.items(), key=lambda x: (x[0][0], x[0][1] or -1)
    ):
        if (main, ver) in existing_parent_keys:
            continue

        meta = excel_parents.get(str(main)) or {}
        siblings = children_by_main.get(main) or kids
        station_id, donor, st_status = _resolve_station_for_parent(kids, siblings, ver)
        if donor is None:
            donor = kids[0]

        name = _parent_display_name(donor, meta, sess)
        sample = {
            "numb": main,
            "name": str(name)[:80],
            "from_child_id": donor.id,
            "database_version_id": ver,
            "child_count": len(kids),
            "station_id": station_id,
            "station_status": st_status,
            "from_excel": bool(meta),
            "phase": "A",
        }

        if require_station and station_id is None:
            result.skipped_no_station.append(sample)
            result.warnings.append(
                f"Родитель numb={main} ver={ver}: нет Station — пропуск."
            )
            continue

        if st_status == "multi_station":
            result.warnings.append(
                f"Родитель numb={main} ver={ver}: дети на нескольких Station; "
                f"взята station_id={station_id} (макс. голосов)."
            )
        elif st_status == "sibling_fallback":
            result.warnings.append(
                f"Родитель numb={main} ver={ver}: Station взята у сиблингов "
                f"другой версии → station_id={station_id}."
            )
        elif st_status == "sibling_fallback_other_ver":
            result.warnings.append(
                f"Родитель numb={main} ver={ver}: нет копии Station в версии, "
                f"привязка к station_id={station_id} из другой версии."
            )
        elif st_status == "no_station":
            result.warnings.append(
                f"Родитель numb={main} ver={ver}: Station нет — создаём без привязки."
            )
            result.created_without_station += 1

        if not meta:
            result.warnings.append(
                f"Родитель numb={main}: нет строки в Excel — имя/поля с донора-ребёнка."
            )
        elif _as_int(meta.get("comp")) != 1:
            result.warnings.append(
                f"Родитель numb={main}: в Excel COMP≠1, но дети ссылаются по MAIN — "
                "создаём с comp=1."
            )

        unique_numbs.add(main)
        result.planned_numbs.add(main)
        result.samples.append(sample)

        if dry_run:
            result.created_or_planned += 1
            continue

        parent = _build_parent_eg(
            name=name, numb=main, ver=ver, meta=meta, donor=donor
        )
        if isinstance(parent.tm, str):
            parent.tm = parent.tm[:255]
        if isinstance(parent.addr, str):
            parent.addr = parent.addr[:255]
        if isinstance(parent.note, str):
            parent.note = parent.note[:1000]

        sess.add(parent)
        sess.flush()
        if station_id is not None:
            _ensure_parent_set_like_donor(sess, parent, donor, station_id, version_id=ver)
            try:
                parent._populate_regional_ids()
            except Exception:
                pass
        existing_parent_keys.add((main, ver))
        result.created_or_planned += 1

    result.unique_parent_numbs = len(unique_numbs)
    if not dry_run and result.created_or_planned:
        sess.flush()
    by_numb_sample: dict[int, dict] = {}
    for s in result.samples:
        by_numb_sample.setdefault(int(s["numb"]), s)
    result.samples = list(by_numb_sample.values())[:40]
    return result


def create_phase_b_comp1_parents_from_excel(
    session: Session | None = None,
    *,
    dry_run: bool = True,
    excel_parents: dict[str, dict[str, Any]] | None = None,
    version_ids: list[int | None] | None = None,
) -> ParentShellsResult:
    """
    Phase B: COMP=1 из Excel, которых ещё нет в АРМ ни в одной версии.
    Создаёт родителя на каждую используемую database_version_id словаря EG.
    Station — по имени из Excel; если нет — «висит» без привязки.
    """
    sess = session or db.session
    excel_parents = excel_parents or {}
    result = ParentShellsResult()

    existing_numbs: set[int] = set()
    for (numb,) in (
        sess.query(EquipmentGroup.numb)
        .filter(EquipmentGroup.numb.isnot(None))
        .distinct()
        .all()
    ):
        n = _as_int(numb)
        if n is not None:
            existing_numbs.add(n)

    versions = version_ids if version_ids is not None else _distinct_eg_version_ids(sess)
    if not versions:
        versions = [None]

    unique_numbs: set[int] = set()
    for numb_key, meta in sorted(
        excel_parents.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0
    ):
        if _as_int(meta.get("comp")) != 1:
            continue
        numb = _as_int(numb_key)
        if numb is None or numb in existing_numbs:
            continue

        name = (meta.get("name") or f"станция numb={numb}").strip()
        unique_numbs.add(numb)
        result.planned_numbs.add(numb)

        for ver in versions:
            station_id = _find_station_id_by_name(sess, name, ver)
            sample = {
                "numb": numb,
                "name": name[:80],
                "from_child_id": None,
                "database_version_id": ver,
                "child_count": 0,
                "station_id": station_id,
                "station_status": "by_name" if station_id else "no_station",
                "from_excel": True,
                "phase": "B",
            }
            result.samples.append(sample)
            if station_id is None:
                result.created_without_station += 1

            if dry_run:
                result.created_or_planned += 1
                continue

            parent = _build_parent_eg(
                name=name, numb=numb, ver=ver, meta=meta, donor=None
            )
            if isinstance(parent.tm, str):
                parent.tm = parent.tm[:255]
            if isinstance(parent.addr, str):
                parent.addr = parent.addr[:255]
            if isinstance(parent.note, str):
                parent.note = parent.note[:1000]
            sess.add(parent)
            sess.flush()
            if station_id is not None:
                type_id = _default_type_id_for_version(sess, ver)
                if type_id is not None:
                    _ensure_parent_set_on_station(
                        sess,
                        parent,
                        station_id=station_id,
                        type_id=type_id,
                        version_id=ver,
                    )
                    try:
                        parent._populate_regional_ids()
                    except Exception:
                        pass
            result.created_or_planned += 1

        existing_numbs.add(numb)

    result.unique_parent_numbs = len(unique_numbs)
    if not dry_run and result.created_or_planned:
        sess.flush()
    by_numb_sample: dict[int, dict] = {}
    for s in result.samples:
        by_numb_sample.setdefault(int(s["numb"]), s)
    result.samples = list(by_numb_sample.values())[:40]
    return result


def create_missing_numbs_from_excel(
    session: Session | None = None,
    *,
    dry_run: bool = True,
    excel_rows: dict[str, dict[str, Any]] | None = None,
    database_version_id: int | None = None,
    exclude_numbs: set[int] | None = None,
) -> ParentShellsResult:
    """
    Создаёт EquipmentGroup для NUMB из «Имена_станций», которых нет в текущей
    версии БД. Без привязки к Station — связь можно проставить вручную позже.

    Не создаёт NUMB=0 и строки-заголовки. exclude_numbs — уже запланированные
    Phase A/B, чтобы не дублировать.
    database_version_id=None: существование проверяется по всем версиям
    (чтобы не предлагать дубликаты с ver=NULL); запись в этом режиме
    вызывающий код должен запретить.
    """
    sess = session or db.session
    excel_rows = excel_rows or {}
    exclude = exclude_numbs or set()
    result = ParentShellsResult()

    existing_in_ver: set[int] = set()
    q = sess.query(EquipmentGroup.numb).filter(EquipmentGroup.numb.isnot(None))
    if database_version_id is not None:
        q = q.filter(EquipmentGroup.database_version_id == database_version_id)
    for (numb,) in q.distinct().all():
        n = _as_int(numb)
        if n is not None:
            existing_in_ver.add(n)

    unique_numbs: set[int] = set()
    for numb_key, meta in sorted(
        excel_rows.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0
    ):
        numb = _as_int(numb_key)
        if numb is None or numb == 0:
            continue
        if numb in existing_in_ver or numb in exclude:
            continue
        name = (meta.get("name") or "").strip()
        if not name or name.lower().startswith("наименование"):
            continue

        unique_numbs.add(numb)
        result.planned_numbs.add(numb)
        main_n = _normalize_main(meta.get("main"))
        sample = {
            "numb": numb,
            "name": name[:80],
            "main": main_n,
            "comp": _as_int(meta.get("comp")),
            "niv": _as_int(meta.get("niv")),
            "database_version_id": database_version_id,
            "station_id": None,
            "station_status": "unattached",
            "from_excel": True,
            "phase": "missing_numb",
        }
        result.samples.append(sample)
        result.created_without_station += 1

        if dry_run:
            result.created_or_planned += 1
            continue

        eg = _build_parent_eg(
            name=name,
            numb=numb,
            ver=database_version_id,
            meta=meta,
            donor=None,
            comp=_as_int(meta.get("comp")),
            main=main_n,
        )
        if isinstance(eg.tm, str):
            eg.tm = eg.tm[:255]
        if isinstance(eg.addr, str):
            eg.addr = eg.addr[:255]
        if isinstance(eg.note, str):
            eg.note = eg.note[:1000]
        sess.add(eg)
        result.created_or_planned += 1
        existing_in_ver.add(numb)

    result.unique_parent_numbs = len(unique_numbs)
    if not dry_run and result.created_or_planned:
        sess.flush()
    by_numb_sample: dict[int, dict] = {}
    for s in result.samples:
        by_numb_sample.setdefault(int(s["numb"]), s)
    result.samples = list(by_numb_sample.values())[:40]
    return result


def _ensure_parent_set_on_station(
    sess: Session,
    parent: EquipmentGroup,
    *,
    station_id: int,
    type_id: int,
    version_id: int | None,
) -> None:
    existing = (
        sess.query(EquipmentGroupSetStation)
        .filter_by(
            station_id=station_id,
            equipment_group_type_id=type_id,
            database_version_id=version_id,
        )
        .first()
    )
    if existing is None:
        existing = EquipmentGroupSetStation(
            station_id=station_id,
            equipment_group_type_id=type_id,
            database_version_id=version_id,
        )
        sess.add(existing)
        sess.flush()
    already = (
        sess.query(EquipmentGroupSet)
        .filter_by(
            equipment_group_id=parent.id,
            equipment_group_set_station_id=existing.id,
        )
        .first()
    )
    if already is None:
        sess.add(
            EquipmentGroupSet(
                equipment_group_id=parent.id,
                equipment_group_set_station_id=existing.id,
            )
        )
        sess.flush()


def _ensure_parent_set_like_donor(
    sess: Session,
    parent: EquipmentGroup,
    donor: EquipmentGroup,
    station_id: int,
    *,
    version_id: int | None = None,
) -> None:
    """Вешает родителя на (station, type); version берётся из аргумента или донора."""
    donor_sets = (
        sess.query(EquipmentGroupSet)
        .filter_by(equipment_group_id=donor.id)
        .all()
    )
    type_id = None
    donor_ver = None
    if donor_sets:
        donor_link = EquipmentGroupSetStation.query.get(
            donor_sets[0].equipment_group_set_station_id
        )
        if donor_link:
            type_id = donor_link.equipment_group_type_id
            donor_ver = donor_link.database_version_id
    if type_id is None:
        type_id = _default_type_id_for_version(
            sess, version_id if version_id is not None else donor_ver
        )
    if type_id is None:
        return
    v_id = version_id if version_id is not None else donor_ver
    _ensure_parent_set_on_station(
        sess,
        parent,
        station_id=station_id,
        type_id=int(type_id),
        version_id=v_id,
    )