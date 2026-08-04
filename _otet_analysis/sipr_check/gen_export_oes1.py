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

$stCols = "NAME,YEAR,NUST,NR,E,EWTP,Q,QOTR,H,HFIX,OBOR,VED,OBL,OES,NUMB1120,numb1,v"
Export-Query "st_oes1_2024" ("SELECT $stCols FROM [Станции(Схема)] WHERE (oes=1) AND (ved>0) AND (year=2024)")
Export-Query "st_oes1_2026" ("SELECT $stCols FROM [Станции(Схема)] WHERE (oes=1) AND (ved>0) AND (year=2026)")

$conn.Close()
'''

Path(r"c:\arm_gs\_otet_analysis\sipr_check\export_oes1.ps1").write_text(ps, encoding="utf-8-sig")
print("wrote export_oes1.ps1")
