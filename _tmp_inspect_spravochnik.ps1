$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false
$wb = $excel.Workbooks.Open('c:\arm_gs\_tmp_ot_calc.xls', $false, $true)
$out = New-Object System.Text.StringBuilder
[void]$out.AppendLine("FILE OK")
foreach ($shItem in $wb.Worksheets) {
  [void]$out.AppendLine("SHEET: $($shItem.Name)")
}
$sh = $wb.Worksheets.Item(1)
[void]$out.AppendLine("TARGET: $($sh.Name)")
$used = $sh.UsedRange
[void]$out.AppendLine("USED rows=$($used.Rows.Count) cols=$($used.Columns.Count) startR=$($used.Row) startC=$($used.Column)")
$maxR = [Math]::Min(6, $used.Rows.Count)
$maxC = [Math]::Min(25, $used.Columns.Count)
for ($r=1; $r -le $maxR; $r++) {
  $vals = @()
  for ($c=1; $c -le $maxC; $c++) {
    $vals += [string]$sh.Cells.Item($r,$c).Text
  }
  [void]$out.AppendLine(("ROW{0}: {1}" -f $r, ($vals -join ' | ')))
}
[void]$out.AppendLine('HEADERS:')
for ($c=1; $c -le $used.Columns.Count; $c++) {
  $h = @()
  for ($r=1; $r -le 4; $r++) { $h += [string]$sh.Cells.Item($r,$c).Text }
  [void]$out.AppendLine(("C{0}: {1}" -f $c, ($h -join ' || ')))
}

[void]$out.AppendLine('VALIDATIONS:')
$seen = @{}
$maxScanR = [Math]::Min(90, $used.Rows.Count)
$maxScanC = [Math]::Min(22, $used.Columns.Count)
for ($r=1; $r -le $maxScanR; $r++) {
  for ($c=1; $c -le $maxScanC; $c++) {
    $cell = $sh.Cells.Item($r,$c)
    try {
      $dv = $cell.Validation
      $formula = [string]$dv.Formula1
      if ($formula) {
        $key = "{0}|{1}|{2}" -f $c, $dv.Type, $formula
        if (-not $seen.ContainsKey($key)) {
          $seen[$key] = $true
          $hdr = [string]$sh.Cells.Item(1,$c).Text
          if (-not $hdr) { $hdr = [string]$sh.Cells.Item(2,$c).Text }
          [void]$out.AppendLine(("VAL r={0} c={1} hdr={2} type={3} formula={4} value={5}" -f $r,$c,$hdr,$dv.Type,$formula,$cell.Text))
        }
      }
    } catch {}
  }
}

[void]$out.AppendLine('COLORS_COL_A:')
for ($r=1; $r -le [Math]::Min(95, $used.Rows.Count); $r++) {
  $cell = $sh.Cells.Item($r,1)
  $txt = [string]$cell.Text
  if (-not $txt) { continue }
  $fill = [int64]$cell.Interior.Color
  $font = [int64]$cell.Font.Color
  [void]$out.AppendLine(("r={0} text={1} fill={2} font={3} pattern={4}" -f $r,$txt,$fill,$font,$cell.Interior.Pattern))
}

# named ranges that might hold dropdown lists
[void]$out.AppendLine('NAMES:')
foreach ($nm in $wb.Names) {
  try {
    [void]$out.AppendLine(("NAME {0} = {1}" -f $nm.Name, $nm.RefersTo))
  } catch {}
}

$path = 'c:\arm_gs\_tmp_spravochnik_inspect.txt'
[System.IO.File]::WriteAllText($path, $out.ToString(), [System.Text.UTF8Encoding]::new($false))
$wb.Close($false)
$excel.Quit()
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($wb) | Out-Null
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($excel) | Out-Null
Write-Output "wrote $path"
