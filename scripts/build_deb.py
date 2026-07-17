#!/usr/bin/env python3
"""
Сборка deb-пакета generation-app.

Скрипт формирует staging-директорию, копирует нужные файлы приложения,
подменяет версию в control-файле и вызывает dpkg-deb.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGING_TEMPLATE = PROJECT_ROOT / "packaging" / "deb"
BUILD_ROOT = PROJECT_ROOT / "packaging" / "build"
DEB_OUTPUT_TEMPLATE = PROJECT_ROOT / "packaging" / "generation-app_{version}_amd64.deb"

# Каталоги/файлы, которые попадут в /opt/generation-app/app
# backups/backup/logs не включаем: дампы БД раздувают .deb до ~1.5 ГБ
PAYLOAD_ITEMS = [
    "app",
    "migrations",
    "scripts",
    "run.py",
    "config.py",
    "gunicorn_config.py",
    "waitress_config.py",
    "start_production.sh",
    "start_waitress.py",
    "requirements.txt",
    "requirements-linux.txt",
    "README.md",
]

# Паттерны, которые не копируем (внутри каталогов)
IGNORE_PATTERNS = [
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".pytest_cache",
    ".mypy_cache",
    ".git",
    ".github",
    ".venv",
    "venv",
    "flask_session",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Собрать deb-пакет generation-app.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--version",
        help="Версия пакета. Если не указана, используется git describe "
        "или дата YYYY.MM.DD.",
    )
    parser.add_argument(
        "--dpkg",
        default="dpkg-deb",
        help="Путь до утилиты dpkg-deb (если не в PATH).",
    )
    parser.add_argument(
        "--compress",
        choices=("default", "gzip", "xz", "zstd", "none"),
        default="default",
        help="Тип сжатия для dpkg-deb -Z. «default» — как у dpkg. "
        "При EIO/zstd попробуйте xz или gzip.",
    )
    parser.add_argument(
        "--temp-dir",
        type=Path,
        default=None,
        help="Каталог для промежуточного .deb (по умолчанию системный temp). "
        "Помогает, если целевой каталог packaging на проблемном томе.",
    )
    return parser.parse_args()


def detect_version(explicit: str | None) -> str:
    if explicit:
        return explicit

    git = shutil.which("git")
    if git:
        try:
            completed = subprocess.run(
                [git, "-C", str(PROJECT_ROOT), "describe", "--tags", "--dirty", "--always"],
                check=True,
                capture_output=True,
                text=True,
            )
            version = completed.stdout.strip()
            if version:
                return version.replace("/", "-")
        except subprocess.CalledProcessError:
            pass

    return dt.datetime.utcnow().strftime("%Y.%m.%d")


def prepare_build_dir(version: str) -> Path:
    build_dir = BUILD_ROOT / f"generation-app_{version}"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    shutil.copytree(PACKAGING_TEMPLATE, build_dir)
    return build_dir


def ensure_app_payload(build_dir: Path) -> Path:
    payload_root = build_dir / "opt" / "generation-app" / "app"
    payload_root.mkdir(parents=True, exist_ok=True)
    return payload_root


def copy_payload(payload_root: Path) -> None:
    log_path = PROJECT_ROOT / ".cursor" / "debug.log"
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "sessionId": "debug-session",
                        "runId": "pre-fix",
                        "hypothesisId": "A",
                        "location": "build_deb.py:copy_payload",
                        "message": "Начало copy_payload",
                        "data": {"ignore_patterns": IGNORE_PATTERNS, "payload_items": PAYLOAD_ITEMS},
                        "timestamp": int(dt.datetime.now().timestamp() * 1000),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    except OSError:
        pass

    ignore = shutil.ignore_patterns(*IGNORE_PATTERNS)
    for item in PAYLOAD_ITEMS:
        src = PROJECT_ROOT / item
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(
                    json.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "pre-fix",
                            "hypothesisId": "A",
                            "location": "build_deb.py:item",
                            "message": "Проверка элемента payload",
                            "data": {
                                "item": item,
                                "src_exists": src.exists(),
                                "src_is_dir": src.is_dir() if src.exists() else None,
                            },
                            "timestamp": int(dt.datetime.now().timestamp() * 1000),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        except OSError:
            pass

        if not src.exists():
            continue

        dest = payload_root / src.name
        if src.is_dir():
            shutil.copytree(src, dest, dirs_exist_ok=True, ignore=ignore)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)


def copy_static_files(build_dir: Path) -> None:
    """
    Копирует статические файлы в /usr/share/generation-app/static
    чтобы nginx всегда раздавал их из стабильного места.
    """
    static_src = PROJECT_ROOT / "app" / "static"
    static_dest = build_dir / "usr" / "share" / "generation-app" / "static"

    if not static_src.exists():
        print(f"Предупреждение: {static_src} не найден, пропускаем копирование статики")
        return

    if static_dest.exists():
        shutil.rmtree(static_dest)

    static_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(static_src, static_dest)
    print(f"Статические файлы скопированы в {static_dest}")


def patch_control_version(build_dir: Path, version: str) -> None:
    control_path = build_dir / "DEBIAN" / "control"
    control_text = control_path.read_text(encoding="utf-8")
    control_path.write_text(control_text.replace("__VERSION__", version), encoding="utf-8")


def normalize_debian_scripts_line_endings(build_dir: Path) -> None:
    """CRLF в скриптах DEBIAN ломает bash на Linux (cd /tmp\\r, upgrade\\r и т.д.)."""
    for script_name in ("postinst", "postrm", "prerm", "preinst"):
        script_path = build_dir / "DEBIAN" / script_name
        if script_path.exists():
            text = script_path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
            script_path.write_text(text, encoding="utf-8")


def normalize_shell_scripts_line_endings(build_dir: Path) -> None:
    """CRLF в .sh из Windows-сборки ломает shebang на Linux."""
    payload_scripts = build_dir / "opt" / "generation-app" / "app" / "scripts"
    for script_path in payload_scripts.glob("*.sh") if payload_scripts.is_dir() else []:
        text = script_path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
        script_path.write_text(text, encoding="utf-8")
        script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def make_scripts_executable(build_dir: Path) -> None:
    for script_name in ("postinst", "postrm", "prerm"):
        script_path = build_dir / "DEBIAN" / script_name
        if script_path.exists():
            script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def build_package(
    build_dir: Path,
    version: str,
    dpkg_bin: str,
    *,
    compress: str = "default",
    temp_dir: Path | None = None,
) -> Path:
    deb_root = Path(build_dir)
    control_dir = deb_root / "DEBIAN"

    if control_dir.exists():
        os.chmod(control_dir, 0o755)
        maint_scripts = {"postinst", "preinst", "prerm", "postrm"}
        for item in control_dir.iterdir():
            if item.is_file():
                if item.name in maint_scripts:
                    os.chmod(item, 0o755)
                else:
                    os.chmod(item, 0o644)

    output_path = DEB_OUTPUT_TEMPLATE.with_name(DEB_OUTPUT_TEMPLATE.name.format(version=version))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    cmd = [dpkg_bin, "--build"]
    if compress != "default":
        cmd.extend(["-Z", compress])

    tmp_fd: int | None = None
    tmp_path: Path | None = None
    try:
        base_dir = os.fspath(temp_dir) if temp_dir else None
        tmp_fd, tmp_name = tempfile.mkstemp(suffix=".deb", prefix="generation-app_", dir=base_dir)
        tmp_path = Path(tmp_name)
        os.close(tmp_fd)
        tmp_fd = None

        subprocess.run(cmd + [str(deb_root), str(tmp_path)], check=True)

        try:
            os.replace(tmp_path, output_path)
        except OSError:
            shutil.copy2(tmp_path, output_path)
            tmp_path.unlink(missing_ok=True)
    finally:
        if tmp_fd is not None:
            try:
                os.close(tmp_fd)
            except OSError:
                pass
        if tmp_path is not None and tmp_path.exists() and tmp_path.resolve() != output_path.resolve():
            tmp_path.unlink(missing_ok=True)

    return output_path


def main() -> int:
    args = parse_args()
    version = detect_version(args.version)
    build_dir = prepare_build_dir(version)
    payload_root = ensure_app_payload(build_dir)
    copy_payload(payload_root)
    copy_static_files(build_dir)
    patch_control_version(build_dir, version)
    normalize_debian_scripts_line_endings(build_dir)
    normalize_shell_scripts_line_endings(build_dir)
    make_scripts_executable(build_dir)
    output_path = build_package(
        build_dir,
        version,
        args.dpkg,
        compress=args.compress,
        temp_dir=args.temp_dir,
    )
    print(f"Готово: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
