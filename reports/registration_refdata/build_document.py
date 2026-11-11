from pathlib import Path
from functools import lru_cache
from runpy import run_path
import ast
import hashlib
import json
import re

from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent
DATA = json.loads((OUT / 'inventory.json').read_text(encoding='utf-8'))
DESCRIPTIONS = json.loads((OUT / 'page_descriptions.json').read_text(encoding='utf-8'))
ORDER = list(DESCRIPTIONS)
DATA.sort(key=lambda item: ORDER.index(item['key']))
SOURCES = {}
EXCERPTS = []


def typography(text):
    return str(text).replace('\u0451', '\u0435').replace('\u0401', '\u0415').replace('\u2014', '\u2013')


@lru_cache(maxsize=None)
def source(path):
    raw = (ROOT / path).read_bytes()
    SOURCES[path] = hashlib.sha256(raw).hexdigest()
    return raw.decode('utf-8-sig').splitlines()


@lru_cache(maxsize=None)
def tree(path):
    return ast.parse('\n'.join(source(path)))


def function(path, name):
    return next(node for node in tree(path).body if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name == name)


def start(node):
    return min([node.lineno] + [d.lineno for d in getattr(node, 'decorator_list', [])])


doc = Document()
sec = doc.sections[0]
sec.page_width = Cm(21)
sec.page_height = Cm(29.7)
sec.top_margin = Cm(2)
sec.bottom_margin = Cm(1.8)
sec.left_margin = Cm(2.2)
sec.right_margin = Cm(1.8)
sec.header_distance = Cm(.8)
sec.footer_distance = Cm(.8)
normal = doc.styles['Normal']
normal.font.name = 'Times New Roman'
normal.font.size = Pt(11)
normal.paragraph_format.space_after = Pt(6)
normal.paragraph_format.line_spacing = 1.08
for name, size in [('Title', 22), ('Heading 1', 16), ('Heading 2', 13), ('Heading 3', 11)]:
    style = doc.styles[name]
    style.font.name = 'Times New Roman'
    style.font.size = Pt(size)
    style.font.color.rgb = RGBColor.from_string('17365D')
    style.paragraph_format.keep_with_next = True
code_style = doc.styles.add_style('SourceCode', 1)
code_style.font.name = 'Consolas'
code_style.font.size = Pt(8)
code_style.paragraph_format.space_after = Pt(0)
code_style.paragraph_format.line_spacing = 1
code_style.paragraph_format.left_indent = Cm(.15)
caption_style = doc.styles['Caption']
caption_style.font.name = 'Times New Roman'
caption_style.font.size = Pt(9)
caption_style.font.color.rgb = RGBColor.from_string('595959')
header = sec.header.paragraphs[0]
header.text = 'АРМ | Модуль «Справочники» | Материалы для государственной регистрации'
header.style = 'Caption'
footer = sec.footer.paragraphs[0]
footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
footer.add_run('Страница ')
field = OxmlElement('w:fldSimple')
field.set(qn('w:instr'), 'PAGE')
footer._p.append(field)
doc.core_properties.title = 'АРМ. Описание модуля «Справочники» для государственной регистрации'
doc.core_properties.subject = 'Описание функций, фрагменты исходного текста и экранные формы'
doc.core_properties.author = ''
doc.core_properties.keywords = 'АРМ, Справочники, refdata, государственная регистрация'


def p(text='', style=None):
    return doc.add_paragraph(typography(text), style)


def h(text, level=1):
    return doc.add_heading(typography(text), level)


def table(headers, rows, widths=None):
    result = doc.add_table(rows=1, cols=len(headers))
    result.style = 'Table Grid'
    for cell, text in zip(result.rows[0].cells, headers):
        cell.text = typography(text)
        for run in cell.paragraphs[0].runs:
            run.bold = True
        shade = OxmlElement('w:shd')
        shade.set(qn('w:fill'), 'E8EEF5')
        cell._tc.get_or_add_tcPr().append(shade)
    repeat = OxmlElement('w:tblHeader')
    result.rows[0]._tr.get_or_add_trPr().append(repeat)
    for row in rows:
        cells = result.add_row().cells
        for cell, text in zip(cells, row):
            cell.text = typography(text)
    for row in result.rows:
        for index, cell in enumerate(row.cells):
            if widths:
                cell.width = Cm(widths[index])
            for para in cell.paragraphs:
                para.paragraph_format.space_after = Pt(3)
                para.paragraph_format.line_spacing = 1
                for run in para.runs:
                    run.font.size = Pt(9)
    p()
    return result


