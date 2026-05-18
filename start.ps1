# ============================================================
# Adcom Standalone - Full Stack Startup Script
# Run this from: c:\Office_Work\Adcom\Adcom_Standalone
# Usage: .\start.ps1
# ============================================================

$BackendDir = "$PSScriptRoot\backend"
$FrontendDir = "$PSScriptRoot\frontend"
$EnvFile = "$BackendDir\.env"

# Allow skipping Redis checks/dashboard when set in environment (use SKIP_REDIS_CHECK=1)
$SkipRedisCheck = $env:SKIP_REDIS_CHECK -eq '1'

# Load Redis URL from .env
$RedisUrl = "redis://127.0.0.1:6379/0" # Fallback
if (Test-Path $EnvFile) {
    $line = Get-Content $EnvFile | Select-String "^REDIS_URL=" | Select-Object -First 1
    if ($line) {
        $RedisUrl = ($line.ToString() -split "=", 2)[1].Trim()
    }
}

Write-Host ""
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "  ADCOM STARTUP (REMOTE REDIS MODE)" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

# Step 1: Verify Remote Redis Connection (optional)
Write-Host ""
# Prefer virtualenv Python inside backend if available
$VenvPython = Join-Path -Path $BackendDir -ChildPath ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    $PythonExe = $VenvPython
    Write-Host "Using venv Python: $PythonExe" -ForegroundColor Green
} else {
    $PythonExe = "python"
    Write-Host "Using system Python: python" -ForegroundColor Yellow
}
if (-not $SkipRedisCheck) {
    Write-Host "[1/6] Verifying Remote Redis Connection..." -ForegroundColor Yellow
    Write-Host "      URL: $RedisUrl" -ForegroundColor Gray

    # Wait for Redis to be ready
    Write-Host "      Waiting for Redis to be ready..." -ForegroundColor Gray
    $maxWait = 20
    $waited = 0
    $ping = "False"
    do {
        Start-Sleep 1
        $waited++
        try {
            $ping = & $PythonExe -c "import redis; r=redis.from_url('$RedisUrl'); print(r.ping())" 2>$null
        } catch {
            $ping = "False"
        }
    } while ($ping -ne "True" -and $waited -lt $maxWait)

    if ($ping -ne "True") {
        Write-Host "WARNING: Redis did not respond after $maxWait seconds. Continuing startup (Redis may already be running or unreachable)." -ForegroundColor Yellow
    } else {
        Write-Host "      Redis is ready!" -ForegroundColor Green
    }
} else {
    Write-Host "[1/6] Skipping Redis readiness check (SKIP_REDIS_CHECK=1)." -ForegroundColor Cyan
}

# Step 2: Start Celery Worker
Write-Host ""
Write-Host "[2/6] Starting Celery Worker..." -ForegroundColor Yellow
    $celery = Start-Process -PassThru -FilePath $PythonExe `
    -ArgumentList "-m", "celery", "-A", "app.core.celery_app", "worker", "--loglevel=info", "--pool=solo" `
    -WorkingDirectory $BackendDir `
    -WindowStyle Normal

Start-Sleep 4

if ($celery.HasExited) {
    Write-Host "ERROR: Celery worker failed to start (exit code $($celery.ExitCode))." -ForegroundColor Red
    exit 1
}
Write-Host "      Celery worker PID: $($celery.Id)" -ForegroundColor Green

# Step 3: Start Celery Beat (Scheduler - Required for scheduled campaigns)
Write-Host ""
Write-Host "[3/6] Starting Celery Beat (Scheduler)..." -ForegroundColor Yellow
    $beat = Start-Process -PassThru -FilePath $PythonExe `
    -ArgumentList "-m", "celery", "-A", "app.core.celery_app", "beat", "--loglevel=info" `
    -WorkingDirectory $BackendDir `
    -WindowStyle Normal

Start-Sleep 3

if ($beat.HasExited) {
    Write-Host "WARNING: Celery Beat exited early (exit code $($beat.ExitCode)). Scheduled campaigns may not fire." -ForegroundColor Yellow
} else {
    Write-Host "      Celery Beat PID: $($beat.Id) (Checks for scheduled campaigns every 60s)" -ForegroundColor Green
}

# Step 4: Start Backend (Uvicorn)
Write-Host ""
Write-Host "[4/6] Starting Backend API (uvicorn)..." -ForegroundColor Yellow

$SSLCert = "C:\ssl\www_ttcitaloraa_shop.crt"
$SSLKey  = "C:\ssl\www_ttcitaloraa_shop.key"
$SSLAvailable = (Test-Path $SSLCert) -and (Test-Path $SSLKey)

