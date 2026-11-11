from functools import lru_cache
from pathlib import Path
import ast
import hashlib
import json

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm
from PIL import Image

from page_descriptions import PAGES, ROUTES, SERVICES, MODELS, TEMPLATES

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent
TARGET = OUT / 'АРМ_Экология_Описание_для_госрегистрации.docx'
BASE = OUT / 'qa' / 'before_ecology.docx'
doc = Document(BASE)
first_module_heading = next(p for p in doc.paragraphs if p.text == '2. Назначение и архитектура модуля')
body = doc.element.body
for element in list(body)[list(body).index(first_module_heading._p):]:
    if element.tag != qn('w:sectPr'):
        body.remove(element)

# Cached TOC entries refer to the original module; keep a fresh field instead.
toc_entries = [p for p in doc.paragraphs if p.style.name.lower().startswith('toc ')]
toc = toc_entries[0]
toc.clear()
for kind in ['begin', 'separate', 'end']:
    field = OxmlElement('w:fldChar')
    field.set(qn('w:fldCharType'), kind)
    toc.add_run()._r.append(field)
    if kind == 'begin':
        instruction = OxmlElement('w:instrText')
        instruction.set(qn('xml:space'), 'preserve')
        instruction.text = ' TOC \\o "1-2" \\h \\z \\u '
        toc.add_run()._r.append(instruction)
for paragraph in toc_entries[1:]:
    body.remove(paragraph._p)
EXCERPTS = []
SOURCES = {}
FIGURES = []
CHANGES = []
BODY = '7.32 Основной текст'
TABLE = '7.32 Таблица. 13 Заголовки ГРАФ+основной части таблицы'
FIGURE = '7.32 Иллюстрация. Расположение иллюстрации'
CAPTION = '7.32 Иллюстрация. Подпись к иллюстрации'


def typography(value):
    return str(value).replace('\u0451', '\u0435').replace('\u0401', '\u0415').replace('\u2014', '\u2013')


@lru_cache(maxsize=None)
def source(path):
    raw = (ROOT / path).read_bytes()
    SOURCES[path] = hashlib.sha256(raw).hexdigest()
    return raw.decode('utf-8-sig').splitlines()


@lru_cache(maxsize=None)
def tree(path):
    return ast.parse('\n'.join(source(path)))


def node(path, name):
    return next(n for n in tree(path).body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == name)


def p(text='', style=BODY):
    return doc.add_paragraph(typography(text), style)


def h(text, level=1):
    paragraph = doc.add_heading(typography(text), level)
    paragraph._p.get_or_add_pPr().get_or_add_numPr().get_or_add_numId().val = 0
    return paragraph


def label(text):
    paragraph = p(text)
    paragraph.paragraph_format.keep_with_next = True
    for run in paragraph.runs:
        run.bold = True
    return paragraph


def table(headers, rows, weights=None):
    result = doc.add_table(rows=1, cols=len(headers))
    result.style = 'Table Grid'
    result.autofit = False
    available = doc.sections[-1].page_width - doc.sections[-1].left_margin - doc.sections[-1].right_margin
    weights = weights or [1] * len(headers)
    widths = [round(available * weight / sum(weights)) for weight in weights]
    for column, width in zip(result.columns, widths):
        column.width = width
    for cell, text in zip(result.rows[0].cells, headers):
        cell.text = typography(text)
    for values in rows:
        for cell, text in zip(result.add_row().cells, values):
            cell.text = typography(text)
    for row in result.rows:
        for cell, width in zip(row.cells, widths):
            cell.width = width
            for paragraph in cell.paragraphs:
                paragraph.style = TABLE
    for cell in result.rows[0].cells:
        for run in cell.paragraphs[0].runs:
            run.bold = True
    repeated = OxmlElement('w:tblHeader')
    result.rows[0]._tr.get_or_add_trPr().append(repeated)
    p()
    return result


