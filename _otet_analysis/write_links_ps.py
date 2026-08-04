# -*- coding: utf-8 -*-
from pathlib import Path

ps = r'''
$ErrorActionPreference = 'Continue'
$mdb = 'z:\НИО-10\АРМ ГС\БД Топливо\ОТЭТ.mdb'
$acc = New-Object -ComObject Access.Application
$acc.Visible = $false
try {
  $acc.OpenCurrentDatabase($mdb)
} catch {
  # already open exclusively? try anyway
  Write-Output ("Open error: " + $_.Exception.Message)
  $acc.OpenCurrentDatabase($mdb)
}
$db = $acc.CurrentDb()
$sb = New-Object System.Text.StringBuilder
foreach ($td in $db.TableDefs) {
  $c = $td.Connect
  if ($c -and $c.Length -gt 0) {
    [void]$sb.AppendLine(($td.Name + "`t" + $c + "`t" + $td.SourceTableName))
  }
}
[void]$sb.AppendLine("===QUERIES with Схема===")
foreach ($q in $db.QueryDefs) {
  if ($q.Name -match 'Схем|Рабоч|коэфф|распред|формул') {
    [void]$sb.AppendLine($q.Name)
  }
}
[System.IO.File]::WriteAllText('c:\arm_gs\_otet_analysis\links.txt', $sb.ToString(), [System.Text.UTF8Encoding]::new($false))
$acc.CloseCurrentDatabase()
$acc.Quit()
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($acc) | Out-Null
Write-Output DONE
'''
Path(r"c:\arm_gs\_otet_analysis\get_links.ps1").write_bytes(b"\xff\xfe" + ps.encode("utf-16-le"))
print("ok")
