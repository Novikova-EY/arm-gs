#Requires -Version 5.1
# UTF-8: use this script with PowerShell; Cyrillic in .ps1 may break on PS 5.1 without BOM
<#
.SYNOPSIS
  Copy PostgreSQL from remote host to local using pg_dump + pg_restore.

.DESCRIPTION
  Set password before run:  $env:PGPASSWORD = '...'
  Or use -Password (secure prompt).
  Requires: pg_dump, pg_restore, psql on PATH.
#>
[CmdletBinding()]
param(
    [string] $RemoteHost = "10.31.205.27",
    [string] $LocalHost = "localhost",
    [int] $Port = 5432,
    [string] $Database = "gs_gen",
    [string] $User = "generation",
    [System.Security.SecureString] $Password,
    [string] $DumpDirectory = "",
    [switch] $DataOnly,
    [switch] $SkipRestore,
    [switch] $Force
)

$ErrorActionPreference = "Stop"

function Test-CommandExists {
    param([string] $Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

foreach ($cmd in @("pg_dump", "pg_restore", "psql")) {
    if (-not (Test-CommandExists $cmd)) {
        Write-Error "Not in PATH: $cmd. Install PostgreSQL client tools."
    }
}

if ($Password) {
    $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($Password)
    $env:PGPASSWORD = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
}
elseif (-not $env:PGPASSWORD) {
    Write-Host "Set `$env:PGPASSWORD first, or use -Password" -ForegroundColor Yellow
    $sec = Read-Host -AsSecureString "PostgreSQL password"
    $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
    $env:PGPASSWORD = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
}

if ($DumpDirectory -eq "") {
    $DumpDirectory = [System.IO.Path]::GetTempPath()
}
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$dumpFile = Join-Path $DumpDirectory "gs_gen_remote_${RemoteHost}_${stamp}.dump"

Write-Host "=== pg_dump from $RemoteHost -> $dumpFile ===" -ForegroundColor Cyan
$dumpArgs = @(
    "-h", $RemoteHost,
    "-p", "$Port",
    "-U", $User,
    "-d", $Database,
    "-Fc",
    "--no-owner",
    "--no-acl",
    "-f", $dumpFile
)
if ($DataOnly) {
    $dumpArgs += "--data-only"
}

& pg_dump @dumpArgs
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed with exit code $LASTEXITCODE" }

$sizeMb = [math]::Round((Get-Item $dumpFile).Length / 1MB, 2)
Write-Host "Dump file: $dumpFile ($sizeMb MB)" -ForegroundColor Green

if ($SkipRestore) {
    Write-Host "Skip restore (-SkipRestore). Dump path above." -ForegroundColor Yellow
    exit 0
}

Write-Host "=== pg_restore to $LocalHost / $Database ===" -ForegroundColor Cyan
if (-not $DataOnly) {
    Write-Host "Full dump: using --clean --if-exists on target (objects recreated)." -ForegroundColor Yellow
}
else {
    Write-Host "Data-only: schema on local must already match server." -ForegroundColor Yellow
}

if (-not $Force) {
    $r = Read-Host "Continue with restore? [y/N]"
    if ($r -notmatch '^[yY]') {
        Write-Host "Cancelled. Dump kept at: $dumpFile" -ForegroundColor Yellow
        exit 0
    }
}

$restoreArgs = @(
    "-h", $LocalHost,
    "-p", "$Port",
    "-U", $User,
    "-d", $Database,
    "--clean",
    "--if-exists",
    "--no-owner",
    "--no-acl",
    "-v",
    $dumpFile
)
if ($DataOnly) {
    $restoreArgs = @(
        "-h", $LocalHost,
        "-p", "$Port",
        "-U", $User,
        "-d", $Database,
        "--data-only",
        "--no-owner",
        "--no-acl",
        "-v",
        $dumpFile
    )
}

& pg_restore @restoreArgs
$code = $LASTEXITCODE
if ($code -ge 2) {
    throw "pg_restore failed with exit code $code"
}
Write-Host "Done. Use DB_HOST=localhost in .env for local app." -ForegroundColor Green