def excerpt(path, first, last, title):
    lines = source(path)
    assert 1 <= first <= last <= len(lines), (path, first, last)
    if path.endswith('.py'):
        for statement in ast.walk(tree(path)):
            if isinstance(statement, ast.stmt) and first <= statement.lineno <= last < statement.end_lineno:
                if statement.end_lineno - last <= 14 and not isinstance(statement, (ast.FunctionDef, ast.ClassDef, ast.If, ast.For, ast.Try, ast.With)):
                    last = statement.end_lineno
    paragraph = p(f'{title}. Источник: {path}, строки {first}–{last}.', 'Normal')
    paragraph.paragraph_format.keep_with_next = True
    for number in range(first, last + 1):
        paragraph = p(f'{number:>4}  {lines[number - 1]}', 'SourceCode')
        paragraph.paragraph_format.keep_with_next = number < last
        shade = OxmlElement('w:shd')
        shade.set(qn('w:fill'), 'F3F5F7')
        paragraph._p.get_or_add_pPr().append(shade)
    p()
    EXCERPTS.append(dict(path=path, first=first, last=last, label=title))


def excerpt_node(path, name, title, limit=22):
    selected = node(path, name)
    first = min([selected.lineno] + [d.lineno for d in getattr(selected, 'decorator_list', [])])
    last = first
    for statement in selected.body:
        if statement.end_lineno - first + 1 > limit and last > first:
            break
        last = statement.end_lineno
        if last - first + 1 >= limit:
            break
    excerpt(path, first, last, title)


def picture(filename, title):
    image = Image.open(OUT / 'screenshots' / filename)
    bottom = image.height if filename == '01_hub.png' else min(image.height, 768)
    image = image.crop((0, 135, min(image.width, 1020), bottom))
    destination = OUT / 'screenshots' / ('document_' + filename)
    image.save(destination)
    paragraph = p(style=FIGURE)
    paragraph.add_run().add_picture(str(destination), width=Cm(min(16.5, 19 * image.width / image.height)))
    paragraph.paragraph_format.keep_with_next = True
    number = 1 + len(FIGURES)
    caption = p(f'Рисунок {number}. {title}. Действующий сайт, 29.10.2026. Показан фрагмент экранной формы.', CAPTION)
    caption._p.get_or_add_pPr().get_or_add_numPr().get_or_add_numId().val = 0
    FIGURES.append(dict(number=number, filename=filename, title=title))


def replace_paragraph(paragraph, text):
    CHANGES.append(dict(before=paragraph.text, after=typography(text)))
    paragraph.text = typography(text)


for paragraph in doc.paragraphs:
    if paragraph.text == 'АРМ\nМодуль «Справочники»':
        replace_paragraph(paragraph, 'АРМ\nМодуль «Экология»')
    elif paragraph.text.startswith('Адрес модуля:'):
        replace_paragraph(paragraph, 'Адрес модуля: http://msk-arm-gs01.ntcees.ru/ecology/')
    elif paragraph.text.startswith('Состав: главная страница, 25 страниц списков'):
        replace_paragraph(paragraph, 'Состав: 30 экранных представлений модуля «Экология», 4 скрытые совместимые вкладки, отчетные данные ПГ и ЗВ, анализ, расчеты действующих и новых ТЭС, сводные расчеты, агрегированные суммы, тексты формул и рассмотрение топливных пакетов.')

registration = doc.tables[0]
registration.cell(0, 2).text = 'Содержание для модуля «Экология»'
registration.cell(1, 2).text = 'Программа: АРМ (обозначение, предоставленное заявителем). Полное регистрационное наименование подлежит уточнению. Описываемая часть: модуль «Экология» (ecology).'
registration.cell(2, 2).text = 'Модуль «Экология» программы АРМ хранит и отображает отчетные данные ГИС ТЭК о парниковых газах и загрязняющих веществах. Поддерживает импорт и экспорт Excel, выверку параметров анализа и сопоставление с топливными и генерационными показателями. Рассчитывает выбросы действующих и новых ТЭС на основе принятых топливных данных, характеристик, коэффициентов и нормативов. Формирует сводные расчетные таблицы и агрегированные суммы отчетно-аналитического контура. Обеспечивает рассмотрение пакетов, переданных из модуля «Топливо», и редактирование текстов подсказок формул. Работает через веб-интерфейс с разграничением прав и учетом выбранной версии БД.'
registration.cell(11, 2).text = 'Фрагменты исходного текста приведены в разделах 2–12, с указанием файлов и строк; экранные формы включены по месту описания. Представлены фрагменты, не полный текст.'
for row in registration.rows:
    for cell in row.cells:
        for paragraph in cell.paragraphs:
            paragraph.style = TABLE
for run in registration.cell(0, 2).paragraphs[0].runs:
    run.bold = True