def excerpt(path, first, last, label):
    lines = source(path)
    last = min(last, len(lines))
    if path.endswith('.py'):
        boundaries = [node.end_lineno for node in ast.walk(tree(path))
                      if isinstance(node, (ast.Assign, ast.Expr, ast.Return, ast.Constant))
                      and hasattr(node, 'lineno') and node.lineno >= first
                      and node.lineno <= last < node.end_lineno <= last + 12]
        if boundaries:
            last = max(boundaries)
    label_paragraph = p(f'{label}. Источник: {path}, строки {first}–{last}.', 'Caption')
    label_paragraph.paragraph_format.keep_with_next = True
    for index in range(first - 1, last):
        para = p(f'{index + 1:>4}  {lines[index]}', 'SourceCode')
        para.paragraph_format.keep_with_next = index < last - 1
        shade = OxmlElement('w:shd')
        shade.set(qn('w:fill'), 'F3F5F7')
        para._p.get_or_add_pPr().append(shade)
    p()
    EXCERPTS.append({'path': path, 'first': first, 'last': last, 'label': label})


def node_excerpt(path, node, label, limit=22):
    excerpt(path, start(node), min(node.end_lineno, start(node) + limit - 1), label)


def around(path, node, predicate, label, before=2, after=5):
    hits = [child for child in ast.walk(node) if predicate(child)]
    if hits:
        target = min(hits, key=lambda child: child.lineno)
        excerpt(path, max(node.lineno, target.lineno - before), min(node.end_lineno, target.end_lineno + after), label)
        return True
    return False


figure_number = 0


def picture(filename, title, crop=True):
    global figure_number
    path = OUT / 'screenshots' / filename
    image = Image.open(path)
    if crop:
        # Exclude the account name in the common navigation header.
        bottom = image.height if filename == '01_refdata.png' else min(image.height, 950)
        image = image.crop((0, 135, image.width, bottom))
    display_path = OUT / 'screenshots' / ('document_' + filename)
    image.save(display_path)
    width = min(17, 20.5 * image.width / image.height)
    para = p()
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para.add_run().add_picture(str(display_path), width=Cm(width))
    para.paragraph_format.keep_with_next = True
    figure_number += 1
    p(f'Рисунок {figure_number}. {title}. Действующий сайт, 29.10.2026. Показан фрагмент экранной формы.', 'Caption')


APP_FILES = [(path.as_posix(), path.read_text(encoding='utf-8-sig').splitlines())
             for path in (ROOT / 'app').rglob('*.py') if '__pycache__' not in path.parts]
APP_FILES = [(str(Path(path).relative_to(ROOT)).replace('\\', '/'), lines) for path, lines in APP_FILES]


def consumers(class_name):
    found = []
    token = re.compile(r'\b' + class_name + r'\b')
    for path, lines in APP_FILES:
        if path.startswith(('app/refdata/', 'app/common/')):
            continue
        for index, line in enumerate(lines, 1):
            if token.search(line) and not line.strip().startswith('#'):
                found.append((path, index, line.strip()))
                break
    selected = []
    modules = set()
    for item in sorted(found, key=lambda entry: ('/models/' not in entry[0], entry[0])):
        module = item[0].split('/')[1]
        if module not in modules:
            selected.append(item)
            modules.add(module)
    for item in found:
        if len(selected) >= 5:
            break
        if item not in selected:
            selected.append(item)
    return selected[:5]


def model_class(item):
    return next(node for node in tree(item['model']).body if isinstance(node, ast.ClassDef))


def assignments(node):
    return [child for child in node.body if isinstance(child, ast.Assign)]


def field_name(node):
    return ast.unparse(node.targets[0])


def form_info(route_path, add_node):
    form_names = [child.func.id for child in ast.walk(add_node) if isinstance(child, ast.Call)
                  and isinstance(child.func, ast.Name) and child.func.id.startswith('Add') and child.func.id.endswith('Form')]
    if not form_names:
        return None, None
    name = form_names[0]
    imports = [node for node in tree(route_path).body if isinstance(node, ast.ImportFrom) and node.module
               and any(alias.name == name for alias in node.names)]
    if not imports:
        return None, None
    path = imports[0].module.replace('.', '/') + '.py'
    return path, function(path, name)


p('МАТЕРИАЛЫ ДЛЯ ГОСУДАРСТВЕННОЙ РЕГИСТРАЦИИ ПРОГРАММЫ ДЛЯ ЭВМ', 'Subtitle')
h('АРМ\nМодуль «Справочники»', 0)
p('Описание функциональных возможностей, фрагменты исходного текста и экранные формы', 'Subtitle')
p('Адрес модуля: http://msk-arm-gs01.ntcees.ru/refdata/')
p('Дата подготовки материалов: 29 октября 2026 года')
p('Состав: главная страница, 25 страниц списков, 25 форм добавления, служебные операции и взаимодействия с другими модулями.')
p('Документ подготовлен как отдельный файл, предусмотренный пунктом «Исходный текст программы (листинг)» шаблона «Сведения для регистрации программы». Приведены фрагменты, а не полный исходный текст программы.')
p('Основание описания: текущие исходные файлы рабочего проекта и экранные формы действующего сайта. Номер релиза серверного приложения отдельно не устанавливался: совпадение серверной сборки со всеми локальными исходными файлами не утверждается.')
doc.add_page_break()
p('Содержание', 'Title')
toc = OxmlElement('w:fldSimple')
toc.set(qn('w:instr'), 'TOC \\o "1-2" \\h \\z \\u')
doc.add_paragraph()._p.append(toc)
doc.add_page_break()

