from pathlib import Path
from collections import Counter
import ast
import hashlib
import json
import re
import zipfile

from docx import Document
import pymupdf
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent
REFDATA = OUT.parent / 'registration_refdata'
manifest = json.loads((OUT / 'verification_manifest.json').read_text(encoding='utf-8'))
path = OUT / manifest['document']
base_path = OUT / 'qa' / 'before_ecology.docx'
assert hashlib.sha256(base_path.read_bytes()).hexdigest() == manifest['base_sha256']
word = Document(path)
base = Document(base_path)
text = '\n'.join(p.text for p in word.paragraphs)
all_text = text + '\n' + '\n'.join(c.text for t in word.tables for row in t.rows for c in row.cells)
assert not any(c in all_text for c in '\u0451\u0401\u2014')
assert word.paragraphs[1].text == 'АРМ\nМодуль «Экология»'
headings = [p.text for p in word.paragraphs if p.style.name == 'Heading 1']
assert [int(h.split('.')[0]) for h in headings] == list(range(1, 13))
assert headings[1] == '2. Модуль «Экология»: назначение и архитектура'
assert len(word.inline_shapes) == len(manifest['figures']) == 12
assert [f['number'] for f in manifest['figures']] == list(range(1, 13))
assert {f['filename'] for f in manifest['figures'][4:8]} == {
    '09_analysis_pg_with_boilers.png', '10_analysis_pg_without_boilers.png',
    '11_analysis_zv_with_boilers.png', '12_analysis_zv_without_boilers.png'}
assert len(word.tables[0].rows) == 13
assert word.tables[0].cell(0, 2).text == 'Содержание для модуля «Экология»'
assert '/refdata/' not in all_text

refdata_path = REFDATA / 'АРМ_Справочники_Описание_для_госрегистрации.docx'
assert refdata_path.read_bytes() == base_path.read_bytes()
assert refdata_path.with_suffix('.pdf').read_bytes() == base_path.with_suffix('.pdf').read_bytes()
combined = Document(OUT / 'qa' / 'combined_before_split.docx')
start_paragraph = next(i for i, p in enumerate(combined.paragraphs) if p.text == '7. Модуль «Экология»: назначение и архитектура')
assert [p.text for p in combined.paragraphs[start_paragraph:] if p.style.name == 'SourceCode'] == [p.text for p in word.paragraphs if p.style.name == 'SourceCode']
combined_tables = combined.tables[len(base.tables):]
assert len(word.tables) == 1 + len(combined_tables)
for before, after in zip(combined_tables, word.tables[1:]):
    values = [[c.text for c in row.cells] for row in before.rows]
    if values[0][0] == 'Раздел':
        for row in values[1:]:
            prefix, suffix = row[0].split('.', 1)
            row[0] = f'{int(prefix) - 5}.{suffix}'
    assert values == [[c.text for c in row.cells] for row in after.rows]


def image_bytes(document, shape):
    rid = shape._inline.graphic.graphicData.pic.blipFill.blip.embed
    return document.part.related_parts[rid].blob


combined_ecology_images = [image_bytes(combined, s) for s in list(combined.inline_shapes)[-8:]]
final_ecology_images = [image_bytes(word, s) for s in word.inline_shapes]
assert combined_ecology_images[:4] == final_ecology_images[:4]
assert combined_ecology_images[4:] == final_ecology_images[8:]
for screenshot, shape in zip(manifest['figures'][4:8], list(word.inline_shapes)[4:8]):
    cropped = OUT / 'screenshots' / ('document_' + screenshot['filename'])
    assert cropped.exists()
    assert image_bytes(word, shape) == cropped.read_bytes()
analysis_pages = [record for record in manifest['pages'] if record['url'].startswith('/ecology/analysis/')]
assert len(analysis_pages) == 4
for record in analysis_pages:
    assert len(record['screenshots']) == 1
    assert record['screenshots'][0][0] in {f['filename'] for f in manifest['figures'][4:8]}
    assert record['screenshots'][0][1] in text
