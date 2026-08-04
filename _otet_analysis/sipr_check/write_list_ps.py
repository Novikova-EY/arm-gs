# -*- coding: utf-8 -*-
"""List tables in target Access MDB via ACE OLEDB."""
from pathlib import Path

mdb = r"c:\Users\novikova-eyu\Desktop\!!!Работа\АРМ ГС_на компе\БД Топливо\БД Гурьева А.Ю\СиПР ЭЭС_2031_4 этап.mdb"
out_dir = Path(r"c:\arm_gs\_otet_analysis\sipr_check")
out_dir.mkdir(parents=True, exist_ok=True)

ps = rf'''
$ErrorActionPreference = 'Stop'
$mdb = @'
{mdb}
'@
$connStr = "Provider=Microsoft.ACE.OLEDB.16.0;Data Source=$mdb;Persist Security Info=False;"
try {{
  $conn = New-Object System.Data.OleDb.OleDbConnection($connStr)
  $conn.Open()
}} catch {{
  $connStr = "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=$mdb;Persist Security Info=False;"
  $conn = New-Object System.Data.OleDb.OleDbConnection($connStr)
  $conn.Open()
}}
$schema = $conn.GetOleDbSchemaTable([System.Data.OleDb.OleDbSchemaGuid]::Tables, @($null,$null,$null,'TABLE'))
$names = @()
foreach ($row in $schema.Rows) {{ $names += [string]$row['TABLE_NAME'] }}
$names = $names | Sort-Object
[System.IO.File]::WriteAllLines(@'
{out_dir / "tables.txt"}
'@, $names, [System.Text.UTF8Encoding]::new($false))
Write-Output ("tables=" + $names.Count)
Write-Output ($names -join "`n")
$conn.Close()
'''

ps_path = out_dir / "list_tables.ps1"
ps_path.write_text(ps, encoding="utf-8")
print("wrote", ps_path)
