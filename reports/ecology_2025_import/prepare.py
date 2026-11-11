import hashlib
import json
import re
import runpy
from decimal import Decimal
from pathlib import Path

import openpyxl

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
SOURCE = Path(r'z:\НИО-10\АРМ ГС\05. Шаблоны для АРМ ГС\9. Экология\Копия Топливо для экологии_отчетный год 2025_29.10.2026_для загрузки.xlsx')
constants = runpy.run_path(str(ROOT / 'app/ecology/services/operating_tes_constants.py'))
workbook = openpyxl.load_workbook(SOURCE, data_only=True)
assert workbook.sheetnames == ['Факт 2025_ОЭС']
sheet = workbook.active
assert (sheet.max_row, sheet.max_column) == (89, 14)
headers = ['Общий итог', 'Минэнерго', 'Пром.предпр.', 'Севзап', 'Центр', 'Волга', 'Юг', 'Урал', 'Сибирь', 'Восток', 'ТИТЭС Востока', 'ТИТЭС Сибири', 'Николаевский энергоузел']
slugs = ['vsego', 'minen', 'prompred', 'severo-zapad', 'centr', 'srednyaya-volga', 'yug', 'ural', 'sibir', 'vostok', 'isolated-dv', 'norilsk', 'nikolaevsky']
assert [sheet.cell(1, c).value for c in range(2, 15)] == headers
assert set(slugs) == {t['slug'] for t in constants['TERRITORIES']}


def normalize(label):
    return re.sub(r'[^а-яa-z0-9]', '', re.sub(r'в\s*т\.\s*ч\.', '', label.lower()))


aliases = {
    'gas_artificial': 'Газ искусственный', 'blast_furnace_gas': 'газ доменный',
    'coke_oven_gas': 'газ коксовый', 'npz_gas': 'прочий газ',
    'oil_fuel': 'Нефтотопливо', 'other_misc': 'иное', 'lpg': 'сжиженный газ',
    'kuzn_gd': 'кузнецкий ГД', 'kuzn_other': 'кузнецкий УН',
    'ural': 'Уральский', 'bashkir': 'Башкирский', 'khakass': 'Хакасский',
    'tuva': 'Тувинский', 'zabaykal': 'Читинские', 'ushumun': 'Ушумунский',
    'bikin': 'Бикинский', 'chukotka': 'Чукотский', 'kazakhstan': 'Казахстанский',
    'karazhyra': 'каражирский',
}
rows = [(2, 'e', 'Выработка электроэнергии, млрд.кВт.ч'),
        (3, 'q', 'Отпуск тепла, тыс.Гкал'), (4, 'b', 'Расход топлива, тыс.тут')]
assert len(constants['FUEL_ROWS']) == 84
for number, spec in enumerate(constants['FUEL_ROWS'], 5):
    number += number >= 13
    expected = aliases.get(spec['key'], spec['label'])
    actual = sheet.cell(number, 1).value
    assert normalize(actual) == normalize(expected), (number, actual, expected)
    rows.append((number, constants['FUEL_PARAM_FIELDS'][spec['key']], actual))
assert normalize(sheet.cell(13, 1).value) == normalize('газотурбинное топливо')
payload = {slug: {} for slug in slugs}
empty = []
for number, field, label in rows:
    for column, slug in enumerate(slugs, 2):
        value = sheet.cell(number, column).value
        if value is None:
            empty.append(sheet.cell(number, column).coordinate)
            continue
        assert isinstance(value, (int, float)) and not isinstance(value, bool)
        amount = Decimal(str(value))
        assert amount.is_finite() and amount >= 0
        if field == 'e':
            amount *= 1000
        payload[slug][field] = str(amount)
extra = {slug: str(Decimal(str(sheet.cell(13, col).value))) for col, slug in enumerate(slugs, 2) if sheet.cell(13, col).value is not None}
for slug, value in extra.items():
    assert Decimal(value).is_finite() and Decimal(value) >= 0
    payload[slug]['gtt'] = value
rows.append((13, 'gtt', sheet.cell(13, 1).value))
rows.sort()
manifest = {
    'source': str(SOURCE), 'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    'sheet': sheet.title, 'year': 2025, 'database_version_id': 37,
    'snapshot_id': 66, 'scope': 'operating', 'rows': rows,
    'columns': dict(zip(headers, slugs)), 'empty_cells': empty,
    'mapped_numeric_cells': sum(map(len, payload.values())),
    'gas_turbine_values': extra, 'gas_turbine_policy': 'Separate gtt field, matching catalog nazvl=GTT, fuel id=3852, version=37.',
    'units': 'Generation: billion kWh in Excel, million kWh in storage; other values unchanged. No rounding.',
}
(OUT / 'payload.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
(OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: manifest[k] for k in ['source_sha256', 'mapped_numeric_cells', 'gas_turbine_values']}, ensure_ascii=False))
