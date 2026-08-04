# -*- coding: utf-8 -*-
import struct
from pathlib import Path

# Write a PowerShell script as UTF-16 LE with BOM so PowerShell parses Cyrillic correctly
ps = r'''
$ErrorActionPreference = 'Continue'
$connStr = 'Provider=Microsoft.ACE.OLEDB.16.0;Data Source=z:\НИО-10\АРМ ГС\БД Топливо\ОТЭТ.mdb;Persist Security Info=False;'
$conn = New-Object System.Data.OleDb.OleDbConnection($connStr)
$conn.Open()
$out = 'c:\arm_gs\_otet_analysis\columns'
New-Item -ItemType Directory -Force -Path $out | Out-Null
$tables = Get-Content 'c:\arm_gs\_otet_analysis\wanted_tables.txt' -Encoding UTF8
foreach ($t in $tables) {
  if ([string]::IsNullOrWhiteSpace($t)) { continue }
  try {
    $cmd = $conn.CreateCommand()
    $escaped = $t.Replace(']',']]')
    $cmd.CommandText = "SELECT TOP 1 * FROM [$escaped]"
    $r = $cmd.ExecuteReader()
    $lines = New-Object System.Collections.Generic.List[string]
    [void]$lines.Add("TABLE: $t")
    for ($i=0; $i -lt $r.FieldCount; $i++) {
      [void]$lines.Add(("{0}`t{1}`t{2}" -f ($i+1), $r.GetName($i), $r.GetDataTypeName($i)))
    }
    $r.Close()
    $safe = [regex]::Replace($t, '[\\/:*?"<>|]', '_')
    [System.IO.File]::WriteAllLines((Join-Path $out ($safe + '.txt')), $lines, [System.Text.UTF8Encoding]::new($false))
    Write-Output ("OK $t cols=$($lines.Count-1)")
  } catch {
    Write-Output ("FAIL $t : $($_.Exception.Message)")
  }
}

# Sample variants
try {
  $da = New-Object System.Data.OleDb.OleDbDataAdapter('SELECT * FROM [Список-вариантов]', $conn)
  $dt = New-Object System.Data.DataTable
  [void]$da.Fill($dt)
  $sb = New-Object System.Text.StringBuilder
  $cols = ($dt.Columns | ForEach-Object { $_.ColumnName }) -join "`t"
  [void]$sb.AppendLine($cols)
  foreach ($row in $dt.Rows) {
    $vals = @()
    foreach ($c in $dt.Columns) { $vals += [string]$row[$c] }
    [void]$sb.AppendLine(($vals -join "`t"))
  }
  [System.IO.File]::WriteAllText('c:\arm_gs\_otet_analysis\variants.tsv', $sb.ToString(), [System.Text.UTF8Encoding]::new($false))
  Write-Output ("variants rows=" + $dt.Rows.Count)
} catch { Write-Output ("FAIL variants: $($_.Exception.Message)") }

# Sample typical rates
try {
  $da = New-Object System.Data.OleDb.OleDbDataAdapter('SELECT TOP 30 * FROM [Типовые_удельные_расходы]', $conn)
  $dt = New-Object System.Data.DataTable
  [void]$da.Fill($dt)
  $sb = New-Object System.Text.StringBuilder
  $cols = ($dt.Columns | ForEach-Object { $_.ColumnName }) -join "`t"
  [void]$sb.AppendLine($cols)
  foreach ($row in $dt.Rows) {
    $vals = @()
    foreach ($c in $dt.Columns) { $vals += [string]$row[$c] }
    [void]$sb.AppendLine(($vals -join "`t"))
  }
  [System.IO.File]::WriteAllText('c:\arm_gs\_otet_analysis\typical_rates_sample.tsv', $sb.ToString(), [System.Text.UTF8Encoding]::new($false))
  Write-Output ("typical sample rows=" + $dt.Rows.Count)
} catch { Write-Output ("FAIL typical: $($_.Exception.Message)") }

# Current variant
try {
  $da = New-Object System.Data.OleDb.OleDbDataAdapter('SELECT * FROM [Текущий_вариант]', $conn)
  $dt = New-Object System.Data.DataTable
  [void]$da.Fill($dt)
  $sb = New-Object System.Text.StringBuilder
  $cols = ($dt.Columns | ForEach-Object { $_.ColumnName }) -join "`t"
  [void]$sb.AppendLine($cols)
  foreach ($row in $dt.Rows) {
    $vals = @()
    foreach ($c in $dt.Columns) { $vals += [string]$row[$c] }
    [void]$sb.AppendLine(($vals -join "`t"))
  }
  [System.IO.File]::WriteAllText('c:\arm_gs\_otet_analysis\current_variant.tsv', $sb.ToString(), [System.Text.UTF8Encoding]::new($false))
  Write-Output ("current variant rows=" + $dt.Rows.Count)
} catch { Write-Output ("FAIL current: $($_.Exception.Message)") }

# Startup properties via Access if needed - skip
# Sample station year range
try {
  $cmd = $conn.CreateCommand()
  $cmd.CommandText = 'SELECT Min(year) as ymin, Max(year) as ymax, Count(*) as cnt FROM [Станции2024]'
  $r = $cmd.ExecuteReader()
  $r.Read() | Out-Null
  Write-Output ("Станции2024 years=$($r['ymin'])..$($r['ymax']) cnt=$($r['cnt'])")
  $r.Close()
} catch { Write-Output ("FAIL stations2024: $($_.Exception.Message)") }

try {
  $cmd = $conn.CreateCommand()
  $cmd.CommandText = 'SELECT TOP 3 NAME, NUMB1120, Year, E, Q, QOTR, EWTP, EOTP, EURT, EUST, TUST, B, SNK, SNt, TURT, VED FROM [Станции2024] WHERE E>0 AND Year>=2020'
  $da = New-Object System.Data.OleDb.OleDbDataAdapter($cmd)
  $dt = New-Object System.Data.DataTable
  [void]$da.Fill($dt)
  $sb = New-Object System.Text.StringBuilder
  $cols = ($dt.Columns | ForEach-Object { $_.ColumnName }) -join "`t"
  [void]$sb.AppendLine($cols)
  foreach ($row in $dt.Rows) {
    $vals = @()
    foreach ($c in $dt.Columns) { $vals += [string]$row[$c] }
    [void]$sb.AppendLine(($vals -join "`t"))
  }
  [System.IO.File]::WriteAllText('c:\arm_gs\_otet_analysis\stations_sample.tsv', $sb.ToString(), [System.Text.UTF8Encoding]::new($false))
  Write-Output ("stations sample ok")
} catch { Write-Output ("FAIL stations sample: $($_.Exception.Message)") }

$conn.Close()
Write-Output DONE
'''

path = Path(r"c:\arm_gs\_otet_analysis\get_cols.ps1")
path.write_bytes(b"\xff\xfe" + ps.encode("utf-16-le"))
print("wrote", path)
