$ports = @(80,443,8000)
$pids = @()
foreach ($port in $ports) {
    Write-Host "=== Port $port ==="
    $lines = netstat -ano | Select-String ":$port " -SimpleMatch
    if ($lines) { $lines | ForEach-Object { $_.ToString() | Write-Host } ; $lines | ForEach-Object { $parts = ($_ -split '\s+'); $pids += $parts[-1] } } else { Write-Host "No entries" }
}
$pids = $pids | Sort-Object -Unique
foreach ($pid in $pids) { if ($pid) { Write-Host "PID: $pid"; try { Get-Process -Id $pid | Select-Object Id, ProcessName, Path | Format-List } catch { Write-Host "Process not found for PID $pid" } } }
