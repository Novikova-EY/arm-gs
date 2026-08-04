# -*- coding: utf-8 -*-
from pathlib import Path

ps = r'''
$ErrorActionPreference = "Stop"
$mdb = (Get-Content -LiteralPath "c:\arm_gs\_otet_analysis\sipr_check\mdb_path.txt" -Encoding UTF8 -Raw).Trim()
$connStr = "Provider=Microsoft.ACE.OLEDB.16.0;Data Source=$mdb;Persist Security Info=False;"
$conn = New-Object System.Data.OleDb.OleDbConnection($connStr)
$conn.Open()

function Export-Query([string]$name, [string]$sql) {
  $cmd = $conn.CreateCommand()
  $cmd.CommandText = $sql
  $adapter = New-Object System.Data.OleDb.OleDbDataAdapter($cmd)
  $dt = New-Object System.Data.DataTable
  [void]$adapter.Fill($dt)
  $path = "c:\arm_gs\_otet_analysis\sipr_check\$name.csv"
  $sb = New-Object System.Text.StringBuilder
  $cols = New-Object System.Collections.Generic.List[string]
  foreach ($c in $dt.Columns) { [void]$cols.Add($c.ColumnName) }
  [void]$sb.AppendLine(($cols -join "`t"))
  foreach ($row in $dt.Rows) {
    $vals = New-Object System.Collections.Generic.List[string]
    foreach ($c in $dt.Columns) {
      $v = $row[$c]
      if ($v -is [DBNull]) { [void]$vals.Add("") }
      else {
        $s = [string]$v
        $s = $s -replace "`t", " " -replace "[\r\n]", " "
        [void]$vals.Add($s)
      }
    }
    [void]$sb.AppendLine(($vals -join "`t"))
  }
  [System.IO.File]::WriteAllText($path, $sb.ToString(), [System.Text.UTF8Encoding]::new($false))
  Write-Output ("OK $name rows=" + $dt.Rows.Count + " cols=" + $dt.Columns.Count)
}

Export-Query "params" "SELECT * FROM [Параметры-распределения]"
try { Export-Query "tek_var" "SELECT * FROM [Текущий_вариант]" } catch { Write-Output ("FAIL tek_var: " + $_.Exception.Message) }
try { Export-Query "spisok_var" "SELECT * FROM [Список-вариантов]" } catch { Write-Output ("FAIL spisok_var: " + $_.Exception.Message) }

$cmd = $conn.CreateCommand()
$cmd.CommandText = "SELECT TOP 1 * FROM [Станции(Схема)]"
$r = $cmd.ExecuteReader()
$lines = New-Object System.Collections.Generic.List[string]
for ($i=0; $i -lt $r.FieldCount; $i++) { [void]$lines.Add(("{0}`t{1}" -f $r.GetName($i), $r.GetDataTypeName($i))) }
$r.Close()
[System.IO.File]::WriteAllLines("c:\arm_gs\_otet_analysis\sipr_check\stations_schema.txt", $lines, [System.Text.UTF8Encoding]::new($false))
Write-Output ("stations_schema cols=" + $lines.Count)

Export-Query "stations_year_counts" "SELECT year, Count(*) AS n FROM [Станции(Схема)] GROUP BY year ORDER BY year"
Export-Query "udeln_year_counts" "SELECT year, Count(*) AS n FROM [Удельные(Схема)] GROUP BY year ORDER BY year"
Export-Query "formula_year_counts" "SELECT year, Count(*) AS n FROM [Формулы_топлива(Схема)] GROUP BY year ORDER BY year"

$conn.Close()
'''

Path(r"c:\arm_gs\_otet_analysis\sipr_check\export_meta.ps1").write_text(ps, encoding="utf-8-sig")
print("ok")