doc.core_properties.title = 'АРМ. Описание модуля «Экология» для государственной регистрации'
doc.core_properties.keywords = 'АРМ, Экология, ecology, государственная регистрация'

h('2. Модуль «Экология»: назначение и архитектура')
p('Модуль предназначен для хранения и просмотра отчетных данных о парниковых газах и загрязняющих веществах, выверки их относительно топливно-энергетических показателей, расчета выбросов действующих и новых ТЭС и подготовки сводных таблиц. Основной адрес: http://msk-arm-gs01.ntcees.ru/ecology/. В документе описывается текущая рабочая копия исходников; совпадение ее сборки с действующим сервером не установлено.')
p('Различаются два контура. Отчетно-аналитический контур использует сведения ГИС ТЭК, выверенные параметры анализа и агрегационные суммы. Расчетный контур использует принятые топливные снимки, характеристики, коэффициенты и нормативы для действующих и новых ТЭС. Итоговые суммы анализа и сводные расчетные выбросы имеют разное происхождение и не заменяют друг друга.')
h('2.1. Страницы, вкладки и границы описания', 2)
p('Описаны 30 функциональных экранных представлений: главная страница, 2 отчета, 4 листа анализа, 10 вкладок действующих ТЭС, 3 вкладки новых ТЭС, 4 сводные вкладки, 4 агрегированных листа, редактор подсказок и рассмотрение топливного пакета. Дополнительно перечислены 4 скрытые совместимые вкладки сводного расчета. Это не 30 отдельных HTML-шаблонов: используются 7 полноценных шаблонов с общими включаемыми фрагментами. Территория, год, мощностная категория, фильтр и пагинация являются параметрами представления. Все 34 объявления маршрутов, включая служебные операции и варианты адресов со слешем, перечислены в разделе 12.')
p('На каждой странице приведены назначение, доступные действия, источники данных, связи с другими модулями и фрагменты реализации с точными путями и строками. Для страниц без отдельной модели указано отсутствие собственного хранилища. Фрагменты являются выборочным листингом, а не полным исходным текстом модуля.')
h('2.2. Программные слои и модели данных', 2)
p('Flask Blueprint ecology_bp связывает маршруты с сервисами. ORM-модели SQLAlchemy хранят первичные и выверенные данные, а шаблоны Jinja и JavaScript выводят таблицы, фильтры, подсказки и интерактивный ввод. Для исходных числовых полей используется Numeric(36, 16); расчетные сервисы применяют Decimal и отдельные правила отображения. Округление для вывода не следует трактовать как изменение сохраненной точности.')
model_rows = []
for path in sorted((ROOT / 'app/ecology/models').rglob('*.py')):
    relative = path.relative_to(ROOT).as_posix()
    for selected in tree(relative).body:
        if not isinstance(selected, ast.ClassDef):
            continue
        assignments = {n.targets[0].id: n for n in selected.body if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)}
        table_name = ast.literal_eval(assignments['__tablename__'].value)
        keys = [key for key in ['database_version_id', 'sheet_slug', 'station_numb', 'equipment_group_id', 'year_number', 'territory_slug', 'affiliation', 'fuel_key', 'capacity_class', 'kind', 'row_key', 'scope', 'status', 'formula_key'] if key in assignments]
        model_rows.append((selected.name, table_name, ', '.join(keys)))
table(['Модель', 'Таблица', 'Ключи и разрезы'], model_rows, [1.1, 1.5, 1.5])
p('Отчетные PGReportGisTek/ZVReportGisTek привязаны к коду группы оборудования, году и версии БД; отдельный equipment_group_id обеспечивает связь с группой «Топлива». Код numb не уникален сам по себе, поэтому версия и разрешение связи существенны. PGParamCalc/ZVParamCalc дополнительно разделены по sheet_slug. Составной внешний ключ года учитывает Year.number и Year.database_version_id. EcologyFuelSnapshot уникален по версии, году и scope. OperatingTesFormulaText, в отличие от числовых моделей, не имеет поля database_version_id: это общее хранилище текстов подсказок.')
excerpt(MODELS+'pg_report_gis_tek_model.py', 19, 37, 'Модель отчетных ПГ: уникальность и составной ключ года')
excerpt(MODELS+'pg_report_gis_tek_model.py', 90, 106, 'Модель отчетных ПГ: исходные числовые поля')
excerpt(MODELS+'zv_param_calc_model.py', 76, 95, 'Выверенные параметры анализа ЗВ: хранимые компоненты')
excerpt_node(MODELS+'fuel_exchange_model.py', 'EcologyFuelSnapshot', 'Модель принятого топливного снимка')

