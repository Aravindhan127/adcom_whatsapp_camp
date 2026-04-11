# start_background_services.ps1
# This script starts the Redis server and the Celery worker for the Adcom application.

Write-Host "Starting Background Services..." -ForegroundColor Cyan

# 1. Start Redis Server
Write-Host "[1/2] Starting Redis on 127.0.0.1:6379..." -ForegroundColor Yellow
Start-Process -FilePath "redis-server.exe" -ArgumentList "--port 6379" -WindowStyle Hidden

# Wait for Redis to start
Start-Sleep -Seconds 2

# 2. Start Celery Worker
# Note: Using '-P solo' is crucial for Celery on Windows to avoid 'ForkPoolWorker' issues.
Write-Host "[2/2] Starting Celery Worker (adcom_worker)..." -ForegroundColor Yellow
Start-Process -FilePath "python.exe" -ArgumentList "-m celery -A app.core.celery_app worker --loglevel=info -P solo" -WindowStyle Normal

Write-Host "Success: All services triggered in the background." -ForegroundColor Green
Write-Host "You can verify the worker in your browser via the Campaign Manager UI." -ForegroundColor Cyan
