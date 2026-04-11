# ============================================================
# Adcom Standalone - Full Stack Startup Script
# Run this from: c:\Office_Work\Adcom\Adcom_Standalone
# Usage: .\start.ps1
# ============================================================

$BackendDir = "$PSScriptRoot\backend"
$FrontendDir = "$PSScriptRoot\frontend"

Write-Host ""
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "  ADCOM STARTUP" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

# Step 1: Start Redis via Docker Compose
Write-Host ""
Write-Host "[1/5] Starting Redis (Docker)..." -ForegroundColor Yellow
docker compose up -d redis
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to start Redis via Docker. Is Docker running?" -ForegroundColor Red
    exit 1
}

# Wait for Redis to be ready
Write-Host "      Waiting for Redis to be ready..." -ForegroundColor Gray
$maxWait = 20
$waited = 0
$ping = "False"
do {
    Start-Sleep 1
    $waited++
    try {
        $ping = python -c "import redis; r=redis.from_url('redis://127.0.0.1:6379/0'); print(r.ping())" 2>$null
    } catch {
        $ping = "False"
    }
} while ($ping -ne "True" -and $waited -lt $maxWait)

if ($ping -ne "True") {
    Write-Host "ERROR: Redis did not respond after $maxWait seconds." -ForegroundColor Red
    exit 1
}
Write-Host "      Redis is ready!" -ForegroundColor Green

# Step 2: Start Celery Worker
Write-Host ""
Write-Host "[2/5] Starting Celery Worker..." -ForegroundColor Yellow
$celery = Start-Process -PassThru -FilePath "python" `
    -ArgumentList "-m celery -A app.core.celery_app worker --loglevel=info --pool=solo" `
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
Write-Host "[3/5] Starting Celery Beat (Scheduler)..." -ForegroundColor Yellow
$beat = Start-Process -PassThru -FilePath "python" `
    -ArgumentList "-m celery -A app.core.celery_app beat --loglevel=info" `
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
Write-Host "[4/5] Starting Backend API (uvicorn)..." -ForegroundColor Yellow
$backend = Start-Process -PassThru -FilePath "python" `
    -ArgumentList "-m uvicorn main:app --port 8000" `
    -WorkingDirectory $BackendDir `
    -WindowStyle Normal

# Wait for backend to be ready
$maxWait = 30
$waited = 0
$backendReady = $false
Write-Host "      Waiting for backend to be ready on port 8000..." -ForegroundColor Gray
do {
    Start-Sleep 1
    $waited++
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:8000/api/health/summary" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($resp.StatusCode -eq 200) { 
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
Write-Host "[5/5] Starting Frontend (npm run dev)..." -ForegroundColor Yellow
$frontend = Start-Process -PassThru -FilePath "cmd" `
    -ArgumentList "/c npm run dev" `
    -WorkingDirectory $FrontendDir `
    -WindowStyle Normal
Write-Host "      Frontend PID: $($frontend.Id)" -ForegroundColor Green

# Summary
Write-Host ""
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "  ALL SERVICES STARTED" -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "  Redis        : redis://127.0.0.1:6379" -ForegroundColor White
Write-Host "  Celery Worker: PID $($celery.Id)" -ForegroundColor White
Write-Host "  Celery Beat  : PID $($beat.Id)  <-- Runs scheduled campaigns" -ForegroundColor White
Write-Host "  Backend API  : http://localhost:8000" -ForegroundColor White
Write-Host "  Frontend     : http://localhost:3000" -ForegroundColor White
Write-Host ""
Write-Host "  To stop all: Close the opened windows" -ForegroundColor Gray
Write-Host "=================================================" -ForegroundColor Cyan