h('2.3. Права, версия БД и журнал', 2)
p('Все внешние маршруты защищены login_required. Для записи can_edit_ecology требует аутентификацию и признак has_admin либо роль, имя которой содержит ecology. Отдельная проверка административной роли регулирует видимость служебных идентификационных столбцов. Недостаток прав блокирует импорт, PATCH, принятие пакета и сохранение текстов на сервере, независимо от того, показана ли кнопка в HTML.')
p('Выбор версии БД используется в запросах отчетов, параметров и снимков. Передача топлива без выбранной версии завершается ошибкой. Журнал «Экология» регистрирует посещения, импорт и выгрузки, изменение значений и решения по пакетам. Дата, пользователь и контекст действия фиксируются существующими сервисами приложения; настоящее описание не подменяет эти записи.')
excerpt_node(SERVICES+'gis_tek_page_services.py', 'can_edit_ecology', 'Проверка права изменения экологических данных')
excerpt_node(SERVICES+'ecology_logging_services.py', 'log_page_visit', 'Регистрация просмотра страницы')

h('2.4. Условия получения экранных форм', 2)
p('Снимки получены 29 октября 2026 года с действующего сайта. Для четырех аналитических листов выбран 2024 год. Общая панель с именем пользователя исключена кадрированием; широкие таблицы представлены видимым фрагментом. По согласованию с пользователем страницы анализа были открыты, хотя GET может создать недостающие строки PGParamCalc/ZVParamCalc из отчетов ГИС ТЭК. В рабочей БД могли появиться такие строки; их количество отдельно не проверялось. Значения существующих показателей не редактировались, формы импорта, PATCH, сохранение подсказок и решения по пакетам не отправлялись. Посещения могут регистрироваться штатным журналом приложения.')
p('Просмотрены также главная страница, два отчета, редактор текстов, принятые топливные показатели действующих и новых ТЭС и коэффициенты. Другие страницы, GET которых вызывает ensure_default_persisted_rows или ensure_default_norm_rows, для иллюстраций не открывались. Их поведение описано по исходникам, без утверждения о проверке изменяющих операций на рабочей БД.')
excerpt(SERVICES+'operating_tes_page_services.py', 812, 818, 'Расчетный GET может сохранять недостающие значения по умолчанию')
excerpt(SERVICES+'new_tes_page_services.py', 275, 291, 'Разделение безопасного просмотра топлива и инициализации нормативов')
excerpt(SERVICES+'gis_tes_pg_from_fuel_services.py', 790, 810, 'Инициализация параметров анализа при формировании годовых строк')

