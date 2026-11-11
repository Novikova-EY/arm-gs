from pathlib import Path
import ast
import hashlib
import json
import re
import zipfile

from docx import Document
import pymupdf

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent
manifest = json.loads((OUT / 'verification_manifest.json').read_text(encoding='utf-8'))
path = OUT / manifest['document']
word = Document(path)
text = '\n'.join(para.text for para in word.paragraphs)
text += '\n' + '\n'.join(cell.text for table in word.tables for row in table.rows for cell in row.cells)
assert not any(character in text for character in '\u0451\u0401\u2014')
assert len(word.inline_shapes) == manifest['figures'] == 7
assert len(manifest['pages']) == 25
assert len(word.tables[0].rows) == 13

expected = set()
for route in (ROOT / 'app/refdata/routes').rglob('*routes.py'):
    if route.name in ['database_versions_routes.py', 'refdata_routes.py', 'year_management_routes.py']:
        continue
    tree = ast.parse(route.read_text(encoding='utf-8-sig'))
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        if not (node.name.endswith('_list') or node.name.startswith('add_')):
            continue
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute) and decorator.func.attr == 'route':
                expected.add('/refdata' + ast.literal_eval(decorator.args[0]))
actual = {record[key] for record in manifest['pages'] for key in ['list_url', 'add_url']}
assert actual == expected and len(actual) == 50
for url in actual:
    assert url in text, url

for relative, digest in manifest['source_sha256'].items():
    assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == digest, relative
for excerpt in manifest['excerpts']:
    lines = (ROOT / excerpt['path']).read_text(encoding='utf-8-sig').splitlines()
    assert 1 <= excerpt['first'] <= excerpt['last'] <= len(lines)
    assert f"{excerpt['path']}, строки {excerpt['first']}–{excerpt['last']}" in text
with zipfile.ZipFile(path) as archive:
    assert archive.testzip() is None

pdf = pymupdf.open(path.with_suffix('.pdf'))
errors = []
blank_pages = []
overflows = []
for number, page in enumerate(pdf, 1):
    content = page.get_text()
    if re.search(r'Ошибка!|Error!|Reference source not found', content):
        errors.append(number)
    if len(content.strip()) < 110:
        blank_pages.append(number)
    for block in page.get_text('blocks'):
        if block[6] == 0 and (block[0] < 10 or block[2] > page.rect.width - 10):
            overflows.append(number)
assert not errors, errors
assert not blank_pages, blank_pages
assert not overflows, overflows
result = {
    'status': 'passed',
    'word_document': path.name,
    'word_bytes': path.stat().st_size,
    'pdf_pages': len(pdf),
    'catalogs': 25,
    'standalone_html_pages': 51,
    'route_coverage': '50 of 50 list/add routes plus the main page',
    'template_rows': 12,
    'embedded_screenshots': len(word.inline_shapes),
    'source_excerpts': len(manifest['excerpts']),
    'source_files_sha256_checked': len(manifest['source_sha256']),
    'field_errors': errors,
    'blank_pages': blank_pages,
    'text_outside_page': overflows,
    'limitations': ['No live write operations performed', 'Server build identity not established',
                    'Applicant must confirm author/legal/size/completion data'],
}
(OUT / 'qa' / 'verification_result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
