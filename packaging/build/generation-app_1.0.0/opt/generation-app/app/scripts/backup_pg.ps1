# backup_pg.ps1  (ASCII, no Cyrillic, no reserved names)
param(
  [string]$DbName      = "arm_gs",
  [string]$DbHost      = "localhost",
  [int]   $DbPort      = 5432,
  [string]$DbUser      = "postgres",
  [string]$BackupDir   = "C:\fproject\backup",
  [string[]]$Schemas   = @('auth','logs','refdata','generation'),     # e.g. @('auth','logs','refdata','generation')
  [switch]$SchemaOnly,            # dump schema only (no data)
  [switch]$DataOnly,              # dump data only (no DDL)
  [int]$RetentionDays = 14,       # keep dumps for N days
  [string]$PgBin       = "C:\Program Files\PostgreSQL\17\bin"  # path to pg_dump.exe
)

# --- Checks ---
if (-not (Test-Path $PgBin)) { throw "PgBin folder not found: $PgBin" }
$pgDump = Join-Path $PgBin "pg_dump.exe"
if (-not (Test-Path $pgDump)) { throw "pg_dump.exe not found at: $pgDump" }

# --- Ensure backup directory exists ---
if (-not (Test-Path $BackupDir)) { New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null }

# --- Read password securely ---
$sec = Read-Host "Enter password for user $DbUser" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
try {
  $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto($ptr)
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}
$env:PGPASSWORD = $plain

# --- Compose output file name ---
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$mode =
  if ($SchemaOnly) { "schema" }
  elseif ($DataOnly) { "data" }
  elseif ($Schemas.Count -gt 0) { "schemas" }
  else { "full" }

# Append small schemas list to name for readability
$schemaname = ""
if ($Schemas.Count -gt 0 -and $Schemas.Count -le 4) {
  $schemaname = "_" + ($Schemas -join "-")
}

$backupFile = Join-Path $BackupDir "$($DbName)_$mode$schemaname_$ts.dump"

# --- Build pg_dump args ---
$args = @("-h", $DbHost, "-p", $DbPort, "-U", $DbUser, "-d", $DbName, "-Fc", "-f", $backupFile)
if ($SchemaOnly) { $args += "--schema-only" }
if ($DataOnly)   { $args += "--data-only"   }
foreach ($s in $Schemas) { $args += @("-n", $s) }

# --- Run pg_dump ---
Write-Host "Starting pg_dump -> $backupFile"
& $pgDump @args
$code = $LASTEXITCODE

# --- Cleanup password from environment ---
$env:PGPASSWORD = $null
Remove-Variable plain -ErrorAction SilentlyContinue
if ($sec) { $sec.Dispose() }

if ($code -ne 0) {
  throw "pg_dump exited with code $code"
}

# --- Retention policy ---
if ($RetentionDays -gt 0) {
  Get-ChildItem -Path $BackupDir -Filter "$DbName*.dump" |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$RetentionDays) } |
    Remove-Item -Force -ErrorAction SilentlyContinue
}

Write-Host "Done: $backupFile"