h('1. Сведения по форме предоставленного шаблона')
abstract = ('Модуль «Справочники» программы АРМ предназначен для централизованного ведения нормативно-справочной информации, '
            'используемой при планировании развития электроэнергетики. Обеспечивает ведение административных территорий, '
            'энергосистем и энергозон, компаний, топлива, типов станций, агрегатов, групп оборудования, технологий, видов затрат и ВЭД. '
            'Реализует поиск, фильтрацию, сортировку, постраничный просмотр, табличное редактирование, добавление и удаление записей. '
            'Для предусмотренных маршрутов поддерживаются импорт и экспорт Excel. Управляет текущим годом, признаками годов и периодами планирования. '
            'Работает в контексте выбранной версии БД; для поддерживаемых справочников предусмотрено изменение во всех версиях по ref_uuid. '
            'Предоставляет единые классификаторы модулям генерации, топлива, экономики, электропотребления, потребности в мощности, '
            'энергетических балансов, экологии и рациональной структуры. Доступ осуществляется через веб-интерфейс после аутентификации.')
source_template = Document(OUT / 'template_source.docx')
labels = [row.cells[1].text for row in source_template.tables[0].rows]
unknown = 'Заполняется заявителем: сведения не предоставлены.'
values = [
    'Программа: АРМ (обозначение, предоставленное заявителем). Полное регистрационное наименование подлежит уточнению. Описываемая часть: модуль «Справочники» (refdata).',
    abstract,
    'Клиент-серверная веб-система. Сервер и клиентские персональные компьютеры; работа пользователя через веб-браузер. Точная аппаратная конфигурация заявляемого экземпляра подлежит уточнению.',
    'Python; JavaScript; шаблоны HTML/Jinja2 и CSS. Доступ к реляционным данным через SQLAlchemy (СУБД PostgreSQL).',
    'В документации проекта описано серверное развертывание на Astra Linux 1.8.4. Текущий рабочий каталог находится в среде Windows. ОС и версия заявляемого экземпляра подтверждаются заявителем.',
    'Объем всей регистрируемой программы и состав поставки указываются заявителем. Размер выборки исходных файлов этого описания не является объемом программы.',
    'Дата окончательного завершения программы указывается заявителем. 29.10.2026 – дата подготовки описания, не подтверждение завершения разработки.',
    unknown,
    unknown,
    'Авторский вклад и доли определяются заявителем. Документ описывает реализацию модуля, но не устанавливает авторство конкретных лиц.',
    'Фрагменты исходного текста приведены в разделах 2–6, с указанием файлов и строк; экранные формы включены по месту описания. Представлены фрагменты, не полный текст.',
    unknown,
]
table(['№', 'Сведения по шаблону', 'Содержание для модуля «Справочники»'], [(str(i), label, value) for i, (label, value) in enumerate(zip(labels, values), 1)], [.7, 5.5, 10.8])
p('Сведения об авторах, их персональных данных, контактах, окончательном названии, объеме и дате завершения не определяются по имени пользователя в интерфейсе или по дате изменения файлов. Вопрос о включении экранных форм в состав охраняемых материалов решается заявителем с учетом прав на используемые элементы интерфейса.')

h('2. Назначение и архитектура модуля')
p(abstract)
h('2.1. Слои реализации', 2)
table(['Слой', 'Реализация и роль'], [
    ('Модели', 'SQLAlchemy-модели app/refdata/models: таблицы классификаторов, внешние ключи, ограничения уникальности, привязка к версии БД и устойчивый ref_uuid.'),
    ('Маршруты', 'Flask Blueprint refdata_bp; обработка GET/POST, получение параметров формы, вызов сервисов, flash-сообщения, перенаправление или render_template.'),
    ('Сервисы', 'app/refdata/services: выборка, фильтры, валидация, изменение данных, импорт/экспорт и синхронизация между версиями.'),
    ('Формы', 'WTForms-классы app/refdata/forms: поля, подписи и валидаторы форм фильтрации и добавления.'),
    ('Представление', 'Jinja2/HTML app/templates/refdata, общий base.html, клиентские скрипты для таблиц, поиска и иерархии топлива.'),
    ('Общие подсистемы', 'Версии БД, аутентификация и права, журналирование, кэш вариантов выбора, транзакции и разрешение внешних ключей.')])
