"""Compare runtime helpers with cached Excel results without changing the database.

Run from the repository root: python -m reports.rational_structure_calculation_pages.audit_runtime_formulas <xlsx>
The comparison isolates each column using its cached Excel dependencies.
"""
import argparse
from collections import Counter, defaultdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from app.rational_structure.services import equipment_runtime_machine_services as runtime


def number(value):
    return Decimal(str(value)) if isinstance(value, (int, float)) else value


def audit(path):
    values_book = load_workbook(path, read_only=True, data_only=True)
    formulas_book = load_workbook(path, read_only=True, data_only=False)
    try:
        sheet_name = next(name for name in values_book.sheetnames if name.replace(chr(0x451), 'е') == 'Расчет')
        hours = defaultdict(list)
        for sheet in (values_book['Турбины'], values_book['Турбины газовые']):
            for row in sheet.iter_rows(min_row=2, max_col=17, values_only=True):
                if isinstance(row[1], (int, float)) and isinstance(row[16], (int, float)) and row[16] != 0:
                    hours[str(row[0]).strip()].append((int(row[1]), number(row[16])))
        matches, compared, differences = Counter(), Counter(), defaultdict(list)
        overrides = defaultdict(list)
        errors = Counter()
        years = Counter()
        count = 0
        value_rows = values_book[sheet_name].iter_rows(min_row=2, max_col=64, values_only=True)
        formula_rows = formulas_book[sheet_name].iter_rows(min_row=2, max_col=64)
        for row_number, (row, formula_cells) in enumerate(zip(value_rows, formula_rows), 2):
            if row[2] in (None, ''):
                continue
            count += 1
            years[str(row[3])] += 1
            v = {get_column_letter(i): number(value) for i, value in enumerate(row, 1)}
            for cell in formula_cells:
                if cell.data_type == 'e':
                    errors[cell.value] += 1
            characteristic = SimpleNamespace(
                standard_service_life=v['S'], operating_hours_total=v['T'],
                commissioning_year=v['M'], expected_service_life_year=v['V'])
            year = int(v['D'])
            is_coal = str(v['AM']).casefold() == 'уголь'
            annual = [value for report_year, value in hours[str(v['C']).strip()] if year - 2 <= report_year <= year]
            results = {'AN': sum(annual) / len(annual) if annual else 0}
            results['AO'] = runtime._remaining_double_resource(characteristic, year)
            results['AP'] = runtime._resource_dismantling_year(characteristic, v, year)
            results['AQ'] = runtime._first_resource_year(characteristic, v['AN'], year)
            results['AR'] = runtime._modernization_year(characteristic, v, year, 2042)
            results['AS'] = runtime._modernization_sipr_year(v, 2031)
            results.update(runtime._dismantling_years(characteristic, v, is_coal, year, 2042, 2031))
            results.update(runtime._dismantling_transfers(v, 2042, 2031))
            results['BC'] = runtime._dismantling_without_modernization(v, 2031)
            results.update(runtime._exceeded_double_resources(characteristic, is_coal, year))
            for key, actual in results.items():
                expected = v[key]
                compared[key] += 1
                equal = actual == expected
                if isinstance(actual, (int, float, Decimal)) and isinstance(expected, (int, float, Decimal)):
                    equal = abs(Decimal(str(actual)) - Decimal(str(expected))) < Decimal('0.00000001')
                if equal:
                    matches[key] += 1
                else:
                    differences[key].append({'cell': f'{key}{row_number}', 'code': str(v['C']),
                                             'station': v['G'], 'excel': expected, 'python': actual})
            for key in ('AS', 'BC'):
                cell = formula_cells[44 if key == 'AS' else 54]
                if cell.data_type != 'f' or (key == 'BC' and '$AS' not in cell.value):
                    overrides[key].append({'cell': f'{key}{row_number}', 'value': cell.value})
        return {'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'rows': count, 'years': dict(years), 'cached_errors_first_64_columns': dict(errors),
                'comparison': {key: {'compared': compared[key], 'matched': matches[key],
                                     'different': len(differences[key])} for key in compared},
                'differences': dict(differences), 'nonstandard_cells': dict(overrides),
                'scope': 'Cached dependencies; report year per row; rolling three-year mean across steam/gas sheets; source constants 2042 / 2032; no Excel recalculation; no database writes.'}
    finally:
        formulas_book.close()
        values_book.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workbook', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = audit(args.workbook)
    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key not in ('differences', 'nonstandard_cells')},
                     ensure_ascii=False, indent=2))
