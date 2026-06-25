Set-Location 'e:\3-2\SUST Hackathon\queueStorm-warmup'
$procs = Get-Process -Name uvicorn -ErrorAction SilentlyContinue
if ($procs) {
    $procs | Stop-Process -Force
    Write-Host ('Killed ' + $procs.Count + ' uvicorn process(es).')
} else {
    Write-Host 'No uvicorn running.'
}
$py = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*uvicorn*' -or $_.Path -like '*queueStorm*' }
if ($py) {
    $py | Stop-Process -Force
    Write-Host ('Killed ' + $py.Count + ' python process(es) holding classifier.')
}