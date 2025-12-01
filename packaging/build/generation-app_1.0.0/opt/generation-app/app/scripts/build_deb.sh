#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_ROOT="${PROJECT_ROOT}/build/deb"
PKG_NAME="generation-app"
VERSION="${1:-$(git describe --tags --always | tr -d 'v')}"
ARCH="amd64"
STAGING="${BUILD_ROOT}/${PKG_NAME}_${VERSION}"

echo "[+] Building ${PKG_NAME} version ${VERSION}"

rm -rf "${BUILD_ROOT}"
mkdir -p "${STAGING}"

copy_app_sources() {
    local dst="${STAGING}/opt/generation-app/app"
    mkdir -p "${dst}"
    rsync -a \
        --exclude '.git' \
        --exclude 'build' \
        --exclude 'venv' \
        --exclude '__pycache__' \
        --exclude '*.pyc' \
        --exclude 'uploads/documents_kommod' \
        "${PROJECT_ROOT}/" "${dst}/"
}

copy_static_files() {
    rsync -a "${PROJECT_ROOT}/packaging/deb/" "${STAGING}/"
}

patch_control_file() {
    local control="${STAGING}/DEBIAN/control"
    sed -i "s/__VERSION__/${VERSION}/g" "${control}"
}

set_permissions() {
    find "${STAGING}/DEBIAN" -type f -exec chmod 755 {} \;
    chmod 644 "${STAGING}/lib/systemd/system/generation-app.service"
    chmod 644 "${STAGING}/usr/lib/tmpfiles.d/generation-app.conf"
    chmod 644 "${STAGING}/usr/share/generation-app/app.env.example"
}

build_package() {
    fakeroot dpkg-deb --build "${STAGING}" "${BUILD_ROOT}"
    echo "[+] Package created: ${BUILD_ROOT}/${PKG_NAME}_${VERSION}.deb"
}

copy_app_sources
copy_static_files
patch_control_file
set_permissions
build_package





