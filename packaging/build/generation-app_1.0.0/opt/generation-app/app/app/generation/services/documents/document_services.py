"""Сервисный модуль: Нормативные документы."""

from app.extensions import db
from sqlalchemy import or_, text
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO 
from config import SCHEMA_GENERATION
import os
from datetime import datetime
from werkzeug.utils import secure_filename

# Функции для работы с версионированием БД
from app.common.services.database_version_filter import (
    filter_by_db_version,
    set_db_version_on_create,
    get_current_db_version_id
)

# Модели
from app.generation.models.document.document_model import Document

# Сервисы
from app.common.services.help_services import (
    _dash,
    _clean_name,
)
from app.common.services.tranzaction_services import (
    _commit_with_retry,
    _locked_get,
    no_autoflush,
    quick_fix_seq,
)

# Логирование
from app.logs.services.logging_service import log_to_db


def document_query(
        document_filter=None, 
        sort_by="id", 
        sort_dir="asc"):
    """ Базовый запрос для выборки документов с фильтрацией и сортировкой. """

    # Валидация сортировки
    allowed_sort_by = {"id", "name"}
    sort_by = sort_by if sort_by in allowed_sort_by else "id"

    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    # Базовый запрос
    query = Document.query.filter(Document.id.isnot(None), Document.id > 0)
    
    # Фильтрация по версии БД
    query = filter_by_db_version(query, Document)

    # Фильтрация
    if document_filter:
        query = query.filter(Document.name.ilike(f"%{document_filter}%"))

    # Сортировка
    if sort_by == "name":
        sort_col = Document.name
    else:
        sort_col = Document.id

    query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    return query

@no_autoflush
def get_document_list(
    page, 
    per_page, 
    document_filter=None, 
    sort_by="id", 
    sort_dir="asc"):
    """ Получает список документов с пагинацией, фильтрацией и сортировкой. """
    
    # Базовый запрос
    query = document_query(
        document_filter=document_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Пагинация
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_document_service(data, user):
    """ Обновление данных по документам """

    if not isinstance(data, list):
        raise ValueError(f"Данные должны быть предоставлены в виде списка словарей.")

    updated_ids = []
    
    log_to_db(
        user, 
        "Получены данные для обновления списка документов", 
        f"{data}",
        entity_type="document")
    
    # Проверки на валидность данных
    with db.session.no_autoflush:
        for record in data:
            document_id = record.get("document_id")
            name = (record.get("name") or "").strip()

            if not name:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись: {record}", 
                    entity_type="document",
                    entity_id=document_id)
                raise ValueError(f"Поле 'name' обязательно для заполнения.")

            obj = db.session.get(Document, document_id)
            if not obj:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись с ID «{document_id}» не найдена.", 
                    entity_type="document", 
                    entity_id=document_id)
                raise ValueError(f"Запись с ID «{document_id}» не найдена.")

            # Проверка уникальности name
            if name != (obj.name or ""):
                q = (Document.query
                     .filter(Document.name == name,
                             Document.id != document_id))
                if q.first():
                    raise ValueError(f"Запись с именем «{name}» уже существует.")

            changes = {}

            if name != (obj.name or ""):
                changes["Наименование"] = f"{_dash(obj.name)} → {name}"
                obj.name = name

            # Если есть реальные изменения — лог и добавление в список
            if changes:
                log_to_db(
                    user, 
                    f"Обновлен документ: {name}",
                    f"Изменения = {changes}", 
                    entity_type="document", 
                    entity_id=document_id)
                updated_ids.append(document_id)

        db.session.flush()

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        if updated_ids:
            log_to_db(
                user, 
                "Сохранены изменения по документам", 
                f"Измененных записей: {len(updated_ids)} (id: {updated_ids})", 
                entity_type="document")
        else:
            log_to_db(
                user, 
                "Изменений по документам не обнаружено", 
                "", 
                entity_type="document")
            
        return updated_ids
    
    except IntegrityError as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения документов (уникальность/целостность)", 
            str(e), 
            entity_type="document")
        raise ValueError(f"Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Неизвестная ошибка при сохранении документов", 
            str(e), 
            entity_type="document")
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


