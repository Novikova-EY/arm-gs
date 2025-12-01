#!/usr/bin/env python3
"""
Сборка deb-пакета generation-app.

Скрипт формирует staging-директорию, копирует нужные файлы приложения,
подменяет версию в control-файле и вызывает dpkg-deb.
"""
from __future__ import annotations

import argparse
import datetime as dt
import shutil
import stat
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGING_TEMPLATE = PROJECT_ROOT / "packaging" / "deb"
BUILD_ROOT = PROJECT_ROOT / "packaging" / "build"
DEB_OUTPUT_TEMPLATE = PROJECT_ROOT / "packaging" / "generation-app_{version}_amd64.deb"

# Каталоги/файлы, которые попадут в /opt/generation-app/app
PAYLOAD_ITEMS = [
    "app",
    "migrations",
    "scripts",
    "backup",
    "backups",
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
    "logs",
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
    ignore = shutil.ignore_patterns(*IGNORE_PATTERNS)
    for item in PAYLOAD_ITEMS:
        src = PROJECT_ROOT / item
        if not src.exists():
            continue

        dest = payload_root / src.name
        if src.is_dir():
            shutil.copytree(src, dest, dirs_exist_ok=True, ignore=ignore)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)


def patch_control_version(build_dir: Path, version: str) -> None:
    control_path = build_dir / "DEBIAN" / "control"
    control_text = control_path.read_text(encoding="utf-8")
    control_path.write_text(control_text.replace("__VERSION__", version), encoding="utf-8")


def make_scripts_executable(build_dir: Path) -> None:
    for script_name in ("postinst", "postrm", "prerm"):
        script_path = build_dir / "DEBIAN" / script_name
        if script_path.exists():
            script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


import os
import subprocess
from pathlib import Path

def build_package(build_dir: Path, version: str, dpkg_bin: str) -> Path:
    deb_root = Path(build_dir)
    control_dir = deb_root / "DEBIAN"

    if control_dir.exists():
        # Папка DEBIAN
        os.chmod(control_dir, 0o755)

        # Файлы внутри DEBIAN
        maint_scripts = {"postinst", "preinst", "prerm", "postrm"}
        for item in control_dir.iterdir():
            if item.is_file():
                if item.name in maint_scripts:
                    # maintainer-скрипты должны быть исполняемыми
                    os.chmod(item, 0o755)
                else:
                    # всё остальное (control, md5sums и т.п.)
                    os.chmod(item, 0o644)

    output_path = DEB_OUTPUT_TEMPLATE.with_name(
        DEB_OUTPUT_TEMPLATE.name.format(version=version)
    )
    if output_path.exists():
        output_path.unlink()

    subprocess.run(
        [dpkg_bin, "--build", str(deb_root), str(output_path)],
        check=True,
    )

    return output_path




def main() -> int:
    args = parse_args()
    version = detect_version(args.version)
    build_dir = prepare_build_dir(version)
    payload_root = ensure_app_payload(build_dir)
    copy_payload(payload_root)
    patch_control_version(build_dir, version)
    make_scripts_executable(build_dir)
    output_path = build_package(build_dir, version, args.dpkg)
    print(f"Готово: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())



