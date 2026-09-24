$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false
$wb = $excel.Workbooks.Open('c:\arm_gs\_tmp_ot_calc.xls', $false, $true)
$out = New-Object System.Text.StringBuilder

function Dump-Sheet($sh, $tag) {
  [void]$out.AppendLine(("==== {0} name={1} ====" -f $tag, $sh.Name))
  $used = $sh.UsedRange
  [void]$out.AppendLine(("USED rows={0} cols={1}" -f $used.Rows.Count, $used.Columns.Count))
  $maxR = [Math]::Min(95, $used.Rows.Count)
  $maxC = [Math]::Min(30, $used.Columns.Count)
  for ($r=1; $r -le $maxR; $r++) {
    $vals = @()
    for ($c=1; $c -le $maxC; $c++) {
      $cell = $sh.Cells.Item($r,$c)
      $txt = [string]$cell.Text
      $fill = [int64]$cell.Interior.Color
      $font = [int64]$cell.Font.Color
      $comment = ''
      try {
        if ($cell.Comment) { $comment = [string]$cell.Comment.Text() }
      } catch {}
      $vals += ("[{0}:{1}|f={2}|fn={3}|c={4}]" -f $c, $txt, $fill, $font, $comment)
    }
    [void]$out.AppendLine(("R{0}: {1}" -f $r, ($vals -join ' ')))
  }
  [void]$out.AppendLine('VALIDATIONS:')
  $seen = @{}
  for ($r=1; $r -le $maxR; $r++) {
    for ($c=1; $c -le $maxC; $c++) {
      $cell = $sh.Cells.Item($r,$c)
      try {
        $dv = $cell.Validation
        $formula = [string]$dv.Formula1
        if ($formula) {
          $key = "{0}|{1}|{2}" -f $c, $dv.Type, $formula
          if (-not $seen.ContainsKey($key)) {
            $seen[$key] = $true
            [void]$out.AppendLine(("VAL r={0} c={1} type={2} formula={3} value={4}" -f $r,$c,$dv.Type,$formula,$cell.Text))
          }
        }
      } catch {}
    }
  }
}

Dump-Sheet $wb.Worksheets.Item(1) 'SPR'
# Хар.топл. is sheet 4
Dump-Sheet $wb.Worksheets.Item(4) 'KHAR'

# dump extra far-right / far-down cells on spravochnik that might be the list
$sh = $wb.Worksheets.Item(1)
[void]$out.AppendLine('FAR_CELLS:')
for ($r=1; $r -le 120; $r++) {
  for ($c=16; $c -le 30; $c++) {
    $txt = [string]$sh.Cells.Item($r,$c).Text
    if ($txt) {
      [void]$out.AppendLine(("FAR r={0} c={1} v={2}" -f $r,$c,$txt))
    }
  }
}

$path = 'c:\arm_gs\_tmp_spravochnik_full.txt'
[System.IO.File]::WriteAllText($path, $out.ToString(), [System.Text.UTF8Encoding]::new($false))
$wb.Close($false)
$excel.Quit()
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($wb) | Out-Null
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($excel) | Out-Null
Write-Output "wrote $path"
