import re
from datetime import datetime, date
from wtforms.validators import ValidationError

def validate_year_or_date(form, field):
    """
    Разрешает ввод:
    - 'YYYY'
    - 'DD.MM.YYYY'
    - 'YYYY-MM-DD'
    - или объект date/datetime (например, при process(obj=...))
    """
    value = field.data

    if not value:
        return  # Пусто — пропускаем

    # ✅ Если пришел объект date/datetime — просто проверим год
    if isinstance(value, (date, datetime)):
        if value.year > 2050:
            raise ValidationError('Год в дате не может быть больше 2050.')
        return

    # ✅ Если пришла строка
    value = value.strip()

    # YYYY-MM-DD
    if re.match(r'^\d{4}-\d{2}-\d{2}$', value):
        try:
            dt = datetime.strptime(value, '%Y-%m-%d')
            if dt.year > 2050:
                raise ValidationError('Год в дате не может быть больше 2050.')
            return
        except ValueError:
            raise ValidationError(f'Некорректная дата: {value}. Используйте YYYY, DD.MM.YYYY или YYYY-MM-DD.')

    # DD-MM-YYYY (часто вводят так же, как DD.MM.YYYY, но с дефисами)
    if re.match(r'^\d{2}-\d{2}-\d{4}$', value):
        try:
            dt = datetime.strptime(value, '%d-%m-%Y')
            if dt.year > 2050:
                raise ValidationError('Год в дате не может быть больше 2050.')
            return
        except ValueError:
            raise ValidationError(f'Некорректная дата: {value}. Используйте YYYY, DD.MM.YYYY или YYYY-MM-DD.')

    # YYYY
    if re.match(r'^\d{4}$', value):
        year = int(value)
        if year > 2050:
            raise ValidationError('Год не может быть больше 2050.')
        return

    # DD.MM.YYYY
    if re.match(r'^\d{2}\.\d{2}\.\d{4}$', value):
        try:
            dt = datetime.strptime(value, '%d.%m.%Y')
            if dt.year > 2050:
                raise ValidationError('Год в дате не может быть больше 2050.')
            return
        except ValueError:
            raise ValidationError(f'Некорректная дата: {value}. Используйте YYYY, DD.MM.YYYY или YYYY-MM-DD.')

    # ❌ Все остальное — ошибка
    raise ValidationError(f'Некорректный формат: {value}. Используйте YYYY, DD.MM.YYYY или YYYY-MM-DD.')


def validate_year_or_date_list(form, field):
    """
    Разрешает ввод нескольких дат/годов в одном поле, разделенных
    запятыми или точкой с запятой.

    Примеры:
    - "2020; 2021"
    - "01.01.2020, 15.02.2021"
    - "2020-01-01; 2021-12-31"
    """
    value = field.data

    if not value:
        return

    # Для объектов date/datetime оставляем поведение одиночного валидатора
    if isinstance(value, (date, datetime)):
        return validate_year_or_date(form, field)

    if not isinstance(value, str):
        raise ValidationError(
            "Некорректный тип значения. Ожидается строка с датами через ',' или ';'."
        )

    # Разбиваем по запятым и точкам с запятой
    parts = re.split(r"[;,]", value)
    errors = []

    for raw_part in parts:
        part = raw_part.strip()
        if not part:
            continue

        # Используем существующую логику проверки одной даты,
        # подставляя временное поле с нужным значением.
        tmp_field = type("TmpField", (), {})()
        tmp_field.data = part
        try:
            validate_year_or_date(form, tmp_field)
        except ValidationError as exc:
            errors.append(str(exc))

    if errors:
        # Показываем первую ошибку, чтобы не перегружать пользователя
        raise ValidationError(errors[0])