assert 'могли появиться такие строки' in text
assert 'По согласованию с пользователем страницы анализа были открыты' in text


def structure(element):
    if element is None:
        return None
    return element.tag, dict(element.attrib), [structure(c) for c in element]


for name in ['7.32 Основной текст', 'Heading 1', 'Heading 2', 'Heading 3',
             '7.32 Иллюстрация. Подпись к иллюстрации', '7.32 Иллюстрация. Расположение иллюстрации',
             '7.32 Таблица. 13 Заголовки ГРАФ+основной части таблицы', 'SourceCode', 'toc 1', 'toc 2']:
    for prop in ['pPr', 'rPr']:
        assert structure(getattr(word.styles[name].element, prop)) == structure(getattr(base.styles[name].element, prop)), (name, prop)
assert len(manifest['pages']) == 30
assert len(set(p['section'] for p in manifest['pages'])) == 30
assert len(set(p['url'] for p in manifest['pages'])) == 30
for record in manifest['pages']:
    assert f"{record['section']}. {record['title']}" in text
    assert record['url'] in text
    assert record['functionality'] in text
    assert record['interaction'] in text
    assert record['route'] and record['service'] and record['html']
    for model in record['models']:
        assert 'app/ecology/models/' + model in text
for path_part, digest in manifest['source_sha256'].items():
    assert hashlib.sha256((ROOT / path_part).read_bytes()).hexdigest() == digest, path_part
code_lines = {p.text for p in word.paragraphs if p.style.name == 'SourceCode'}
for item in manifest['excerpts']:
    lines = (ROOT / item['path']).read_text(encoding='utf-8-sig').splitlines()
    assert 1 <= item['first'] <= item['last'] <= len(lines)
    assert f"{item['path']}, строки {item['first']}–{item['last']}" in text
    for number in range(item['first'], item['last'] + 1):
        expected = f'{number:>4}  {lines[number - 1]}'
        expected = expected.replace('\u0451', '\u0435').replace('\u0401', '\u0415').replace('\u2014', '\u2013')
        assert expected in code_lines, (item['path'], number)

actual_routes = []
for route in (ROOT / 'app/ecology/routes').glob('*.py'):
    tree = ast.parse(route.read_text(encoding='utf-8-sig'))
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute) and decorator.func.attr == 'route':
                url = '/ecology' + ast.literal_eval(decorator.args[0])
                methods = next((ast.literal_eval(k.value) for k in decorator.keywords if k.arg == 'methods'), ['GET'])
                actual_routes.append((url, tuple(methods), node.name))
                assert url in all_text, url
expected_routes = [(r['url'], tuple(r['methods']), r['function']) for r in manifest['routes']]
assert Counter(actual_routes) == Counter(expected_routes)
assert len(actual_routes) == 34


def constant(path_part, name):
    tree = ast.parse((ROOT / path_part).read_text(encoding='utf-8-sig'))
    selected = next(n for n in tree.body if (isinstance(n, ast.AnnAssign) and getattr(n.target, 'id', None) == name) or
                    (isinstance(n, ast.Assign) and any(getattr(t, 'id', None) == name for t in n.targets)))
    return selected.value


for file, name, url_prefix in [
    ('operating_tes_constants.py', 'CALC_SHEETS', '/ecology/operating_tes/vsego/'),
    ('new_tes_constants.py', 'NEW_TES_CALC_SHEETS', '/ecology/new_tes/vsego/'),
    ('calculation_summary_services.py', 'CALCULATION_SUMMARY_TABS', '/ecology/calculation_summary/vsego/'),
    ('calculation_summary_services.py', '_LEGACY_TABS', '/ecology/calculation_summary/vsego/'),
    ('gis_tes_fuel_comparison_constants.py', 'COMPARISON_SHEETS', '/ecology/analysis/'),
]:
    items = constant('app/ecology/services/' + file, name)
    for element in items.elts:
        slug = next(ast.literal_eval(v) for k, v in zip(element.keys, element.values) if ast.literal_eval(k) == 'slug')
        assert url_prefix + slug + '/' in text
        if name == 'COMPARISON_SHEETS':
            assert '/ecology/totals_summary/' + slug + '/' in text
