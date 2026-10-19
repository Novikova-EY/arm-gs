# -*- coding: utf-8 -*-
"""Сравнение файлов из последнего .deb с тем, что стоит на сервере."""
import hashlib
import io
import sys
import tarfile

sys.stdout.reconfigure(encoding="utf-8")

DEB = r"packaging/generation-app_1.0.505_amd64.deb"
TARGETS = [
    "app/app/fuel/services/stations/stations_equipment_groups_services.py",
    "app/app/common/services/version_entity_resolve_services.py",
    "app/app/fuel/routes/fuel_routes.py",
]

with open(DEB, "rb") as fh:
    blob = fh.read()

# ar-архив: 8 байт magic, дальше записи по 60 байт заголовка
offset = 8
data = None
while offset + 60 <= len(blob):
    header = blob[offset : offset + 60]
    name = header[:16].decode("ascii", "replace").strip()
    size = int(header[48:58].decode("ascii", "replace").strip())
    start = offset + 60
    if name.startswith("data.tar"):
        data = blob[start : start + size]
        print("data member:", name, size)
    offset = start + size + (size % 2)

if data is None:
    print("data.tar не найден")
    sys.exit(1)

try:
    tar = tarfile.open(fileobj=io.BytesIO(data))
except Exception as exc:  # noqa: BLE001
    print("не удалось открыть data.tar:", exc)
    sys.exit(1)

with tar:
    names = {m.name.lstrip("./"): m for m in tar.getmembers() if m.isfile()}
    for target in TARGETS:
        member = names.get(target)
        if member is None:
            print(f"{target}: нет в пакете")
            continue
        content = tar.extractfile(member).read()
        print(f"{target}: sha256={hashlib.sha256(content).hexdigest()} len={len(content)}")