if ($SSLAvailable) {
    Write-Host "      SSL detected - Starting HTTPS on port 443 + HTTP redirect on port 80" -ForegroundColor Cyan
    # Port 80 HTTP -> HTTPS redirect (background)
    $redirect = Start-Process -PassThru -FilePath $PythonExe `
        -ArgumentList "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80" `
        -WorkingDirectory $BackendDir `
        -WindowStyle Minimized
    Write-Host "      HTTP Redirect PID: $($redirect.Id)" -ForegroundColor Green

    # Port 443 HTTPS main app
    $backend = Start-Process -PassThru -FilePath $PythonExe `
        -ArgumentList "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "443", "--ssl-certfile", "$SSLCert", "--ssl-keyfile", "$SSLKey" `
        -WorkingDirectory $BackendDir `
        -WindowStyle Normal
    $backendPort = 443
    $backendProto = "https"
} else {
    $backendPort = 8000
    $portInUse = Get-NetTCPConnection -LocalPort $backendPort -State Listen -ErrorAction SilentlyContinue
    if ($portInUse) {
        Write-Host "      Port $backendPort is already in use; falling back to port 8001." -ForegroundColor Yellow
        $backendPort = 8001
    }

    Write-Host "      Starting HTTP on port $backendPort" -ForegroundColor Yellow
    $backend = Start-Process -PassThru -FilePath $PythonExe `
        -ArgumentList "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "$backendPort" `
        -WorkingDirectory $BackendDir `
        -WindowStyle Normal
    $backendProto = "http"
}

# Wait for backend to be ready
$maxWait = 30
$waited = 0
$backendReady = $false
Write-Host "      Waiting for backend to be ready on port $backendPort..." -ForegroundColor Gray
do {
    Start-Sleep 1
    $waited++
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:$backendPort/api/health/summary" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($resp.StatusCode -eq 200 -or $resp.StatusCode -eq 301) { 
            $backendReady = $true
            break 
        }
    } catch {
        $backendReady = $false
    }
} while ($waited -lt $maxWait)

if (-not $backendReady) {
    Write-Host "WARNING: Backend may still be starting - check its window manually." -ForegroundColor Yellow
} else {
    Write-Host "      Backend is ready! (took $waited sec)" -ForegroundColor Green
}

# Step 5: Start Frontend
Write-Host ""
Write-Host "[5/6] Starting Frontend..." -ForegroundColor Yellow

$NodeModulesPath = Join-Path -Path $FrontendDir -ChildPath "node_modules"
if (-not (Test-Path -Path $NodeModulesPath)) {
    Write-Host "      node_modules not found. Installing dependencies (this may take a minute)..." -ForegroundColor Cyan
    $npmInstall = Start-Process -PassThru -FilePath "cmd" `
        -ArgumentList "/c npm install" `
        -WorkingDirectory $FrontendDir `
        -WindowStyle Normal
    $npmInstall.WaitForExit()
    Write-Host "      Dependencies installed." -ForegroundColor Green
}

Write-Host "      Starting development server (npm run dev)..." -ForegroundColor Cyan
$frontend = Start-Process -PassThru -FilePath "cmd" `
    -ArgumentList "/c npm run dev" `
    -WorkingDirectory $FrontendDir `
    -WindowStyle Normal
Write-Host "      Frontend PID: $($frontend.Id) (Access at http://localhost:5173)" -ForegroundColor Green

# Step 6: Start Redis Dashboard (Redis Commander)
Write-Host ""
if (-not $SkipRedisCheck) {
    Write-Host "[6/6] Starting Redis Dashboard (redis-commander)..." -ForegroundColor Yellow

    # Parse URL for Redis Commander (Format: redis://:password@host:port/db)
    $DashHost = "127.0.0.1"
    $DashPort = 6379
    $DashPass = ""
    if ($RedisUrl -match 'redis://(:(?<pass>.*)@)?(?<host>[^:/]+)(:(?<port>\d+))?(/.*)?') {
        $DashHost = $Matches['host']
        if ($Matches['port']) { $DashPort = $Matches['port'] }
        if ($Matches['pass']) { $DashPass = $Matches['pass'] }
    }

    $dashArgs = "--redis-host $DashHost --redis-port $DashPort --redis-label RemoteServer"
    if ($DashPass) { $dashArgs += " --redis-password $DashPass" }

    $dashboard = Start-Process -PassThru -FilePath "cmd" `
        -ArgumentList "/c redis-commander $dashArgs" `
        -WindowStyle Normal
    Write-Host "      Dashboard PID: $($dashboard.Id) (Access at http://localhost:8081)" -ForegroundColor Green
} else {
    Write-Host "[6/6] Skipping Redis dashboard start (SKIP_REDIS_CHECK=1)." -ForegroundColor Cyan
}

# Summary
Write-Host ""
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "  ALL SERVICES STARTED" -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "  Redis        : $RedisUrl" -ForegroundColor White
Write-Host "  Celery Worker: PID $($celery.Id)" -ForegroundColor White
Write-Host "  Celery Beat  : PID $($beat.Id)  (Runs scheduled campaigns)" -ForegroundColor White
Write-Host "  Backend API  : $($backendProto)://localhost:$($backendPort)" -ForegroundColor White
Write-Host "  Frontend     : http://localhost:5173" -ForegroundColor White
Write-Host "  Swagger Docs : $($backendProto)://localhost:$($backendPort)/docs" -ForegroundColor Cyan

Write-Host ""
Write-Host "  To stop all: Close the opened windows" -ForegroundColor Gray
Write-Host "=================================================" -ForegroundColor Cyan
