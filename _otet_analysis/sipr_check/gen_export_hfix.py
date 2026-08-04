# -*- coding: utf-8 -*-
"""Generate PowerShell export of HFIX=1 from Access, then apply to ARM."""
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

Export-Query "hfix_all" "SELECT NUMB1120, [Year] AS YearN, H, HFIX, NUST, OES FROM [Станции(Схема)] WHERE (HFIX=1) AND ([Year] Is Not Null) AND (NUMB1120 Is Not Null) ORDER BY [Year], NUMB1120"

$conn.Close()
'''

Path(r"c:\arm_gs\_otet_analysis\sipr_check\export_hfix.ps1").write_text(ps, encoding="utf-8-sig")
print("wrote export_hfix.ps1")
