Set-Location 'e:\3-2\SUST Hackathon\queueStorm-warmup'

# Kill any previous uvicorn
$existing = Get-Process -Name uvicorn -ErrorAction SilentlyContinue
if ($existing) { $existing | Stop-Process -Force }

# Load key from .env
$line = (Get-Content '.\.env' | Where-Object { $_ -like 'GEMINI_API_KEY=*' }) | Select-Object -First 1
$key = $line -replace '^GEMINI_API_KEY=', ''
$env:GEMINI_API_KEY = $key
Write-Host ("Using key prefix: {0}... (length={1})" -f $key.Substring(0,7), $key.Length)

# Start uvicorn detached
Start-Process -FilePath '.\.venv\Scripts\python.exe' `
    -ArgumentList '-m','uvicorn','main:app','--host','127.0.0.1','--port','8000' `
    -WindowStyle Hidden `
    -RedirectStandardOutput '.\uvicorn.out' `
    -RedirectStandardError '.\uvicorn.err'

Start-Sleep -Seconds 3
Write-Host '--- listening sockets on :8000 ---'
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
    Select-Object LocalAddress, LocalPort, State | Format-Table -AutoSize