@no_autoflush
def add_document_service(data, user):
    """Создание новой записи: документ"""
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    created_ids = []
    
    def _do_insert():
        with db.session.no_autoflush:
            for record in data:
                name = (record.get("name") or "").strip()

                if not name:
                    log_to_db(
                        user, 
                        "Ошибка валидации", 
                        f"Запись: {record}", 
                        entity_type="document")
                    raise ValueError("Каждая запись должна содержать 'name'.")

                dup_name = (Document.query
                            .filter(Document.name == name)
                            .with_for_update().first())
                if dup_name:
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")

                obj = Document(name=name)
                # Автоматически связываем с текущей версией БД
                set_db_version_on_create(obj)
                db.session.add(obj)
                db.session.flush()
                
                created_ids.append(obj.id)

                log_to_db(
                    user, 
                    "Создан документ", 
                    f"Наименование: {name}, ID: {obj.id}",
                    entity_type="document", 
                    entity_id=obj.id)

    try:
        _do_insert()
        _commit_with_retry()
        return created_ids[0] if len(created_ids) == 1 else created_ids

    except IntegrityError:
        db.session.rollback()
        created_ids.clear()
        quick_fix_seq(SCHEMA_GENERATION, "documents_kommod")
        _do_insert()
        _commit_with_retry()
        return created_ids[0] if len(created_ids) == 1 else created_ids
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения нового документа", 
            str(e), 
            entity_type="document")
        raise ValueError(f"Ошибка сохранения нового документа: {e}") from e


@no_autoflush
def delete_document_service(ids, user):
    """Удаляет записи документов по переданным ID."""

    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError(f"Не переданы ID для удаления.")

    log_to_db(
        user, 
        "Удаление документов", 
        f"Переданы ID для удаления: {ids}", 
        entity_type="document")

    successful_deletes = 0
    deleted_names = []
    not_found = []
    invalid = []

    for doc_id in ids:
        try:
            document_id = int(doc_id)
        except (TypeError, ValueError):
            invalid.append(doc_id)
            log_to_db(
                user, 
                "Ошибка удаления документов", 
                f"Некорректный ID: {doc_id}", 
                entity_type="document",
                entity_id=doc_id)
            continue

        obj = _locked_get(Document, document_id)
        if obj:
            name = obj.name or f"ID={document_id}"
            
            # Удаляем файл из файловой системы, если он существует
            if obj.file_path and os.path.exists(obj.file_path):
                try:
                    os.remove(obj.file_path)
                    log_to_db(
                        user, 
                        f"Удален файл документа при удалении документа ID={document_id}", 
                        obj.file_path, 
                        entity_type="document", 
                        entity_id=document_id)
                except Exception as e:
                    log_to_db(
                        user, 
                        f"Ошибка удаления файла при удалении документа ID={document_id}", 
                        str(e), 
                        entity_type="document", 
                        entity_id=document_id)
            
            db.session.delete(obj)
            successful_deletes += 1
            deleted_names.append(name)
            log_to_db(
                user, 
                "Удален документ", 
                f"{name}", 
                entity_type="document", 
                entity_id=document_id)
        else:
            not_found.append(document_id)
            log_to_db(
                user, 
                "Ошибка удаления документов", 
                f"Документ с ID={document_id} не найден.", 
                entity_type="document", 
                entity_id=document_id)

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        parts = [f"Удалено: {successful_deletes}"]
        if deleted_names:
            parts.append(f"Наименование: {deleted_names}")
        if not_found:
            parts.append(f"Не найдены ID: {not_found}")
        if invalid:
            parts.append(f"Некорректные ID: {invalid}")

        return {
            "deleted": successful_deletes,
            "deleted_names": deleted_names,
            "not_found": not_found,
            "invalid": invalid,
        }
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка удаления документов", 
            str(e), 
            entity_type="document")
        raise ValueError(f"Ошибка при удалении данных.")


