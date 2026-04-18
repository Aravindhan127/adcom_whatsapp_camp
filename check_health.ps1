$urls = @('http://localhost/api/health/summary','http://127.0.0.1/api/health/summary','http://localhost:80/api/health/summary','http://127.0.0.1:8000/api/health/summary','http://localhost:8000/api/health/summary')
foreach ($u in $urls) {
    Write-Host "--- Testing $u ---"
    try {
        $r = Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        Write-Host "STATUS: $($r.StatusCode)"
        Write-Host $r.Content
        break
    } catch {
        Write-Host "FAILED: $($_.Exception.Message)"
    }
}