p('Основной поток просмотра: браузер → GET-маршрут → сервис выборки с контекстом версии → SQLAlchemy/БД → пагинация и варианты выбора → шаблон Jinja2 → HTML. Поток изменения: POST → чтение и проверка значений → сервис изменения → проверка зависимостей и сохранение → сообщение → перенаправление на список.')
excerpt('app/refdata/routes/__init__.py', 1, 18, 'Регистрация Blueprint и маршрутов')
h('2.2. Версии БД и межверсионная идентичность', 2)
p('Записи классификаторов имеют database_version_id. Первичный ключ id идентифицирует строку. У справочников с RefdataUuidMixin поле ref_uuid позволяет сопоставить логически одну и ту же запись в разных версиях. Числовой id связанной записи нельзя безусловно копировать в другую версию: для межверсионной операции используется разрешение внешнего ключа по ref_uuid.')
node_excerpt('app/refdata/services/refdata_all_versions_common.py', function('app/refdata/services/refdata_all_versions_common.py', 'fk_id_for_version'), 'Разрешение связей между версиями', 22)
p('Операции с признаком all_versions=1 вызываются только там, где они реализованы в маршруте и сервисе. Для справочника годов такой режим не предусмотрен. Проверки has_admin и is_admin различаются: конкретный маршрут может требовать общие административные полномочия либо именно роль admin. Документ не приравнивает эти признаки.')
node_excerpt('app/refdata/routes/refdata_all_versions_guard.py', function('app/refdata/routes/refdata_all_versions_guard.py', 'block_all_versions_without_admin'), 'Серверная проверка межверсионной операции', 18)
h('2.3. Общие правила обработки и ограничения', 2)
p('Большинство списков совмещает просмотр и изменение: GET получает фильтры, сортировку и номер страницы, POST передает массивы идентификаторов и значений строк. Удаление обычно задается флажками и обрабатывается при отправке формы. Фактический результат зависит от проверок сервиса, ограничений БД и наличия зависимых записей; возможность безусловного удаления не заявляется.')
p('Наличие login_required означает требование входа в систему, но не доказывает отдельного административного ограничения для каждой операции. Для годов предусмотрен has_admin_required; изменение текущего года требует roles_required(["admin"]). Видимость кнопки в шаблоне и серверная проверка прав описываются раздельно.')
p('Сохранение выполняется транзакционными средствами проекта. В сервисах применяются commit/rollback и общий _commit_with_retry; отдельные операции используют дополнительную обработку конфликтов и ограничений целостности. Изменения и ошибки регистрируются через log_to_db. Журналирование не является отдельной пользовательской страницей справочника.')

h('3. Главная страница и периоды планирования')
p('Адрес: GET /refdata/. Страница предоставляет навигацию по группам справочников и показывает текущий год, период СиПР и горизонт Генеральной схемы. Текущий год выбирается из справочных годов выбранной версии. При отсутствии выбранной версии маршрут передает нулевые значения и пустой список вариантов выбора.')
p('Для текущего года 2025 на действующем сайте показаны СиПР 2026–2031 и Генеральная схема 2026–2042. Это значения конкретного состояния данных, а не постоянные параметры программы.')
picture('01_refdata.png', 'Главная страница модуля «Справочники»')
h('3.1. Модели и маршрут главной страницы', 2)
p('Используются Year (календарный год и его признак), YearFeature (факт, текущий/оценка, план), YearService (границы СиПР и даты), DatabaseVersion (контекст выбранной версии).')
node_excerpt('app/refdata/models/years/year_service_model.py', function('app/refdata/models/years/year_service_model.py', 'YearService'), 'Модель параметров периода', 22)
node_excerpt('app/refdata/routes/refdata_routes.py', function('app/refdata/routes/refdata_routes.py', 'refdata'), 'Маршрут главной страницы', 26)
h('3.2. Изменение текущего года', 2)
p('POST /refdata/update_current_year проверяет роль admin, выбранную версию и наличие года в get_reference_years(). Сервис update_current_year проставляет признаки: годы меньше выбранного – «факт», равный – «текущий (оценка)», большие – «план». Границы СиПР сохраняются как current_year + 1 и current_year + 6. После сохранения очищаются связанные кэши годов.')
node_excerpt('app/refdata/routes/refdata_routes.py', function('app/refdata/routes/refdata_routes.py', 'update_current_year_refdata'), 'Проверки маршрута изменения года', 23)
excerpt('app/refdata/services/year_management_services.py', 156, 188, 'Изменение признаков годов и периода СиПР')
p('Горизонт Генеральной схемы определяется по шестилетнему циклу разработки, начиная с 2024 года, на 18 лет. Для current_year < 2024 или отсутствующего года конец не определяется; для 2024–2029 возвращается 2042, для 2030–2035 – 2048. Начальная граница в шаблоне выводится из sipr_start.')
node_excerpt('app/refdata/services/year_management_services.py', function('app/refdata/services/year_management_services.py', 'get_general_scheme_end_year'), 'Правило горизонта Генеральной схемы', 10)
excerpt('app/templates/refdata/refdata.html', 17, 35, 'HTML выбора текущего года')
excerpt('app/templates/refdata/refdata.html', 46, 55, 'HTML периода Генеральной схемы')
h('3.3. Служебные операции периодов и взаимодействия', 2)
table(['Метод и адрес', 'Назначение'], [
    ('POST /refdata/update_sipr_dates', 'Сохранение дат СиПР через HTML-маршрут; отдельной формы на текущей главной странице нет.'),
    ('GET /refdata/api/current_year_info', 'JSON-информация о годах текущей версии; без выбранной версии возвращается набор нулевых значений.'),
    ('POST /refdata/api/update_current_year', 'Изменение текущего года через JSON. Маршрут проверяет диапазон 2000–2100, в отличие от HTML-маршрута с проверкой get_reference_years().'),
    ('POST /refdata/api/update_sipr_years', 'Изменение начала и конца СиПР через JSON, с проверками маршрута и сервиса.'),
    ('POST /refdata/api/update_sipr_dates', 'Изменение дат СиПР через JSON.')])
