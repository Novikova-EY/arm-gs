$ErrorActionPreference = 'Stop'
$mdb = Get-Content -LiteralPath 'c:\arm_gs\_otet_analysis\sipr_check\mdb_path.txt' -Encoding UTF8 -Raw
$mdb = $mdb.Trim()
$out = 'c:\arm_gs\_otet_analysis\sipr_check\tables.txt'
Write-Output "MDB=$mdb"
Write-Output "Exists=$([System.IO.File]::Exists($mdb))"

$providers = @(
  'Microsoft.ACE.OLEDB.16.0',
  'Microsoft.ACE.OLEDB.12.0',
  'Microsoft.Jet.OLEDB.4.0'
)
$conn = $null
$lastErr = $null
foreach ($p in $providers) {
  try {
    $connStr = "Provider=$p;Data Source=$mdb;Persist Security Info=False;"
    $conn = New-Object System.Data.OleDb.OleDbConnection($connStr)
    $conn.Open()
    Write-Output "Opened with $p"
    break
  } catch {
    $lastErr = $_.Exception.Message
    Write-Output "Fail $p : $lastErr"
    $conn = $null
  }
}
if ($null -eq $conn) { throw "Cannot open MDB: $lastErr" }

$schema = $conn.GetOleDbSchemaTable([System.Data.OleDb.OleDbSchemaGuid]::Tables, @($null,$null,$null,'TABLE'))
$names = New-Object System.Collections.Generic.List[string]
foreach ($row in $schema.Rows) { [void]$names.Add([string]$row['TABLE_NAME']) }
$sorted = $names | Sort-Object
[System.IO.File]::WriteAllLines($out, $sorted, [System.Text.UTF8Encoding]::new($false))
Write-Output ("tables=" + $sorted.Count)
$sorted | Select-Object -First 80 | ForEach-Object { Write-Output $_ }
$conn.Close()
