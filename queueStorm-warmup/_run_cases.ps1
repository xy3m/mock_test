Set-Location 'e:\3-2\SUST Hackathon\queueStorm-warmup'
foreach ($id in 'T-001','T-002','T-003','T-004','T-005') {
    Write-Host ('--- ' + $id + ' ---')
    & curl.exe -sS -X POST http://127.0.0.1:8000/sort-ticket `
        -H 'Content-Type: application/json' `
        --data ('@.\test_bodies\' + $id + '.json')
    Write-Host ''
}