p('Данные о периодах передаются общим сервисам годов и далее используются в годовых фильтрах и расчетных представлениях. Смена текущего года изменяет классификацию временной оси; она не означает автоматического выполнения всех расчетов АРМ. Сервисные адреса возвращают JSON либо перенаправление и не являются дополнительными самостоятельными HTML-страницами.')

h('4. Страницы справочников и формы добавления')
p('Ниже описаны все 25 справочников, доступных из навигации модуля, включая административный справочник годов. Для каждого отдельно рассматриваются список и форма добавления. Технические адреса приведены с префиксом /refdata. Номера строк соответствуют файлам рабочей копии на дату подготовки. Листинги фрагментарные: промежуточные части функций не выдаются за полный исполняемый модуль. В русскоязычном тексте листингов нормализована типографика.')

page_records = []
for number, item in enumerate(DATA, 1):
    key = item['key']
    title, description, interaction = DESCRIPTIONS[key]
    route_path, service_path, model_path = item['route'], item['service'], item['model']
    main = next(entry for entry in item['functions'] if entry['name'].endswith('_list'))
    add = next(entry for entry in item['functions'] if entry['name'].startswith('add_'))
    main_node, add_node = function(route_path, main['name']), function(route_path, add['name'])
    cls = model_class(item)
    model_fields = assignments(cls)
    h(f'4.{number}. {title}', 2)
    h(f'4.{number}.1. Страница списка', 3)
    p(f'Адрес: {", ".join(main["methods"])} /refdata{main["url"]}. Обработчик: {main["name"]}().')
    p(description)
    # Read the actual field controls rather than assuming each model column is editable.
    template_path = 'app/templates/' + main['templates'][0]
    template = '\n'.join(source(template_path))
    controls = list(dict.fromkeys(re.findall(r'name=[\"\x27]([^\"\x27]+)[\"\x27]', template)))
    controls = [value for value in controls if '{{' not in value and value not in ['csrf_token']]
    p('Поля и параметры HTML-формы: ' + ', '.join(controls) + '.')
    p('Обработка: маршрут получает параметры отображения, при POST читает изменяемые строки и флажки удаления, вызывает сервисы и возвращает пользователя к списку с параметрами просмотра. Для обычного просмотра строится выборка и передается в шаблон вместе с пагинацией и вариантами выбора связанных справочников.')
    if key == 'years':
        p('Доступ к списку, добавлению и экспорту годов ограничен has_admin_required. Межверсионных кнопок у этого справочника нет.')
    if key in ['years', 'regional_district', 'fuel', 'equipment_group']:
        picture({'years': '07_years.png', 'regional_district': '02_regional_district.png', 'fuel': '04_fuel.png', 'equipment_group': '06_equipment_group.png'}[key], title)
    p(f'Модель: {cls.name}. Поля SQLAlchemy: ' + ', '.join(field_name(node) for node in model_fields if not field_name(node).startswith('__')) + '.')
    excerpt(model_path, cls.lineno, min(cls.end_lineno, cls.lineno + 18), 'Модель данных – фрагмент объявления')
    relations = [node for node in model_fields if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == 'relationship']
    if relations and relations[0].lineno > cls.lineno + 18:
        node_excerpt(model_path, relations[0], 'Связь модели с другой сущностью', 12)
    node_excerpt(route_path, main_node, 'Маршрут списка – вход и параметры', 16)
    around(route_path, main_node, lambda node: isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id.startswith('update_') and node.func.id.endswith('_service'), 'Маршрут списка – передача изменений сервису', 2, 3)
    getters = [node for node in tree(service_path).body if isinstance(node, ast.FunctionDef) and node.name.startswith('get_') and node.name.endswith('_list')]
    if getters:
        node_excerpt(service_path, getters[0], 'Сервис списка – выборка и пагинация', 22)
    updates = [node for node in tree(service_path).body if isinstance(node, ast.FunctionDef) and node.name.startswith('update_') and '_all_versions_' not in node.name]
    if updates:
        around(service_path, updates[0], lambda node: isinstance(node, ast.Call) and ((isinstance(node.func, ast.Attribute) and node.func.attr == 'commit') or (isinstance(node.func, ast.Name) and node.func.id == '_commit_with_retry')), 'Сервис изменения – сохранение и журналирование', 4, 5)
    # A real editable field is more informative than the template title or base inheritance.
    html_lines = source(template_path)
    anchor = next((index for index, line in enumerate(html_lines, 1) if '<input' in line and 'type="text"' in line), None)
    if anchor is None:
        anchor = next((index for index, line in enumerate(html_lines, 1) if '<form' in line), 1)
    excerpt(template_path, max(1, anchor - 2), min(len(html_lines), anchor + 11), 'HTML/Jinja2 списка – элементы формы')
    p('Взаимодействие с другими модулями. ' + interaction)
    refs = consumers(cls.name)
    if refs:
        p('Подтверждающие ссылки на потребителей модели:')
        for ref_path, line, text in refs:
            p(f'{ref_path}:{line} – {text}', 'Caption')
    h(f'4.{number}.2. Форма добавления', 3)
    p(f'Адрес: {", ".join(add["methods"])} /refdata{add["url"]}. Обработчик: {add["name"]}().')
    add_template_path = 'app/templates/' + add['templates'][0]
    add_template_text = '\n'.join(source(add_template_path))
    fields = list(dict.fromkeys(re.findall(r'form\.([A-Za-z_][A-Za-z_0-9]*)\(', add_template_text)))
    fields = [value for value in fields if value not in ['hidden_tag', 'submit']]
    p('Назначение: создание записи справочника «' + title + '». Вводимые поля формы: ' + ', '.join(fields) + '. Список полей формы может быть уже модели: дополнительные реквизиты изменяются на странице списка или заполняются сервисом.')
    p(f'GET создает форму и подготавливает варианты выбора. POST с валидной формой формирует данные и передает их сервису добавления. При успехе выполняется переход к списку; сообщения о результате выводятся пользователю. Кнопка отмены возвращает к списку без создания записи. Создаваемая сущность – {cls.name}, модель и ее связи приведены выше в подразделе 4.{number}.1.')
    fp, fc = form_info(route_path, add_node)
    if fp:
        fields_ast = [node for node in fc.body if isinstance(node, ast.Assign)]
        p('Поля WTForms и валидаторы: ' + '; '.join(ast.unparse(node) for node in fields_ast) + '.')
    if 'all_versions' in add_template_text:
        p('Шаблон содержит кнопку добавления во всех версиях для административного пользователя. Серверная ветвь all_versions=1 вызывает специализированную проверку доступа и межверсионный сервис; при обычном добавлении используется выбранная версия.')
    else:
        p('Отдельной кнопки добавления во всех версиях в этой форме нет.')
    # Include a compact model definition again so the add page has all four requested layers.
    first_field = next((node for node in model_fields if field_name(node) == ('number' if key == 'years' else 'name')), model_fields[0])
    node_excerpt(model_path, first_field, f'Модель добавляемого объекта {cls.name} – основной реквизит', 8)
    node_excerpt(route_path, add_node, 'Маршрут добавления – вход в форму', 13)
    around(route_path, add_node, lambda node: isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id.startswith('add_') and node.func.id.endswith('_service') and 'all_versions' not in node.func.id, 'Маршрут добавления – вызов сервиса', 5, 4)
    adds = [node for node in tree(service_path).body if isinstance(node, ast.FunctionDef) and node.name.startswith('add_') and '_all_versions_' not in node.name]
    if adds:
        insert_calls = [node for node in ast.walk(adds[0]) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == cls.name]
        if insert_calls:
            target = min(insert_calls, key=lambda node: node.lineno)
            excerpt(service_path, max(adds[0].lineno, target.lineno - 3), min(adds[0].end_lineno, target.end_lineno + 6), 'Сервис добавления – создание сущности')
        else:
            node_excerpt(service_path, adds[0], 'Сервис добавления – обработка входных данных', 19)
    add_lines = source(add_template_path)
    add_anchor = next((index for index, line in enumerate(add_lines, 1) if '<label' in line), 8)
    excerpt(add_template_path, max(1, add_anchor - 1), min(len(add_lines), add_anchor + 13), 'HTML/Jinja2 формы добавления')
    p('Взаимодействие при добавлении. ' + interaction + ' После создания запись становится доступна для выбора в зависимых формах при их следующем построении с учетом версии и используемых механизмов кэширования.')
    if key == 'regional_district':
        p('В текущей форме создания субъекта РФ вводятся наименования и ФО. Связи с энергозоной и синхронной зоной редактируются в списке; наличие этих полей в модели не означает их наличие в форме добавления.')
        picture('03_add_regional_district.png', 'Форма добавления субъекта РФ')
    h(f'4.{number}.3. Экспорт, импорт и дополнительные операции', 3)
    ops = [entry for entry in item['functions'] if entry not in [main, add]]
    table(['Адрес и метод', 'Обработчик', 'Результат'], [
        (', '.join(entry['methods']) + ' /refdata' + entry['url'], entry['name'],
         'JSON-дерево видов топлива' if entry['name'] == 'fuel_hierarchy' else
         'Файл Excel для скачивания' if entry['name'].startswith('export_') else 'Обработка загруженного файла и сообщение о результате') for entry in ops])
    imports_present = any(entry['name'].startswith('import_') for entry in ops)
    p('Отдельный маршрут импорта в этом справочнике ' + ('предусмотрен; наличие маршрута не означает наличие видимой кнопки загрузки в текущем шаблоне.' if imports_present else 'не зарегистрирован. Поддержка импорта не приписывается всем справочникам по аналогии.'))
    if key == 'fuel':
        p('Кнопка «Иерархия» открывает модальное окно на странице видов топлива, а не отдельную HTML-страницу. Дерево загружается через GET /refdata/fuel/hierarchy. Пользователь может искать по названию, коду и NazvL, раскрывать и сворачивать ветви. Сервис строит дерево текущей версии; parent_id определяет отношение родитель–потомок.')
        node_excerpt(route_path, function(route_path, 'fuel_hierarchy'), 'Маршрут JSON-дерева топлива', 21)
        node_excerpt(service_path, function(service_path, '_assert_valid_fuel_parent'), 'Проверка допустимости родительского вида топлива', 22)
        picture('05_fuel_hierarchy.png', 'Модальное окно иерархии топлива', crop=False)
    page_records.append({'key': key, 'title': title, 'list_url': '/refdata' + main['url'], 'add_url': '/refdata' + add['url'], 'model': cls.name, 'sources': [model_path, route_path, service_path, template_path, add_template_path]})

