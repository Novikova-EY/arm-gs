# -*- coding: utf-8 -*-
from pathlib import Path

folder = Path(r"z:\НИО-10\АРМ ГС\БД Топливо")
target = None
for p in folder.glob("*.mdb"):
    # skip ОТЭТ; take the other large DB (~310MB)
    if p.stat().st_size > 250_000_000:
        target = p
        break
if target is None:
    raise SystemExit("target mdb not found")

print("target:", target)
Path(r"c:\arm_gs\_otet_analysis\target_mdb.txt").write_text(str(target), encoding="utf-8")

# Escape single quotes for PowerShell single-quoted string
mdb_ps = str(target).replace("'", "''")

ps = f'''
$ErrorActionPreference = 'Continue'
$mdb = '{mdb_ps}'
$outDir = 'c:\\arm_gs\\_otet_analysis\\toplivo_gs'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$vbaDir = Join-Path $outDir 'vba'
New-Item -ItemType Directory -Force -Path $vbaDir | Out-Null
$acc = New-Object -ComObject Access.Application
$acc.Visible = $false
$acc.OpenCurrentDatabase($mdb)
$db = $acc.CurrentDb()

$forms = New-Object System.Collections.Generic.List[string]
for ($i=0; $i -lt $acc.CurrentProject.AllForms.Count; $i++) {{
  [void]$forms.Add($acc.CurrentProject.AllForms.Item($i).Name)
}}
$modules = New-Object System.Collections.Generic.List[string]
for ($i=0; $i -lt $acc.CurrentProject.AllModules.Count; $i++) {{
  [void]$modules.Add($acc.CurrentProject.AllModules.Item($i).Name)
}}
[System.IO.File]::WriteAllLines((Join-Path $outDir 'forms.txt'), $forms, [System.Text.UTF8Encoding]::new($false))
[System.IO.File]::WriteAllLines((Join-Path $outDir 'modules.txt'), $modules, [System.Text.UTF8Encoding]::new($false))
Write-Output ("Forms=" + $forms.Count + " Modules=" + $modules.Count)

foreach ($m in $modules) {{
  $safe = [regex]::Replace($m, '[\\\\/:*?"<>|]', '_')
  try {{
    $acc.SaveAsText(5, $m, (Join-Path $vbaDir ("mod_" + $safe + ".txt")))
    Write-Output ("OK mod " + $m)
  }} catch {{ Write-Output ("FAIL mod " + $m + " : " + $_.Exception.Message) }}
}}

# Export ALL forms (needed to find Расчет by caption)
foreach ($f in $forms) {{
  $safe = [regex]::Replace($f, '[\\\\/:*?"<>|]', '_')
  try {{
    $acc.SaveAsText(2, $f, (Join-Path $vbaDir ("form_" + $safe + ".txt")))
    Write-Output ("OK form " + $f)
  }} catch {{ Write-Output ("FAIL form " + $f + " : " + $_.Exception.Message) }}
}}

$sb = New-Object System.Text.StringBuilder
foreach ($td in $db.TableDefs) {{
  if ($td.Connect -and $td.Connect.Length -gt 0) {{
    [void]$sb.AppendLine(($td.Name + "`t" + $td.Connect + "`t" + $td.SourceTableName))
  }} elseif ($td.Name -notlike 'MSys*') {{
    # local table names collected separately
  }}
}}
[System.IO.File]::WriteAllText((Join-Path $outDir 'links.txt'), $sb.ToString(), [System.Text.UTF8Encoding]::new($false))

$sb2 = New-Object System.Text.StringBuilder
foreach ($td in $db.TableDefs) {{
  if ($td.Name -notlike 'MSys*') {{ [void]$sb2.AppendLine($td.Name) }}
}}
[System.IO.File]::WriteAllText((Join-Path $outDir 'tables.txt'), $sb2.ToString(), [System.Text.UTF8Encoding]::new($false))

$acc.CloseCurrentDatabase()
$acc.Quit()
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($acc) | Out-Null
Write-Output DONE
'''

Path(r"c:\arm_gs\_otet_analysis\explore_toplivo_gs.ps1").write_bytes(
    b"\xff\xfe" + ps.encode("utf-16-le")
)
print("ps written ok")