GROUPS = {
    '3': '3. Главная страница и отчетные данные ГИС ТЭК',
    '4': '4. Анализ отчетных данных и сопоставление с модулем «Топливо»',
    '5': '5. Расчет по действующим ТЭС',
    '6': '6. Расчет по новым ТЭС',
    '7': '7. Сводные данные расчетов',
    '8': '8. Агрегированные суммы отчетно-аналитического контура',
    '9': '9. Тексты подсказок формул',
    '10': '10. Рассмотрение данных, переданных из модуля «Топливо»',
}
current_group = None
for record in PAGES:
    group = record['section'].split('.')[0]
    if group != current_group:
        h(GROUPS[group])
        current_group = group
        if group == '5':
            p('Территориальные разрезы обычных расчетных форм: Всего; станции отрасли; промпредприятия; ОЭС Северо-Запада, Центра, Средней Волги, Юга, Урала, Сибири и Востока; ТИТЭС Сибири и Востока; децентрализованная зона. На коэффициентах используются отдельные территориальные ключи tites-sibir, tites-vostok и decentralized-zone, а принадлежность выбирается параметром affiliation. Большинство годовых форм показывают территории столбцами, коэффициенты показывают выбранную территорию и годы столбцами.')
            excerpt(SERVICES+'operating_tes_constants.py', 20, 47, 'Каталоги территорий и принадлежностей')
        elif group == '6':
            p('Для новых ТЭС нет самостоятельной формы «Добавить станцию»: состав поступает из топливной подсистемы, а редактируются только разрешенные нормативы. Передаваемые категории определены критериями сводки «Топлива». Внутренние ключи le100/gt100 исторические; актуальная передача new_lt100/new_ge100 разделяет заполненную мощность блока n1 на менее 100 МВт и 100 МВт или более. Старый низкоуровневый помощник _capacity_class_expr использует другой порог по Nуст; эти пути не следует смешивать при описании принятых снимков.')
            excerpt(SERVICES+'fuel_summary_constants.py', 3, 14, 'Категории передачи и их сопоставление с capacity_class')
        elif group == '8':
            p('После группировки исходные абсолютные показатели суммируются, а производные коэффициенты и удельные показатели вычисляются заново на суммарной базе. Складывать готовые удельные значения станций нельзя. Представления с котельными и без котельных имеют разные исходные выборки.')
            excerpt_node(SERVICES+'gis_tes_fuel_comparison_services.py', '_sum_filled_rows', 'Суммирование с повторным вычислением производных показателей', limit=25)
    h(f"{record['section']}. {record['title']}", 2)
    p('Адрес: ' + record['url'])
    label('Функциональные возможности и действия пользователя')
    p(record['functionality'])
    label('Взаимодействие и источники данных')
    p(record['interaction'])
    for filename, title in record.get('screenshots', []):
        picture(filename, title)
    label('Элементы реализации')
    for model in record['models']:
        path = MODELS + model
        selected = next(n for n in tree(path).body if isinstance(n, ast.ClassDef))
        excerpt_node(path, selected.name, 'Модель ' + selected.name, limit=18)
    if not record['models']:
        p('Собственной модели этой страницы нет: маршрут собирает навигацию и права, не создавая отдельную таблицу показателей.')
    excerpt_node(ROUTES+record['route'][0], record['route'][1], 'Маршрут страницы', limit=21)
    excerpt_node(SERVICES+record['service'][0], record['service'][1], 'Сервис и расчетная логика', limit=23)
    excerpt(TEMPLATES+record['html'][0], record['html'][1], record['html'][2], 'HTML-шаблон экранной формы')
    for title, path, first, last in record.get('extra_sources', []):
        excerpt(path, first, last, title)

h('11. Сквозная логика и взаимодействие с другими модулями')
h('11.1. Отчет, выверенные параметры и агрегаты', 2)
p('Последовательность: пользователь выбирает версию БД и год; уполномоченный специалист загружает Excel на странице отчета; импорт разрешает код группы оборудования и год, создает или обновляет исходные строки и возвращает счетчики. Для анализа создаются только отсутствующие параметры, после чего специалист может выверять их отдельно. Лист анализа соединяет эти параметры с топливными и генерационными показателями, вычисляет разности и удельные значения. Агрегированная форма суммирует базовые величины и заново вычисляет производные показатели.')
p('Загрузка ПГ дополнительно инициирует заполнение отсутствующих параметров анализа ПГ. Для ЗВ заполнение предусмотрено при построении аналитических строк. Импорт не является безусловной заменой всех выверенных параметров: существующие строки анализа сохраняются. Пропуск неизвестного года или кода станции и отсутствие найденной группы учитываются отдельными счетчиками; отсутствие группы не следует смешивать с отсутствием кода.')
excerpt(SERVICES+'gis_tek_import_services.py', 304, 332, 'Импорт: обязательные колонки, текущая версия и индекс существующих записей')
excerpt(SERVICES+'gis_tek_import_services.py', 435, 445, 'Первичное заполнение анализа ПГ после импорта отчета')
excerpt(SERVICES+'analysis_param_services.py', 64, 88, 'Отсутствующие параметры создаются без перезаписи существующих')
excerpt_node(SERVICES+'analysis_param_services.py', 'upsert_param_values', 'Отдельное хранилище выверенных параметров', limit=28)

