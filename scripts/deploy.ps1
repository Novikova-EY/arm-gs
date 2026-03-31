# =============================================================================
# Скрипт автоматического деплоя generation-app на сервер
# =============================================================================
# Использование:
#   .\deploy.ps1 -Version 1.0.68                    # Указать версию явно
#   .\deploy.ps1 -Version 1.0.68 -SkipBuild        # Пропустить сборку (deb уже есть)
#   .\Deploy.ps1 -Version 1.0.68 -DeployOnly       # Только передача и установка
#   .\deploy.ps1                                   # Версия из git describe
#
# Переменные окружения (или .env.deploy):
#   DEPLOY_SERVER   - хост сервера (например 10.31.205.27)
#   DEPLOY_USER     - пользователь SSH (например novikova-eyu)
#   DEPLOY_PATH     - путь на сервере для .deb (по умолчанию /tmp)
# =============================================================================

param(
    [string]$Version = "",
    [switch]$SkipBuild,      # Не собирать deb заново
    [switch]$DeployOnly,     # Только SCP + установка (deb уже собран)
    [switch]$NoInstall       # Только SCP, не выполнять установку на сервере
)

$ErrorActionPreference = "Stop"
# Кодировка UTF-8 без BOM — иначе bash получает BOM в начале скрипта и «cd: команда не найдена»
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
$OutputEncoding = [Console]::OutputEncoding = $utf8NoBom
chcp 65001 | Out-Null
$ProjectRoot = Split-Path -Parent $PSScriptRoot

# --- Конфигурация ---
$DepEnvFile = Join-Path $ProjectRoot ".env.deploy"
if (Test-Path $DepEnvFile) {
    Get-Content $DepEnvFile | ForEach-Object {
        if ($_ -match "^\s*([^#][^=]*)=(.*)$") {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            Set-Item -Path "Env:$name" -Value $value -ErrorAction SilentlyContinue
        }
    }
}

$Server = $env:DEPLOY_SERVER
$User = $env:DEPLOY_USER
$RemotePath = if ($env:DEPLOY_PATH) { $env:DEPLOY_PATH } else { "/tmp" }

if (-not $Server -or -not $User) {
    Write-Host "Ошибка: задайте DEPLOY_SERVER и DEPLOY_USER" -ForegroundColor Red
    Write-Host "Пример: создать .env.deploy в корне проекта:" -ForegroundColor Yellow
    Write-Host "  DEPLOY_SERVER=10.31.205.27" -ForegroundColor Gray
    Write-Host "  DEPLOY_USER=novikova-eyu" -ForegroundColor Gray
    exit 1
}

# --- Определение версии ---
if (-not $Version) {
    try {
        $gitOut = git -C $ProjectRoot describe --tags --dirty --always 2>$null
        if ($gitOut) {
            $Version = $gitOut.Trim() -replace '/', '-'
        }
    } catch {}
    if (-not $Version) {
        $Version = Get-Date -Format "yyyy.MM.dd"
    }
}

$DebName = "generation-app_${Version}_amd64.deb"
$DebPath = Join-Path (Join-Path $ProjectRoot "packaging") $DebName

# --- 1. Сборка deb (если нужно) ---
if (-not $DeployOnly) {
    if (-not $SkipBuild) {
        Write-Host "[1/4] Сборка Docker-образа..." -ForegroundColor Cyan
        docker build -t arm-gs-deb $ProjectRoot
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

        Write-Host "[2/4] Сборка .deb пакета (версия $Version)..." -ForegroundColor Cyan
        docker run --rm -v "${ProjectRoot}:/app" arm-gs-deb --version $Version
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    } else {
        Write-Host "[1-2/4] Пропуск сборки (--SkipBuild)" -ForegroundColor Gray
    }

    if (-not (Test-Path $DebPath)) {
        Write-Host "Ошибка: не найден пакет $DebPath" -ForegroundColor Red
        exit 1
    }
} else {
    if (-not (Test-Path $DebPath)) {
        Write-Host "Ошибка: --DeployOnly указан, но $DebName не найден" -ForegroundColor Red
        exit 1
    }
    Write-Host "[1-2/4] DeployOnly: используем существующий пакет" -ForegroundColor Gray
}

# --- 2. Копирование на сервер ---
Write-Host "[3/4] Передача пакета на $User@$Server ..." -ForegroundColor Cyan
scp $DebPath "${User}@${Server}:${RemotePath}/"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# --- 3. Установка на сервере ---
if (-not $NoInstall) {
    Write-Host "[4/4] Установка и миграции на сервере..." -ForegroundColor Cyan
    $RemoteDeb = "${RemotePath}/${DebName}"
    # Миграции выполняем от пользователя generation-app — он может читать /etc/generation-app/app.env
    # merge heads — объединяет несколько веток миграций (иначе "Multiple head revisions"); при одном head — безопасно игнорируем
    # upgrade до head. Fallback: если в БД старая/несуществующая ревизия — stamp к базовой (5f943277b415) и upgrade
    $Commands = @"
set -e
cd /tmp
sudo dpkg -i $RemoteDeb || sudo apt -f install -y
sudo -u generation-app bash -c 'set -a; [ -f /etc/generation-app/app.env ] && . /etc/generation-app/app.env; set +a; cd /opt/generation-app/app && source /opt/generation-app/venv/bin/activate && export FLASK_APP=run.py FLASK_ENV=production && (flask db merge heads -m "merge heads" 2>/dev/null || true) && (flask db upgrade || (flask db stamp 5f943277b415 && flask db upgrade))'
sudo systemctl restart generation-app
sudo nginx -t 2>/dev/null && sudo systemctl reload nginx 2>/dev/null || true
echo 'Deploy complete. Checking service...'
sudo systemctl status generation-app --no-pager
"@

    # Запись в файл и передача через cmd — избегаем BOM при pipe из PowerShell
    # CRLF -> LF: bash на Linux интерпретирует \r как часть команды (cd /tmp\r, upgrade\r и т.д.)
    $scriptText = $Commands.Replace("`r`n", "`n").Replace("`r", "`n").TrimStart([char]0xFEFF)
    $tempFile = Join-Path $env:TEMP "deploy_$([Guid]::NewGuid().ToString('N')).sh"
    $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText($tempFile, $scriptText, $utf8NoBom)
    try {
        cmd /c "ssh `"${User}@${Server}`" `"bash -s`" < `"$tempFile`""
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    } finally {
        Remove-Item $tempFile -Force -ErrorAction SilentlyContinue
    }
    Write-Host "`nDone. Version $Version deployed." -ForegroundColor Green
} else {
    Write-Host ('[4/4] Install skipped (-NoInstall). Package copied to ' + $RemotePath + '/') -ForegroundColor Gray
}
