# -*- coding: utf-8 -*-
"""Get columns for key tables via ACE OLEDB."""
import csv
from pathlib import Path

try:
    import win32com.client  # noqa
except ImportError:
    pass

import subprocess
import sys

# Use PowerShell with ADO Recordset OpenSchema via Python COM is hard without pywin32.
# Use adodbapi or just powershell one-table-at-a-time with properly encoded script file.

tables = [
    "Типовые_удельные_расходы",
    "Удельные(архив)",
    "Удельные2024",
    "Нормативные удельные",
    "Перет-коэфф",
    "Список-вариантов",
    "Текущий_вариант",
    "Станции2024",
    "KOEFF",
    "main",
    "work",
    "sumvar",
    "Удельные нового и  модерн оборуд",
]

ps = r'''
$ErrorActionPreference = 'Stop'
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
    $cmd.CommandText = 'SELECT TOP 1 * FROM [' + $t.Replace(']',']]') + ']'
    $r = $cmd.ExecuteReader()
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("TABLE: $t")
    for ($i=0; $i -lt $r.FieldCount; $i++) {
      $lines.Add(("{0}`t{1}`t{2}" -f ($i+1), $r.GetName($i), $r.GetDataTypeName($i)))
    }
    $r.Close()
    $safe = ($t -replace '[\\/:*?"<>|]', '_')
    [System.IO.File]::WriteAllLines((Join-Path $out ($safe + '.txt')), $lines, [System.Text.UTF8Encoding]::new($false))
    Write-Output ("OK " + $t + " cols=" + $lines.Count)
  } catch {
    Write-Output ("FAIL " + $t + " : " + $_.Exception.Message)
  }
}
$conn.Close()
'''

Path(r"c:\arm_gs\_otet_analysis\wanted_tables.txt").write_text("\n".join(tables), encoding="utf-8")
Path(r"c:\arm_gs\_otet_analysis\get_cols.ps1").write_text(ps, encoding="utf-8")
print("script written")
