"""Формы для справочника «Номативные документы». """

from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, HiddenField, IntegerField
from wtforms.validators import DataRequired, Optional, Length, NumberRange
from flask_wtf.file import FileField, FileAllowed


class DocumentFilterForm(FlaskForm):
    """Форма списка/фильтрации документов."""
    csrf_token = HiddenField()

    # Для пакетного обновления
    document_ids = HiddenField("ID записей")

    # Поля редактируемых строк (в шаблоне рендерятся массивами name="name[]" и т.д.)
    name = StringField(
        "Название документа",
        validators=[
            DataRequired(message="Поле «Название документа» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )

    # Флаг удаления строки (в шаблоне как массив checkbox'ов)
    document_delete = HiddenField("Удалить")

    # Поля фильтра
    document_filter = StringField(
        "Фильтр по названию документа",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Поиск по названию документа"},
    )

    # Пагинация
    page = HiddenField(default=1)
    per_page = SelectField(
        "Количество строк на странице",
        choices=[(5, '5 строк'), (10, '10 строк'), (25, '25 строк'), (50, '50 строк')],
        coerce=int,
        validators=[Optional(), NumberRange(min=5, max=50)],
    )


class AddDocumentForm(FlaskForm):
    """Форма добавления записи документа."""
    csrf_token = HiddenField()

    name = StringField(
        "Название документа",
        validators=[
            DataRequired(message="Поле «Название документа» обязательно."),
            Length(min=3, max=255, message="Длина от 3 до 255 символов."),
        ],
    )

    file = FileField(
        "Файл документа",
        validators=[
            Optional(),
            FileAllowed(
                ["pdf", "doc", "docx", "xls", "xlsx", "txt", "zip", "rar", "7z"],
                message="Допустимые форматы: pdf, doc, docx, xls, xlsx, txt, zip, rar, 7z."
            ),
        ],
    )


class UploadDocumentFileForm(FlaskForm):
    """Форма загрузки/замены файла документа."""
    csrf_token = HiddenField()

    file = FileField(
        "Файл документа",
        validators=[
            DataRequired(message="Выберите файл для загрузки."),
            FileAllowed(
                ["pdf", "doc", "docx", "xls", "xlsx", "txt", "zip", "rar", "7z"],
                message="Допустимые форматы: pdf, doc, docx, xls, xlsx, txt, zip, rar, 7z."
            ),
        ],
    )