h('5. Взаимодействие с другими модулями')
p('Обмен внутри АРМ преимущественно осуществляется через общие модели и внешние ключи в одной БД, а не через переходы пользователя между страницами. Маршруты справочников вызывают собственные сервисы; расчетные модули читают соответствующие сущности напрямую либо через общие get-сервисы. REST-адреса обмена упоминаются только как подтвержденные потребители моделей, а не как самостоятельные страницы справочников.')
table(['Модуль/подсистема', 'Получаемые данные и логика связи'], [
    ('Генерирующие мощности', 'Территории, энергосистемы, компании, типы станций/агрегатов/ТЭС/ПГУ, состояния, технологии, топливо и годы. Station, Machine, PGUMachine и годовые модели хранят ссылки на классификаторы.'),
    ('Топливо', 'Единые Fuel/FuelType, типы групп оборудования и затрат, компании, территории и годы. Классификатор типа группы отделен от экземпляров топливных групп и их расчетных параметров.'),
    ('Экономика', 'Федеральные округа, ВЭД и годы для отраслевых и территориальных показателей. Используются идентификаторы ВЭД и версионные/годовые ключи.'),
    ('Электропотребление и электроемкость', 'Территориально-энергетическая иерархия, ВЭД и временная ось. Изменение привязки субъекта к энергозоне сопровождается синхронизацией агрегатов потребления через сервис.'),
    ('Потребность в мощности', 'Уровни ФО, субъект РФ, ОЭС, РЭС, энергорайон, энергоузел, тип энергосистемы, синхронная зона и энергозона. Модели параметров связывают показатели с соответствующим уровнем справочника.'),
    ('Энергетические балансы', 'Энергосистемы, территории, страны, типы станций и годы. Используются для группировки генерации, межсистемных передач и импортно-экспортных значений.'),
    ('Экология', 'Территории, энергосистемы, оборудование, топливо и годы для сопоставления исходных данных и построения расчетных представлений. Расчет выбросов не реализуется в страницах справочников.'),
    ('Рациональная структура', 'Типы технологий и групп оборудования для территориально-технологических моделей и сопоставления оборудования.'),
    ('Версии БД', 'Выбор контекста database_version_id; межверсионная идентичность ref_uuid и разрешение ссылок на записи соответствующей версии.'),
    ('Авторизация, журнал и кэши', 'flask_login/current_user и декораторы доступа; log_to_db для событий; варианты выбора и справочные get-сервисы для зависимых форм.')])