h('11.2. Передача топлива и расчет выбросов ТЭС', 2)
p('Последовательность: в «Топливе» собирается сводка за год и категорию; отправка создает EcologyFuelSubmission со статусом pending, не меняя содержимое уже принятого снимка. Предыдущий ожидающий пакет того же разреза получает superseded. Специалист «Экологии» сравнивает значения и принимает либо отклоняет пакет. Только accepted заменяет payload снимка выбранного разреза. Расчетные сервисы читают принятые EcologyFuelSnapshot, применяют физические характеристики, коэффициенты очистки и нормативы, затем сводят действующие и обе категории новых ТЭС.')
p('Объекты групп оборудования, их топливные параметры и дополнительные виды топлива принадлежат «Топливу». «Генерация» предоставляет связанные станции, мощность, выработку и сведения для проверки соответствия. «Справочники» задают годы, виды топлива, территориальную и энергетическую иерархию. Выбранная версия БД ограничивает предметный разрез. Журнал отражает изменения и решения, но не является источником расчетных значений.')
excerpt_node(SERVICES+'fuel_exchange_services.py', 'submit_fuel_year', 'Отправка пакета без замены принятой базы', limit=28)
excerpt_node(SERVICES+'fuel_exchange_services.py', 'review_fuel_submission', 'Акцепт или отклонение пакета', limit=30)
excerpt_node('app/fuel/routes/ecology_summary_routes.py', 'ecology_summary', 'Вход передачи из модуля «Топливо»', limit=24)

h('11.3. Формулы, единицы измерения и отсутствующие данные', 2)
p('Для действующих ТЭС перевод в натуральное топливо для золы, серы и CO использует В × 7000 / Qн. Прямой расчет CO2 использует В × KCO2; энергетический вариант дополнительно использует ТДж и т CO2/ТДж. Улавливание рассчитывается как Мотх × (1 − коэффициент). В новых ТЭС масса ЗВ = расход в тыс. т у.т. × норматив в кг/т у.т. дает тонны, а масса CO2 = расход × норматив в т/т у.т. дает тыс. т. Перед суммированием выполняется согласование единиц.')
p('Для удельных показателей важны единицы знаменателя. Расчетные ТЭС используют приведенную энергию (E + Q × 1,163) / 1000 в млрд кВт·ч; анализ отчетов использует свою функцию приведения W_en + Teplo / 859,8 × 1000 в млн кВт·ч. Эти выражения описывают текущую реализацию разных форм, а не замену одной формулы другой. Отсутствующее значение и нулевой знаменатель обрабатываются явно; знак отсутствия данных не является автоматически измеренным нулем. Документ не подтверждает научную аттестацию методики или полноту исходных данных.')
excerpt_node(SERVICES+'operating_tes_calc_services.py', 'to_natural_by_heat', 'Натуральный расход топлива по теплоте сгорания')
excerpt_node(SERVICES+'operating_tes_calc_services.py', 'apply_capture', 'Учет улавливания или подавления')
excerpt_node(SERVICES+'operating_tes_calc_services.py', 'equivalent_energy_billion_kwh', 'Приведенная энергия расчетных ТЭС')
excerpt_node(SERVICES+'gis_tes_fuel_comparison_services.py', '_brought_energy_mln_kwh', 'Приведенная энергия анализа отчетных данных')
excerpt_node(SERVICES+'gis_tes_fuel_comparison_services.py', '_safe_divide', 'Защита от отсутствующей или нулевой базы деления')
excerpt(SERVICES+'new_tes_calc_services.py', 12, 35, 'Единицы массы в расчетах новых ТЭС')

h('11.4. Обмен Excel и интерактивные действия', 2)
p('Отчеты ПГ/ЗВ имеют собственные маршруты импорта и выгрузки. Анализ экспортируется без ограничения текущей страницей (per_page=all). Выгрузка итоговых сумм учитывает выбранные уровни и период. Для действующих ТЭС и сводного расчета Excel формируется по вкладкам и годовым блокам. В текущем new_tes_routes.py отдельного маршрута выгрузки новых ТЭС нет; при описании этой страницы нельзя автоматически приписывать ей экспорт действующих ТЭС.')
p('Ввод в разрешенную числовую ячейку передает PATCH с годом, полем и ключами строки. Сервер проверяет пользователя, допустимый лист, вид поля и корректность числа; листы только для просмотра возвращают отказ. Формы решения по пакету и сохранения подсказок используют POST. Тексты подсказок не исполняются как программные формулы и не меняют расчетный алгоритм.')
excerpt_node(SERVICES+'tes_excel_export_services.py', 'build_tes_excel_stream', 'Excel: расчетные вкладки и годовые блоки', limit=33)
excerpt(TEMPLATES+'operating_tes/operating_tes_table.html', 1068, 1089, 'HTML/JavaScript: PATCH разрешенной числовой ячейки')
excerpt(TEMPLATES+'analysis/gis_tes_fuel_comparison.html', 1098, 1118, 'HTML/JavaScript: сохранение параметра анализа')
excerpt_node(ROUTES+'new_tes_routes.py', 'new_tes_update_value', 'Проверки сохранения норматива новых ТЭС', limit=29)
excerpt_node(ROUTES+'ecology_routes.py', 'operating_tes_formulas_reset', 'Сброс только текста подсказки', limit=24)

