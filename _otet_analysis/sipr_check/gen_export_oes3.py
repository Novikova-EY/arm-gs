# -*- coding: utf-8 -*-
from pathlib import Path

ps = r'''
$ErrorActionPreference = "Stop"
$mdb = (Get-Content -LiteralPath "c:\arm_gs\_otet_analysis\sipr_check\mdb_path.txt" -Encoding UTF8 -Raw).Trim()
$conn = New-Object System.Data.OleDb.OleDbConnection("Provider=Microsoft.ACE.OLEDB.16.0;Data Source=$mdb;Persist Security Info=False;")
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
        $s = ([string]$v) -replace "`t"," " -replace "[\r\n]"," "
        [void]$vals.Add($s)
      }
    }
    [void]$sb.AppendLine(($vals -join "`t"))
  }
  [System.IO.File]::WriteAllText($path, $sb.ToString(), [System.Text.UTF8Encoding]::new($false))
  Write-Output ("OK $name rows=" + $dt.Rows.Count)
}

# Волгаэнерго oes=3, years 2024/2031 — ключевые поля для сверки Коэфф/Распред/Топливо
$stCols = "NAME,YEAR,NUST,NR,E,EWTP,Q,QOTR,H,HFIX,OBOR,VED,OBL,OES,NUMB1120,numb1,v,EOTP,EURT,EUST,TURT,TUST,B,GAZ,MAZUT,PROCH,UGOL,PECH,KUZN,KAN,URAL"
Export-Query "st_oes3_2024" ("SELECT $stCols FROM [Станции(Схема)] WHERE (oes=3) AND (ved>0) AND (year=2024)")
Export-Query "st_oes3_2031" ("SELECT $stCols FROM [Станции(Схема)] WHERE (oes=3) AND (ved>0) AND (year=2031)")

# Удельные для станций oes=3 (по numb1120 из станций 2031) — берём все строки с year<=2031
Export-Query "ud_oes3" "SELECT U.numb1120, U.v, U.year, U.y, U.snk, U.sntp, U.bk, U.btp, U.snbas, U.Ksn, U.bbas, U.Kh FROM [Удельные(Схема)] AS U INNER JOIN (SELECT DISTINCT numb1120 FROM [Станции(Схема)] WHERE oes=3 AND ved>0 AND year=2031) AS S ON U.numb1120=S.numb1120 WHERE U.year<=2031"

Export-Query "form_oes3" "SELECT F.numb1120, F.v, F.year, F.formtxt FROM [Формулы_топлива(Схема)] AS F INNER JOIN (SELECT DISTINCT numb1120 FROM [Станции(Схема)] WHERE oes=3 AND ved>0 AND year=2031) AS S ON F.numb1120=S.numb1120 WHERE F.year<=2031"

# доп угли schema + sample
$cmd = $conn.CreateCommand()
$cmd.CommandText = "SELECT TOP 1 * FROM [Доп_угли(Схема)]"
$r = $cmd.ExecuteReader()
$lines = New-Object System.Collections.Generic.List[string]
for ($i=0; $i -lt $r.FieldCount; $i++) { [void]$lines.Add($r.GetName($i)) }
$r.Close()
[System.IO.File]::WriteAllLines("c:\arm_gs\_otet_analysis\sipr_check\dop_schema.txt", $lines, [System.Text.UTF8Encoding]::new($false))
Write-Output ("dop_schema cols=" + $lines.Count)

Export-Query "dop_oes3_2031" "SELECT D.* FROM [Доп_угли(Схема)] AS D INNER JOIN (SELECT DISTINCT numb1 FROM [Станции(Схема)] WHERE oes=3 AND ved>0 AND year=2031) AS S ON D.numb1=S.numb1 WHERE D.year=2031"

Export-Query "restrictions" "SELECT * FROM [Ограничения]"

$conn.Close()
'''

Path(r"c:\arm_gs\_otet_analysis\sipr_check\export_oes3.ps1").write_text(ps, encoding="utf-8-sig")
print("wrote export_oes3.ps1")
