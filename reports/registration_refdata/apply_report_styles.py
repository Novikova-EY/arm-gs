from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

OUT = Path(__file__).parent
REFERENCE = Path('z:/НИО-10/АРМ ГС/02. Отчеты НИР/2026 год/Отчет_Этап 1_АРМ_ГС_2026-НК.docx')
TARGET = OUT / 'АРМ_Справочники_Описание_для_госрегистрации.docx'
BODY = '7.32 Основной текст'
STRUCTURAL = '7.32 ЗАГОЛОВОК СТРУКТУРНЫХ ЭЛЕМЕНТОВ (НЕ ОТОБРАЖАЕТСЯ В СОДЕРЖАНИИ)'
FIGURE = '7.32 Иллюстрация. Расположение иллюстрации'
FIGURE_CAPTION = '7.32 Иллюстрация. Подпись к иллюстрации'
TABLE = '7.32 Таблица. 13 Заголовки ГРАФ+основной части таблицы'


def content(document):
    return ([p.text for p in document.paragraphs if not p.style.name.lower().startswith('toc ')],
            [[c.text for row in t.rows for c in row.cells] for t in document.tables])


def no_numbering(paragraph):
    numbering = paragraph._p.get_or_add_pPr().get_or_add_numPr()
    numbering.get_or_add_numId().val = 0


reference_hash = hashlib.sha256(REFERENCE.read_bytes()).hexdigest()
reference = Document(REFERENCE)
document = Document(TARGET)
before = content(document)
already_applied = BODY in document.styles
paragraphs = [(p, p.style.name) for p in document.paragraphs]
backup = OUT / 'qa' / 'before_report_styles'
backup.mkdir(exist_ok=True)
for suffix in ['.docx', '.pdf']:
    original = TARGET.with_suffix(suffix)
    destination = backup / original.name
    if original.exists() and not destination.exists():
        shutil.copy2(original, destination)

code_style = deepcopy(document.styles['SourceCode'].element)
styles = document.styles.element
for child in list(styles):
    styles.remove(child)
for child in reference.styles.element:
    styles.append(deepcopy(child))
styles.append(code_style)
numbering = document.part.numbering_part.element
for child in list(numbering):
    numbering.remove(child)
for child in reference.part.numbering_part.element:
    numbering.append(deepcopy(child))

for paragraph, old_style in paragraphs:
    if old_style == 'SourceCode':
        paragraph.style = document.styles['SourceCode']
        continue
    properties = paragraph._p.get_or_add_pPr()
    for child in list(properties):
        if child.tag not in [qn('w:keepNext'), qn('w:keepLines'), qn('w:pageBreakBefore')]:
            properties.remove(child)
    for run in paragraph.runs:
        if run._r.rPr is not None:
            run._r.remove(run._r.rPr)
    if paragraph._p.xpath('.//w:drawing'):
        paragraph.style = FIGURE
    elif old_style.startswith('Heading '):
        paragraph.style = old_style
        no_numbering(paragraph)
    elif old_style in ['Title', 'Subtitle', STRUCTURAL]:
        paragraph.style = STRUCTURAL
        outline = OxmlElement('w:outlineLvl')
        outline.set(qn('w:val'), '9')
        properties.append(outline)
        paragraph.paragraph_format.page_break_before = paragraph.text == 'Содержание'
    elif old_style.lower().startswith('toc '):
        paragraph.style = old_style
    elif old_style in ['Caption', FIGURE_CAPTION] or (already_applied and old_style == 'Normal'):
        paragraph.style = FIGURE_CAPTION if paragraph.text.startswith('Рисунок ') else 'Normal'
        no_numbering(paragraph)
    else:
        paragraph.style = BODY

for table in document.tables:
    table.style = 'Table Grid'
    for row in table.rows:
        for cell in row.cells:
            cell_properties = cell._tc.get_or_add_tcPr()
            for shade in list(cell_properties.findall(qn('w:shd'))):
                cell_properties.remove(shade)
            for paragraph in cell.paragraphs:
                properties = paragraph._p.get_or_add_pPr()
                for child in list(properties):
                    properties.remove(child)
                paragraph.style = TABLE
                for run in paragraph.runs:
                    if run._r.rPr is not None:
                        run._r.remove(run._r.rPr)
    for cell in table.rows[0].cells:
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.bold = True

layout = reference.sections[-1]
for section in document.sections:
    for name in ['page_width', 'page_height', 'left_margin', 'right_margin', 'top_margin',
                 'bottom_margin', 'header_distance', 'footer_distance']:
        setattr(section, name, getattr(layout, name))
    section.different_first_page_header_footer = True
    for header in [section.header, section.first_page_header]:
        for child in list(header._element):
            header._element.remove(child)
        header._element.append(OxmlElement('w:p'))
    for footer in [section.footer, section.first_page_footer]:
        for child in list(footer._element):
            footer._element.remove(child)
        footer._element.append(OxmlElement('w:p'))
    paragraph = section.footer.paragraphs[0]
    paragraph.style = 'Normal'
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    field = OxmlElement('w:fldSimple')
    field.set(qn('w:instr'), 'PAGE')
    paragraph._p.append(field)
    available = section.page_width - section.left_margin - section.right_margin
    for shape in document.inline_shapes:
        if shape.width > available:
            shape.height = round(shape.height * available / shape.width)
            shape.width = available
    for table in document.tables:
        widths = [column.width for column in table.columns]
        scale = available / sum(widths)
        for column, width in zip(table.columns, widths):
            column.width = round(width * scale)
        for row in table.rows:
            for cell in row.cells:
                cell.width = round(cell.width * scale)

assert content(document) == before, 'Document content changed'
assert hashlib.sha256(REFERENCE.read_bytes()).hexdigest() == reference_hash
document.save(TARGET)
result = {
    'reference': str(REFERENCE),
    'reference_sha256': reference_hash,
    'document': TARGET.name,
    'body_style': BODY,
    'table_style': TABLE,
    'figure_style': FIGURE,
    'figure_caption_style': FIGURE_CAPTION,
    'headings': ['Heading 1', 'Heading 2', 'Heading 3'],
    'code_style': 'SourceCode retained for monospaced source listings; report has no code style',
    'content_unchanged': True,
    'style_definitions_imported': len(reference.styles),
}
(OUT / 'qa' / 'report_styles_applied.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
