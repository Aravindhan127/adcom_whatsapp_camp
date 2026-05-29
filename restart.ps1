# Stop existing Python processes (Uvicorn, Celery worker, Celery Beat)
Write-Host "Killing Python processes..." -ForegroundColor Yellow
taskkill /F /IM python.exe 2>$null

# Stop existing Node/CMD/Redis Commander processes
Write-Host "Killing Node & Cmd processes..." -ForegroundColor Yellow
taskkill /F /IM node.exe 2>$null
taskkill /F /IM cmd.exe 2>$null

Start-Sleep 1

# Start fresh stack in a new window
Write-Host "Launching start.ps1 in new window..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-ExecutionPolicy", "Bypass", "-File", "$PSScriptRoot\start.ps1" -WorkingDirectory $PSScriptRoot