h('5.1. Пример сквозного взаимодействия: субъект РФ → энергозона → потребление', 2)
p('Пользователь изменяет энергозону субъекта в списке. POST передает energy_zone_id в сервис субъектов РФ. После изменения принадлежности сервис собирает затронутые зоны, обновляет состояние ORM-связи regional_districts и вызывает sync_energy_zone_consumption_aggregates. В результате данные территориальной привязки используются модулем электропотребления без повторного ручного ввода классификатора.')
node_excerpt('app/refdata/services/territories/regional_district_services.py', function('app/refdata/services/territories/regional_district_services.py', '_sync_energy_zone_aggregates_for_ids'), 'Вызов синхронизации модуля электропотребления', 24)
h('5.2. Пример сквозного взаимодействия: тип группы → технология → оборудование', 2)
p('Тип группы оборудования связан с TechnologyType и TechnologyAvailability. Модель Machine содержит ссылку на тип группы, а топливные модели используют тот же классификатор в собственных связях. Изменение классификационной записи влияет на последующее чтение зависимых объектов; перенос связей при объединении дубликатов реализуется специализированными сервисами. Это не равнозначно изменению индивидуальных расчетных параметров всех групп.')
node_excerpt('app/refdata/services/refdata_for_stations/technologies/equipment_group_services.py', function('app/refdata/services/refdata_for_stations/technologies/equipment_group_services.py', '_merge_equipment_group_type_into_canonical'), 'Объединение дублирующихся типов групп – фрагмент', 24)
h('5.3. Граница модуля: управление версиями БД', 2)
p('Файл app/refdata/routes/database_versions_routes.py физически расположен рядом со справочниками, но регистрирует страницы на station_bp, в пространстве адресов /generation/. Ссылка «Версии» относится к общей подсистеме версий АРМ. Ее страницы не включены в перечень HTML-страниц /refdata/: в настоящем документе описана именно логика взаимодействия с ними.')