def export_document_service(
    user,
    document_filter=None,
    sort_by="id",
    sort_dir="asc",):
    """ Экспортирует данные документов в Excel. """

    log_to_db(user, "Начата выгрузка таблицы документов из базы данных", entity_type="document")
    log_to_db(user, "Параметры экспорта",
        (
            f"Фильтр по столбцу: Название документа = {document_filter},"
            f"Сортировка по = {sort_by}, направление сортировки = {sort_dir}."
        ), entity_type="document"
    )

    # Базовый запрос
    query = document_query(
        document_filter=document_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Получение данных
    items = query.all()
    log_to_db(user, "Получение данных завершено", f"Найдено записей: {len(items)}", entity_type="document")

    # Подготовка данных для Excel
    data = []
    for idx, o in enumerate(items, start=1):
        data.append({
            "№": idx,
            "Название документа": _dash(o.name),
        })

    log_to_db(user, "Подготовка данных для экспорта таблицы документов в Excel",
              f"Записей для экспорта: {len(data)}", entity_type="document")

    df = pd.DataFrame(data)

    # Создание Excel и авто-ширина столбцов
    output = BytesIO()
    sheet_name = "Нормативные документы"
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        ws = writer.sheets[sheet_name]

        # Автоподбор ширины с аккуратным лимитом
        for i, col in enumerate(df.columns):
            max_len = max(len(str(col)), *(len(str(v)) for v in df[col].values)) if not df.empty else len(str(col))
            ws.set_column(i, i, min(max_len + 2, 60))

    output.seek(0)
    log_to_db(user, "Экспорт таблицы документов в Excel завершен", f"Экспортировано записей: {len(data)}", entity_type="document")
    return output


# Константы для работы с файлами
UPLOAD_FOLDER = 'uploads/documents_kommod'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'zip', 'rar', '7z'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 МБ


def normalize_file_path(file_path):
    """
    Нормализует путь к файлу для корректной работы в Windows.
    Исправляет смешанные слеши и приводит путь к стандартному виду ОС.
    Если путь относительный, строит абсолютный путь от корня проекта.
    
    Args:
        file_path: путь к файлу
        
    Returns:
        str: нормализованный абсолютный путь
    """
    if not file_path:
        return file_path
    
    # Нормализуем путь (исправляем слеши)
    normalized = os.path.normpath(file_path)
    
    # Если путь уже абсолютный, возвращаем его
    if os.path.isabs(normalized):
        return normalized
    
    # Если путь относительный, строим абсолютный от корня проекта
    # Корень проекта - это директория, где находится run.py
    # __file__ = c:\fproject\app\generation\services\documents\document_services.py
    # Нужно подняться на 5 уровней: documents -> services -> generation -> app -> fproject
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    absolute_path = os.path.join(project_root, normalized)
    
    return absolute_path


def allowed_file(filename):
    """Проверяет, допустимо ли расширение файла."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@no_autoflush
def save_document_file(file, document_id, user):
    """
    Сохраняет файл документа в файловую систему и обновляет запись в БД.
    
    Args:
        file: FileStorage объект из Flask
        document_id: ID документа
        user: имя пользователя для логирования
        
    Returns:
        dict: информация о сохраненном файле
        
    Raises:
        ValueError: если файл не валиден или документ не найден
    """
    log_to_db(user, f"Начало загрузки файла для документа ID={document_id}", f"Имя файла: {file.filename if file else 'None'}", entity_type="document", entity_id=document_id)
    
    if not file or file.filename == '':
        raise ValueError("Файл не выбран.")
    
    if not allowed_file(file.filename):
        raise ValueError(f"Недопустимый тип файла. Разрешены: {', '.join(ALLOWED_EXTENSIONS)}")
    
    # Проверка размера файла
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    log_to_db(user, f"Размер файла проверен: {file_size} байт", "", entity_type="document", entity_id=document_id)
    
    if file_size > MAX_FILE_SIZE:
        raise ValueError(f"Файл слишком большой. Максимальный размер: {MAX_FILE_SIZE // (1024 * 1024)} МБ.")
    
    # Получаем документ из БД
    with db.session.no_autoflush:
        document = db.session.get(Document, document_id)
        if not document:
            raise ValueError(f"Документ с ID {document_id} не найден.")
        
        document_name = document.name  # Сохраняем имя для использования вне блока
        log_to_db(user, f"Документ найден: {document_name}", "", entity_type="document", entity_id=document_id)
        
        # Определяем корень проекта и создаем абсолютный путь к директории
        # Нужно подняться на 5 уровней: documents -> services -> generation -> app -> fproject
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
        upload_dir_absolute = os.path.join(project_root, UPLOAD_FOLDER)
        
        # Создаем директорию если не существует
        os.makedirs(upload_dir_absolute, exist_ok=True)
        
        # Генерируем безопасное имя файла
        original_filename = secure_filename(file.filename)
        file_extension = original_filename.rsplit('.', 1)[1].lower()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filename = f"doc_{document_id}_{timestamp}.{file_extension}"
        
        # Относительный путь для сохранения в БД
        file_path_relative = os.path.join(UPLOAD_FOLDER, safe_filename).replace('\\', '/')
        # Абсолютный путь для сохранения файла в FS
        file_path_absolute = os.path.join(upload_dir_absolute, safe_filename)
        
        log_to_db(user, f"Путь для сохранения (относительный): {file_path_relative}", "", entity_type="document", entity_id=document_id)
        log_to_db(user, f"Путь для сохранения (абсолютный): {file_path_absolute}", "", entity_type="document", entity_id=document_id)
        
        # Удаляем старый файл если существует
        if document.file_path:
            old_file_path = normalize_file_path(document.file_path)
            if os.path.exists(old_file_path):
                try:
                    os.remove(old_file_path)
                    log_to_db(user, f"Удален старый файл документа ID={document_id}", old_file_path, entity_type="document", entity_id=document_id)
                except Exception as e:
                    log_to_db(user, f"Ошибка удаления старого файла документа ID={document_id}", str(e), entity_type="document", entity_id=document_id)
        
        # Сохраняем новый файл (используем абсолютный путь)
        try:
            file.save(file_path_absolute)
            log_to_db(user, f"Файл сохранен в файловую систему: {file_path_absolute}", "", entity_type="document", entity_id=document_id)
            
            # Обновляем запись в БД (сохраняем относительный путь)
            document.file_path = file_path_relative
            document.file_name = original_filename
            document.file_size = file_size
            document.file_type = file.content_type
            document.uploaded_at = datetime.now()
            
            log_to_db(user, f"Обновление полей документа в БД", f"file_path={file_path_relative}, file_name={original_filename}", entity_type="document", entity_id=document_id)
            
            db.session.flush()
            log_to_db(user, f"Flush выполнен успешно", "", entity_type="document", entity_id=document_id)
            
        except Exception as e:
            db.session.rollback()
            # Удаляем файл если сохранение в БД не удалось
            if os.path.exists(file_path_absolute):
                os.remove(file_path_absolute)
            log_to_db(user, f"Ошибка сохранения файла документа ID={document_id}", str(e), entity_type="document", entity_id=document_id)
            raise ValueError(f"Ошибка сохранения файла: {e}")
    
    # Коммит вне блока no_autoflush
    try:
        _commit_with_retry()
        
        log_to_db(
            user, 
            f"Загружен файл для документа: {document_name}",
            f"Файл: {original_filename}, Размер: {file_size} байт, Путь: {file_path_relative}",
            entity_type="document",
            entity_id=document_id
        )
        
        return {
            "file_name": original_filename,
            "file_size": file_size,
            "file_path": file_path_relative,
        }
    except Exception as e:
        db.session.rollback()
        if os.path.exists(file_path_absolute):
            os.remove(file_path_absolute)
        log_to_db(user, f"Ошибка коммита при сохранении файла документа ID={document_id}", str(e), entity_type="document", entity_id=document_id)
        raise ValueError(f"Ошибка сохранения файла в БД: {e}")


def delete_document_file(document_id, user):
    """
    Удаляет файл документа из файловой системы и обновляет запись в БД.
    
    Args:
        document_id: ID документа
        user: имя пользователя для логирования
        
    Raises:
        ValueError: если документ не найден
    """
    document = db.session.get(Document, document_id)
    if not document:
        raise ValueError(f"Документ с ID {document_id} не найден.")
    
    if not document.file_path:
        raise ValueError("У документа нет загруженного файла.")
    
    # Удаляем файл из файловой системы
    file_path = normalize_file_path(document.file_path)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            log_to_db(user, f"Удален файл документа: {document.name}", file_path, entity_type="document", entity_id=document_id)
        except Exception as e:
            log_to_db(user, f"Ошибка удаления файла документа ID={document_id}", str(e), entity_type="document", entity_id=document_id)
            raise ValueError(f"Ошибка удаления файла: {e}")
    
    # Обновляем запись в БД
    try:
        document.file_path = None
        document.file_name = None
        document.file_size = None
        document.file_type = None
        document.uploaded_at = None
        
        db.session.flush()
        _commit_with_retry()
        
        log_to_db(user, f"Информация о файле удалена для документа: {document.name}", "", entity_type="document", entity_id=document_id)
        
    except Exception as e:
        db.session.rollback()
        log_to_db(user, f"Ошибка обновления БД при удалении файла документа ID={document_id}", str(e), entity_type="document", entity_id=document_id)
        raise ValueError(f"Ошибка обновления БД: {e}")


def get_document_file_path(document_id):
    """
    Получает путь к файлу документа.
    
    Args:
        document_id: ID документа
        
    Returns:
        tuple: (file_path, file_name) или (None, None) если файла нет
    """
    document = db.session.get(Document, document_id)
    if not document or not document.file_path:
        return None, None
    
    return document.file_path, document.file_name

