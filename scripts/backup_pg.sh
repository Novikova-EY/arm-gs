#!/bin/bash
# Бэкап PostgreSQL для generation-app (custom format, с ротацией).
# Предназначен для cron / systemd timer на сервере — вне дерева релиза.
set -euo pipefail

ENV_FILE="${ENV_FILE:-/etc/generation-app/app.env}"
KEEP_DEFAULT=14

if [[ -f "${ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    . "${ENV_FILE}"
    set +a
fi

BACKUP_BASE_DIR="${BACKUP_BASE_DIR:-/var/backups/generation-app}"
BACKUP_DIR="${AUTO_BACKUP_DIR:-${BACKUP_BASE_DIR}/auto}"
KEEP="${KEEP_AUTO_BACKUPS:-${KEEP_DEFAULT}}"

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-}"
DB_NAME="${DB_NAME:-}"
DB_PASS="${DB_PASS:-${DB_PASSWORD:-}}"

if [[ -z "${DB_USER}" || -z "${DB_NAME}" ]]; then
    echo "error: DB_USER и DB_NAME должны быть заданы (через ${ENV_FILE} или окружение)" >&2
    exit 1
fi

if ! command -v pg_dump >/dev/null 2>&1; then
    echo "error: pg_dump не найден в PATH" >&2
    exit 1
fi

mkdir -p "${BACKUP_DIR}"
chmod 750 "${BACKUP_DIR}" 2>/dev/null || true

TS="$(date +%Y%m%d_%H%M%S)"
OUT="${BACKUP_DIR}/auto_backup_${TS}.dump"

export PGPASSWORD="${DB_PASS}"
pg_dump \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -F c \
    -b \
    -f "${OUT}" \
    "${DB_NAME}"
unset PGPASSWORD

SIZE="$(du -h "${OUT}" | awk '{print $1}')"
echo "backup ok: ${OUT} (${SIZE})"

# Оставляем только последние KEEP файлов auto_backup_*.dump
mapfile -t FILES < <(ls -1t "${BACKUP_DIR}"/auto_backup_*.dump 2>/dev/null || true)
if (( ${#FILES[@]} > KEEP )); then
    for OLD in "${FILES[@]:KEEP}"; do
        rm -f "${OLD}"
        echo "removed old backup: ${OLD}"
    done
fi