with zipfile.ZipFile(path) as archive:
    assert archive.testzip() is None
style_record = json.loads((REFDATA / 'qa' / 'report_styles_applied.json').read_text(encoding='utf-8'))
assert hashlib.sha256(Path(style_record['reference']).read_bytes()).hexdigest() == style_record['reference_sha256']

pdf = pymupdf.open(path.with_suffix('.pdf'))
blank, errors, overflow = [], [], []
start = None
for index, page in enumerate(pdf):
    body = page.get_text()
    if '2. Модуль «Экология»: назначение и архитектура' in body and len(body) > 300:
        start = index
    if len(body.strip()) < 110:
        blank.append(index + 1)
    if re.search(r'Ошибка!|Error!|Reference source not found', body):
        errors.append(index + 1)
    for block in page.get_text('blocks'):
        if block[6] == 0 and (block[0] < 10 or block[2] > page.rect.width - 10 or block[1] < 0 or block[3] > page.rect.height):
            overflow.append(index + 1)
assert start is not None
assert not blank, blank
assert not errors, errors
assert not overflow, overflow
pdf_text = '\n'.join(page.get_text() for page in pdf)
for figure in manifest['figures']:
    assert f"Рисунок {figure['number']}." in pdf_text
toc_text = '\n'.join(p.text for p in word.paragraphs if p.style.name.lower().startswith('toc '))
assert '2. Модуль «Экология»' in toc_text
assert '12. Полнота описания модуля «Экология»' in toc_text
assert 'Страницы справочников' not in toc_text
selected = sorted(set([0, 1, 2, start, start + 2, start + 5, start + 10, start + 20,
                       start + 35, start + 50, len(pdf)-2, len(pdf)-1] +
                      [i for i in range(start, len(pdf)) if pdf[i].get_images()]))
columns = 4
canvas = Image.new('RGB', (1600, ((len(selected) + columns - 1) // columns) * 570), '#ddd')
draw = ImageDraw.Draw(canvas)
for position, number in enumerate(selected):
    pixmap = pdf[number].get_pixmap(matrix=pymupdf.Matrix(.64, .64), alpha=False)
    image = Image.frombytes('RGB', (pixmap.width, pixmap.height), pixmap.samples)
    x, y = position % columns * 400, position // columns * 570
    canvas.paste(image, (x, y + 20))
    draw.text((x + 5, y + 3), str(number + 1), fill='black')
canvas.save(OUT / 'qa' / 'contact_sheet.png')
(OUT / 'document_text_for_review.txt').write_text(all_text, encoding='utf-8')
result = dict(status='passed', document=path.name, pages=len(pdf), ecology_starts_on_page=start+1,
              ecology_screen_presentations=30, analysis_screenshots=4, legacy_tabs=4, route_declarations=34,
              ecology_source_excerpts=len(manifest['excerpts']), ecology_screenshots=len(manifest['figures']),
              total_screenshots=len(word.inline_shapes), refdata_restored_byte_for_byte=True,
              ecology_code_and_tables_preserved=True, ecology_screenshots_preserved=True, styles_preserved=True,
              reference_report_unchanged=True,
              ecology_source_files_sha256_checked=len(manifest['source_sha256']),
              blank_pages=blank, field_errors=errors, text_outside_page=overflow,
              limitations=['No direct data edits, imports, PATCH requests or submission reviews sent',
                           'Analysis GET visits authorized by user; missing parameter rows may have been initialized; counts not checked',
                           'Other automatic-initialization screens documented from source only',
                           'Server build identity and scientific validation not established'])
(OUT / 'qa' / 'verification_result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
