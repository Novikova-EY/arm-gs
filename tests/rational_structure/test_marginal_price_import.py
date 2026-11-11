import hashlib
import re
from io import BytesIO

import pytest
from flask.templating import render_template
from openpyxl import load_workbook
from sqlalchemy.exc import SQLAlchemyError

from test_calculation_pages import calculation_database, price_bytes
from test_technical_characteristics import database, http_client
from app.extensions import db
from app.rational_structure.models import CalculationWorkbook
from app.rational_structure.routes import marginal_price_routes as routes
from app.rational_structure.services.marginal_price_services import (
    TERRITORY_SHEETS, import_marginal_price_workbook, read_marginal_price_workbook,
)


def changed_book(*, year=2030, missing_sheet=False):
    book = load_workbook(BytesIO(price_bytes()))
    for sheet in book:
        sheet['A5'] = year
        sheet['C5'] = 0
        sheet['D5'] = 'Новая станция'
    if missing_sheet:
        del book['Восток']
    stream = BytesIO()
    book.save(stream)
    book.close()
    return stream.getvalue()


def test_import_persists_all_territories_and_replaces_only_selected_version(calculation_database):
    raw = changed_book()
    counts = import_marginal_price_workbook(raw, 2, 'tester', 'Первый.xlsx')
    assert counts == {'territories': 5, 'rows': 15, 'errors': 0}
    db.session.remove()
    row = db.session.scalar(db.select(CalculationWorkbook).filter_by(database_version_id=2))
    first_id = row.id
    assert row.source_sha256 == hashlib.sha256(raw).hexdigest()
    assert row.source_filename == 'Первый.xlsx'
    assert set(row.data) == set(TERRITORY_SHEETS)
    assert row.data['east']['rows'][0]['values']['C'] == 0
    assert row.data['east']['rows'][1]['values']['A'] == 2030
    import_marginal_price_workbook(price_bytes(), 2, 'tester', 'Второй.xlsx')
    db.session.remove()
    records = list(db.session.scalars(db.select(CalculationWorkbook)))
    assert len(records) == 3
    row = next(record for record in records if record.database_version_id == 2)
    assert row.id == first_id
    assert row.source_filename == 'Второй.xlsx'
    assert row.data['east']['rows'][0]['values']['C'] == '1.23456789'
    assert all(record.source_filename == 'source.xlsx' for record in records if record.database_version_id == 1)


@pytest.mark.parametrize('version_id', [None, 999])
def test_import_requires_existing_version(calculation_database, version_id):
    with pytest.raises(ValueError, match='верси'):
        import_marginal_price_workbook(price_bytes(), version_id, 'tester', 'bad.xlsx')
    assert db.session.query(CalculationWorkbook).count() == 2


@pytest.mark.parametrize('raw', [b'bad zip', changed_book(missing_sheet=True), changed_book(year='не год')])
def test_invalid_import_keeps_previous_data(calculation_database, raw):
    with pytest.raises(ValueError):
        import_marginal_price_workbook(raw, 1, 'tester', 'bad.xlsx')
    db.session.expire_all()
    row = db.session.scalar(db.select(CalculationWorkbook).filter_by(database_version_id=1, kind='marginal_price'))
    assert row.source_filename == 'source.xlsx'
    assert row.data == read_marginal_price_workbook(price_bytes())


def test_import_preserves_formulas_and_excel_errors(calculation_database):
    book = load_workbook(BytesIO(price_bytes()))
    for sheet in book:
        sheet['C5'] = '=1+2'
        sheet['C6'] = '#N/A'
    stream = BytesIO()
    book.save(stream)
    book.close()
    counts = import_marginal_price_workbook(stream.getvalue(), 1, 'tester', 'formulas.xlsx')
    assert counts['errors'] == 10
    db.session.remove()
    row = db.session.scalar(db.select(CalculationWorkbook).filter_by(kind='marginal_price'))
    for table in row.data.values():
        first, second = table['rows'][:2]
        assert first['formulas']['C'] == '=1+2'
        assert first['values']['C'] is None
        assert first['errors'] == ['C']
        assert second['values']['C'] == '#N/A'
        assert second['errors'] == ['C']


def test_database_failure_rolls_back_replacement(calculation_database, monkeypatch):
    def fail_commit():
        raise SQLAlchemyError('failure')

    with monkeypatch.context() as patch:
        patch.setattr(db.session, 'commit', fail_commit)
        with pytest.raises(SQLAlchemyError):
            import_marginal_price_workbook(changed_book(), 1, 'tester', 'bad.xlsx')
    row = db.session.scalar(db.select(CalculationWorkbook).filter_by(database_version_id=1, kind='marginal_price'))
    assert row.source_filename == 'source.xlsx'
    assert row.data == read_marginal_price_workbook(price_bytes())


@pytest.fixture
def import_client(calculation_database, http_client, monkeypatch):
    monkeypatch.setattr(routes, 'render_template', render_template)
    monkeypatch.setattr(routes, 'log_to_db', lambda *args, **kwargs: None)
    return http_client


def csrf_token(client):
    html = client.get('/rational_structure/marginal_price').get_data(as_text=True)
    return re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html).group(1)