h('6. Полнота материалов и перечень страниц')
p('Описаны 51 самостоятельная HTML-страница: главная страница плюс 25 списков и 25 форм добавления. Сортировка, поиск и пагинация не создают новых страниц по назначению: это состояния соответствующего списка. Модальное окно иерархии топлива описано отдельно внутри справочника. Экспорт, импорт и JSON API перечислены как служебные операции.')
table(['№ раздела', 'Справочник', 'Список', 'Добавление'], [(f'4.{i}', record['title'], record['list_url'], record['add_url']) for i, record in enumerate(page_records, 1)])
p('Вне перечня самостоятельных страниц: модели организаций business_unit, department, economic_region, признаки годов YearFeature, параметры YearService, коэффициенты пересчета цен и другие вспомогательные сущности, не имеющие собственной страницы в навигации /refdata. Их наличие в каталоге моделей не является основанием приписывать модулю дополнительные веб-страницы.')
h('6.1. Сведения об источниках и проверке', 2)
p('Шаблон заявки: «Сведения для регистрации программы.doc», предоставлен пользователем. Структура 12 пунктов сохранена в разделе 1; отдельные листинги и экранные формы размещены в последующих разделах, как допускает шаблон.')
p('Снимки экрана получены с действующего сайта 29.10.2026. Для печатного документа общий навигационный заголовок с именем учетной записи исключен кадрированием; длинные таблицы представлены верхним фрагментом. Изображения не являются макетами и не заменяют описание полей, скрытых горизонтальной или вертикальной прокруткой.')
p('Функциональные возможности и листинги сверены со структурой маршрутов, моделей, форм, сервисов и шаблонов текущей рабочей копии. Просмотр сайта выполнялся без отправки форм сохранения, добавления, удаления или импорта. Исполнение всех изменяющих операций на рабочей БД не проверялось и в рамках подготовки регистрационного описания не требовалось.')
p('Документ является описанием одного модуля и не заменяет окончательную заявку на регистрацию всей программы. До подачи заявитель подтверждает официальное наименование программы, авторский состав и вклад, контакты, дату завершения, объем заявляемой поставки и сведения об операционной системе.')

settings = doc.settings.element
update = OxmlElement('w:updateFields')
update.set(qn('w:val'), 'true')
settings.append(update)
path = OUT / 'АРМ_Справочники_Описание_для_госрегистрации.docx'
doc.save(path)
manifest = {'document': path.name, 'catalogs': len(DATA), 'html_pages': 1 + len(DATA) * 2,
            'figures': figure_number, 'pages': page_records, 'excerpts': EXCERPTS,
            'source_sha256': SOURCES}
(OUT / 'verification_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(path)
print('Catalogs:', len(DATA), 'HTML pages:', manifest['html_pages'], 'Figures:', figure_number, 'Excerpts:', len(EXCERPTS))
run_path(str(OUT / 'apply_report_styles.py'))
