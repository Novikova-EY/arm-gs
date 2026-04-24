from datetime import datetime
from io import BytesIO
import re

from flask import Blueprint, current_app, jsonify, render_template, request, send_file
from flask_login import login_required
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

start_bp = Blueprint('start', __name__)

@start_bp.route('/')
def index():
    return render_template('home.html')


def _safe_excel_sheet_name(sheet_name: str) -> str:
    cleaned = re.sub(r'[:\\/?*\[\]]', '_', (sheet_name or '').strip())
    cleaned = cleaned[:31].strip()
    return cleaned or 'Sheet1'


def _safe_download_name(filename: str) -> str:
    cleaned = re.sub(r'[^A-Za-zА-Яа-я0-9._() -]+', '_', (filename or '').strip())
    cleaned = cleaned.strip(' ._')
    return cleaned or f'table_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}'


@start_bp.route('/export_table_excel', methods=['POST'])
@login_required
def export_table_excel():
    """Универсальный экспорт произвольной HTML-таблицы в XLSX."""

    payload = request.get_json(silent=True) or {}
    headers = payload.get('headers') or []
    rows = payload.get('rows') or []
    sheet_name = _safe_excel_sheet_name(payload.get('sheet_name') or 'Данные')
    filename = _safe_download_name(payload.get('filename') or 'table_export')

    if not isinstance(headers, list) or not isinstance(rows, list):
        return jsonify({'error': 'Некорректный формат данных для экспорта.'}), 400

    try:
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = sheet_name

        if headers:
            worksheet.append([str(value) if value is not None else '' for value in headers])
            header_fill = PatternFill(fill_type='solid', fgColor='D1E7DD')
            header_font = Font(bold=True)
            for cell in worksheet[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

        for row in rows:
            if not isinstance(row, list):
                continue
            worksheet.append([str(value) if value is not None else '' for value in row])

        if headers:
            worksheet.freeze_panes = 'A2'
            worksheet.auto_filter.ref = worksheet.dimensions

        for column_cells in worksheet.columns:
            max_length = 0
            column_letter = column_cells[0].column_letter
            for cell in column_cells:
                value = '' if cell.value is None else str(cell.value)
                if len(value) > max_length:
                    max_length = len(value)
                cell.alignment = Alignment(vertical='top', wrap_text=True)
            worksheet.column_dimensions[column_letter].width = min(max(max_length + 2, 12), 60)

        output = BytesIO()
        workbook.save(output)
        output.seek(0)

        if not filename.lower().endswith('.xlsx'):
            filename = f'{filename}.xlsx'

        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            max_age=0,
        )
    except Exception as exc:
        current_app.logger.error('Ошибка универсального экспорта таблицы: %s', exc)
        return jsonify({'error': 'Не удалось сформировать Excel-файл.'}), 500