h('12. Полнота описания модуля «Экология» и источники')
h('12.1. Перечень экранных представлений', 2)
table(['Раздел', 'Представление', 'Адрес или пример'], [(x['section'], x['title'], x['url']) for x in PAGES], [.6, 1.3, 1.7])
h('12.2. Скрытые совместимые вкладки сводного расчета', 2)
legacy = [
    ('operating', 'Действующие ТЭС', 'Показывает расчет действующих ТЭС без добавления новых.'),
    ('new', 'Новые ТЭС: обе категории', 'Суммирует объемы новых ТЭС le100 и gt100 без действующих.'),
    ('new-le100', 'Новые ТЭС le100', 'Показывает отдельную категорию новых ТЭС, сопоставленную с new_lt100.'),
    ('new-gt100', 'Новые ТЭС gt100', 'Показывает отдельную категорию новых ТЭС, сопоставленную с new_ge100.'),
]
for index, (slug, title, description) in enumerate(legacy, 1):
    h(f'12.2.{index}. {title}', 3)
    p(f'Адрес: /ecology/calculation_summary/vsego/{slug}/. {description} Вкладка не выводится в основном списке CALCULATION_SUMMARY_TABS, но доступна по сохраненной ссылке. Общий маршрут calculation_summary, сервис build_calculation_summary_context и HTML operating_tes_table.html совпадают с разделом 7. Используются принятые топливные снимки, NewTesNorm и общие характеристики; отдельная модель скрытой вкладки не создается. Числовые результаты доступны для просмотра.')
excerpt(SERVICES+'calculation_summary_services.py', 16, 29, 'Основные и скрытые совместимые вкладки')
excerpt(SERVICES+'calculation_summary_services.py', 162, 196, 'Выбор источников совместимых сводных представлений')
h('12.3. Маршруты страниц и служебные операции', 2)
routes = json.loads((OUT / 'routes.json').read_text(encoding='utf-8'))
table(['Метод', 'Адрес', 'Обработчик'], [(', '.join(x['methods']), x['url'], x['function']) for x in routes], [.5, 1.7, 1.4])
p('Маршруты верхнего уровня operating_tes/, new_tes/, calculation_summary/ и totals_summary/ перенаправляют к исходному листу. Export, value, import, save и reset являются операциями существующих страниц, а не дополнительными экранными формами. Варианты totals_summary со слешем и без него ведут к одному представлению. Технические HEAD и OPTIONS Flask в число отдельных прикладных операций не включены.')
h('12.4. Проверка и ограничения', 2)
p('Описание сверено с маршрутами, моделями, сервисами, HTML и включаемыми JavaScript текущей рабочей копии. Снимки подтверждают внешний вид только просмотренных страниц и конкретного состояния БД на дату получения. Изменяющие операции и научная корректность расчетов не испытывались на рабочем сервере. При подаче заявки заявитель по-прежнему подтверждает официальное название программы, авторов, правообладателя, объем и дату завершения. Описание модуля не заполняет эти сведения автоматически.')
p('Сведения по предоставленному шаблону регистрации приведены в разделе 1, описание модуля «Экология» в разделах 2–12. Описание «Справочников» оформлено отдельным файлом. Стили основного текста, заголовков, таблиц и иллюстраций унаследованы из ранее примененного отчета «Отчет_Этап 1_АРМ_ГС_2026-НК.docx». Моноширинный SourceCode сохранен для листингов. Оглавление включает только разделы настоящего документа и обновляется средствами Word.')

doc.save(TARGET)
manifest = dict(document=TARGET.name, base_sha256=hashlib.sha256(BASE.read_bytes()).hexdigest(),
                pages=PAGES, legacy_pages=[item[0] for item in legacy], routes=routes,
                figures=FIGURES, excerpts=EXCERPTS, source_sha256=SOURCES, front_matter_changes=CHANGES)
(OUT / 'verification_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(TARGET)
print('Ecology pages:', len(PAGES), 'legacy:', len(legacy), 'routes:', len(routes), 'figures:', len(FIGURES), 'excerpts:', len(EXCERPTS))