def test_upload_form_available_without_existing_workbook(import_client):
    client, user = import_client
    db.session.query(CalculationWorkbook).filter_by(kind='marginal_price').delete()
    db.session.commit()
    html = client.get('/rational_structure/marginal_price').get_data(as_text=True)
    assert 'multipart/form-data' in html
    assert '📁 Импорт из Excel' in html
    assert 'Загрузить в выбранную версию' in html
    assert 'aria-disabled="true"' in html
    assert 'пока не загружена' in html
    user.has_admin = False
    html = client.get('/rational_structure/marginal_price').get_data(as_text=True)
    assert 'type="file"' not in html


def test_http_upload_then_get_reads_saved_data(import_client):
    client, _ = import_client
    response = client.post('/rational_structure/marginal_price/import', data={
        'csrf_token': csrf_token(client), 'database_version_id': '1',
        'file': (BytesIO(changed_book()), 'Расчет замыкающей станции.xlsx'),
    })
    assert response.status_code == 302
    assert response.location == '/rational_structure/marginal_price'
    db.session.remove()
    html = client.get('/rational_structure/marginal_price?territory=east&year=2030').get_data(as_text=True)
    assert 'Новая станция' in html
    assert 'Загруженный файл:' not in html
    assert db.session.query(CalculationWorkbook).count() == 2


@pytest.mark.parametrize('case,message', [
    ('csrf', 'проверить форму'), ('version', 'Версия БД изменилась'),
    ('missing', 'формате .xlsx'), ('extension', 'формате .xlsx'),
    ('empty', 'Файл пуст'), ('corrupt', 'Не удалось прочитать'),
    ('large', 'превышает 30 МБ'), ('no_version', 'Выберите версию'),
])
def test_http_rejects_bad_upload_without_changes(import_client, monkeypatch, case, message):
    client, _ = import_client
    data = {'csrf_token': csrf_token(client), 'database_version_id': '1',
            'file': (BytesIO(price_bytes()), 'price.xlsx')}
    if case == 'csrf':
        del data['csrf_token']
    elif case == 'version':
        data['database_version_id'] = '2'
    elif case == 'missing':
        del data['file']
    elif case == 'extension':
        data['file'] = (BytesIO(b'bad'), 'price.xls')
    elif case in ('empty', 'corrupt', 'large'):
        raw = b'' if case == 'empty' else b'bad'
        if case == 'large':
            raw = b'x' * (30 * 1024 * 1024 + 1)
        data['file'] = (BytesIO(raw), 'price.xlsx')
    else:
        monkeypatch.setattr(routes, 'get_current_db_version_id', lambda: None)
    response = client.post('/rational_structure/marginal_price/import', data=data)
    assert response.status_code == 302
    with client.session_transaction() as session:
        assert message in session['_flashes'][-1][1]
    row = db.session.scalar(db.select(CalculationWorkbook).filter_by(kind='marginal_price'))
    assert row.source_filename == 'source.xlsx'


def test_http_export_all_territories_years_and_precision(import_client):
    client, user = import_client
    user.has_admin = False
    response = client.get('/rational_structure/marginal_price/export?territory=east&year=2041')
    assert response.status_code == 200
    assert response.mimetype == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    assert 'attachment;' in response.headers['Content-Disposition']
    data = read_marginal_price_workbook(response.data)
    assert set(data) == set(TERRITORY_SHEETS)
    for table in data.values():
        assert len(table['rows']) == 3
        assert {row['values']['A'] for row in table['rows']} == {2041, 2042}
        assert table['rows'][0]['values']['C'] == '1.23456789'


def test_export_keeps_text_inert_and_uses_selected_version(import_client):
    client, _ = import_client
    raw = changed_book()
    book = load_workbook(BytesIO(raw))
    book['Восток']['D5'] = '=1+1'
    book['Восток']['D5'].data_type = 's'
    stream = BytesIO()
    book.save(stream)
    book.close()
    import_marginal_price_workbook(stream.getvalue(), 1, 'tester', 'text.xlsx')
    import_marginal_price_workbook(price_bytes(), 2, 'tester', 'other.xlsx')
    response = client.get('/rational_structure/marginal_price/export')
    book = load_workbook(BytesIO(response.data), data_only=False)
    assert book['Восток']['D5'].value == '=1+1'
    assert book['Восток']['D5'].data_type == 's'
    assert book['Восток']['A5'].value == 2030
    book.close()


def test_export_without_data_or_version_is_rejected(import_client, monkeypatch):
    client, _ = import_client
    db.session.query(CalculationWorkbook).filter_by(kind='marginal_price').delete()
    db.session.commit()
    assert client.get('/rational_structure/marginal_price/export').status_code == 400
    monkeypatch.setattr(routes, 'get_current_db_version_id', lambda: None)
    assert client.get('/rational_structure/marginal_price/export').status_code == 400


def test_http_upload_requires_admin_and_login(import_client):
    client, user = import_client
    user.has_admin = False
    assert client.post('/rational_structure/marginal_price/import').status_code == 403
    with client.session_transaction() as session:
        session.clear()
    from flask import g
    g.pop('_login_user', None)
    assert client.post('/rational_structure/marginal_price/import').status_code == 401
    assert client.get('/rational_structure/marginal_price/export').status_code == 401
