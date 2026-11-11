import re
import unicodedata
from decimal import Decimal
from difflib import SequenceMatcher

from app.common.services.help_services import format_decimal_for_display


_FIELDS = {
    "subject_name": "Собственник",
    "station_name": "Станция",
    "station_number": "Станционный номер",
    "equipment_brand": "Марка оборудования",
    "installed_electric_power": "Установленная электрическая мощность, МВт",
}

# Поля, обязательные для статуса "matched" (Субъект ЭЭ исключен по требованию)
_MATCH_REQUIRED_FIELDS = {"station_name", "equipment_brand", "installed_electric_power"}
_POWER_REL_TOLERANCE = Decimal("0.005")
_VISUAL_LETTERS = str.maketrans("abcehkmoptxy", "авсенкмортху")
_LEGAL_FORMS = re.compile(r"\b(?:ооо|пао|оао|зао|ао|ип|фгуп|гуп|муп)\b")
_INSIGNIFICANT = re.compile(r"[\s\-‐‑‒––−'\"«»„“”‘’`]+")
_STATION_PARENTHESES = re.compile(r"\([^()]*\)")


def _normalize_text(value: str | None, field: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").casefold().replace("\u0451", "е")
    if field == "subject_name":
        text = _LEGAL_FORMS.sub("", text)
    if field == "equipment_brand":
        text = text.translate(_VISUAL_LETTERS)
    if field == "station_name":
        # Скобочное уточнение номера не меняет принадлежность к станции.
        text = _STATION_PARENTHESES.sub("", text)

    def remove_separator(match: re.Match) -> str:
        start, end = match.span()
        if start and end < len(text) and text[start - 1].isdigit() and text[end].isdigit():
            return "|"
        return ""

    text = _INSIGNIFICANT.sub(remove_separator, text)
    if field == "station_number":
        # NFKC превращает знак номера в латинское No; префикс допустим только перед числом.
        text = re.sub(r"^(?:ст\.?)?(?:no)?(?=\d)", "", text)
        if re.fullmatch(r"\d+(?:[.,]0+)?", text):
            return str(int(text.replace(",", ".").split(".")[0]))
    return text


def _normalize(record: dict) -> dict:
    normalized = {
        field: _normalize_text(record.get(field), field)
        for field in _FIELDS if field != "installed_electric_power"
    }
    power = record.get("installed_electric_power")
    normalized["installed_electric_power"] = power if power is not None and power.is_finite() else None
    return normalized


def _equal(field: str, source: dict, target: dict) -> bool:
    left, right = source[field], target[field]
    if left is None or right is None or left == "" or right == "":
        return False
    if field == "installed_electric_power":
        scale = max(abs(left), abs(right))
        if scale == 0:
            return left == right
        return abs(left - right) <= scale * _POWER_REL_TOLERANCE
    return left == right


def _similarity(source: str, target: str) -> float:
    if not source or not target:
        return 0.0
    if source == target:
        return 1.0
    # Близость текста не должна скрывать разные номера станций или моделей.
    if re.findall(r"\d+", source) != re.findall(r"\d+", target):
        return 0.0
    return SequenceMatcher(None, source, target, autojunk=False).ratio()


_BRAND_EQUIVALENT_RATIO = 0.75
_BRAND_TOKENS = re.compile(r"[0-9]+|[a-zа-я]+")


def _brand_parts(text: str) -> tuple[str, str]:
    head = ""
    first_number = ""
    for token in _BRAND_TOKENS.findall(text):
        if token.isdigit():
            if not first_number:
                first_number = token
        elif not head:
            head = token
        if head and first_number:
            break
    return head, first_number


def _brand_key(text: str) -> str:
    return re.sub(r"[^0-9a-zа-я]+", "", text)


def _brand_equivalent(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if _brand_key(left) == _brand_key(right):
        return True
    left_head, left_first = _brand_parts(left)
    right_head, right_first = _brand_parts(right)
    if not left_head or left_head != right_head or not left_first or left_first != right_first:
        return False
    return SequenceMatcher(None, _brand_key(left), _brand_key(right), autojunk=False).ratio() >= _BRAND_EQUIVALENT_RATIO


def _display(value: str | Decimal | None) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return format_decimal_for_display(value, digits=0)
    return value


class MachineMatcher:
    """Порог станции 0.85, подсказки 60/100, неоднозначности 5 баллов."""

    def __init__(self, candidates: list[dict]):
        self._stations: dict[str, list[tuple[dict, dict]]] = {}
        self._station_cache: dict[str, list[tuple[str, float]]] = {}
        for candidate in candidates:
            candidate = candidate.copy()
            normalized = _normalize(candidate)
            station = normalized["station_name"]
            self._stations.setdefault(station, []).append((candidate, normalized))

    def _select_stations(self, station: str) -> list[tuple[str, float]]:
        if station not in self._station_cache:
            if not station:
                selected = []
            elif station in self._stations:
                selected = [(station, 1.0)]
            else:
                selected = []
                for target in self._stations:
                    similarity = _similarity(station, target)
                    if similarity >= 0.85:
                        selected.append((target, similarity))
            self._station_cache[station] = selected
        return self._station_cache[station]

    @staticmethod
    def _score(source: dict, target: dict, station_similarity: float, brand_similarity: float) -> int:
        number_equal = _equal("station_number", source, target)
        if not number_equal and brand_similarity < 0.85:
            return 0
        score = 30 * station_similarity + 30 * number_equal
        if brand_similarity >= 0.85:
            score += 20 * brand_similarity
        score += 10 * _equal("subject_name", source, target)
        if _equal("installed_electric_power", source, target):
            score += 10
        else:
            left, right = source["installed_electric_power"], target["installed_electric_power"]
            if left is not None and right is not None:
                scale = max(abs(left), abs(right))
                if scale and abs(left - right) <= scale * Decimal("0.05"):
                    score += 5
        return round(score)

    @staticmethod
    def _candidate_details(record: dict, candidate: dict, differing: list[str], score: int) -> dict:
        return {
            "machine_id": candidate["machine_id"],
            "pgu_machine_id": candidate.get("pgu_machine_id"),
            "station_id": candidate["station_id"],
            "station_name": candidate["station_name"],
            "station_number": candidate["station_number"],
            "equipment_brand": candidate["equipment_brand"],
            "installed_electric_power": _display(candidate.get("installed_electric_power")),
            "score": score,
            "differences": [
                {"field": field, "label": _FIELDS[field],
                 "source": _display(record.get(field)), "target": _display(candidate.get(field))}
                for field in differing
            ],
        }

    def match(self, record: dict) -> dict:
        source = _normalize(record)
        ranked = []
        exact: list[tuple[dict, bool]] = []
        brand_similarities: dict[str, float] = {}
        for station, similarity in self._select_stations(source["station_name"]):
            for candidate, target in self._stations[station]:
                station_equal = _equal("station_name", source, target)
                power_equal = _equal("installed_electric_power", source, target)
                brand_equal = _brand_equivalent(source["equipment_brand"], target["equipment_brand"])
                if station_equal and power_equal and brand_equal:
                    exact.append((self._candidate_details(record, candidate, [], 100),
                                  _equal("station_number", source, target)))
                    continue
                differing = [field for field in _MATCH_REQUIRED_FIELDS if not _equal(field, source, target)]
                brand = target["equipment_brand"]
                if brand not in brand_similarities:
                    brand_similarities[brand] = _similarity(source["equipment_brand"], brand)
                score = min(99, self._score(source, target, similarity, brand_similarities[brand]))
                if score >= 60:
                    ranked.append(self._candidate_details(record, candidate, differing, score))

        ranked.sort(key=lambda candidate: (-candidate["score"], candidate["machine_id"]))
        exact.sort(key=lambda entry: entry[0]["machine_id"])
        machine_id = None
        pgu_machine_id = None
        if len(exact) == 1:
            status = "matched"
            reason = "Найден единственный агрегат с совпадением станции, марки оборудования и мощности."
            machine_id = exact[0][0]["machine_id"]
            pgu_machine_id = exact[0][0].get("pgu_machine_id")
            selected = [entry[0] for entry in exact]
        elif exact:
            number_matches = [entry for entry in exact if entry[1]]
            if len(number_matches) == 1:
                status = "matched"
                reason = "Станция, марка и мощность совпадают, номер агрегата указывает на единственный вариант."
                machine_id = number_matches[0][0]["machine_id"]
                pgu_machine_id = number_matches[0][0].get("pgu_machine_id")
                selected = [entry[0] for entry in number_matches]
            else:
                status = "ambiguous"
                reason = "Станция, марка оборудования и мощность совпадают у нескольких агрегатов."
                selected = [entry[0] for entry in exact[:3]]
        elif ranked:
            ambiguous = len(ranked) > 1 and ranked[0]["score"] - ranked[1]["score"] <= 5
            status = "ambiguous" if ambiguous else "partial"
            reason = (
                "Найдено несколько агрегатов с близкими оценками; требуется выбор."
                if ambiguous else "Найден вероятный агрегат."
            )
            selected = ranked[:3]
        else:
            status = "unmatched"
            reason = "Нет кандидатов с подходящей станцией и признаками агрегата."
            selected = []
            # Для unmatched ищем похожие станции и показываем как частичное совпадение
            if not selected and source["station_name"]:
                similar_stations = []
                for target_station in self._stations:
                    similarity = _similarity(source["station_name"], target_station)
                    if similarity >= 0.6:
                        similar_stations.append((target_station, similarity))
                similar_stations.sort(key=lambda x: -x[1])
                for station, similarity in similar_stations[:3]:
                    for candidate, target in self._stations[station]:
                        brand = target["equipment_brand"]
                        brand_sim = _similarity(source["equipment_brand"], brand)
                        score = min(99, self._score(source, target, similarity, brand_sim))
                        if score >= 40:
                            differing = [field for field in _MATCH_REQUIRED_FIELDS if not _equal(field, source, target)]
                            selected.append(self._candidate_details(record, candidate, differing, score))
                if selected:
                    status = "partial"
                    reason = "Станция не найдена точно, но есть похожие станции с подходящими агрегатами."
                    selected.sort(key=lambda candidate: (-candidate["score"], candidate["machine_id"]))
                    selected = selected[:3]
        differing_fields = [
            field for field in _FIELDS
            if any(any(diff["field"] == field for diff in item["differences"]) for item in selected)
        ]
        return {
            "machine_id": machine_id,
            "pgu_machine_id": pgu_machine_id,
            "match_status": status,
            "match_details": {
                "reason": reason,
                "differing_fields": differing_fields,
                "candidates": selected,
            },
        }
