$val = [Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY', 'Process')
if ($null -eq $val) {
    Write-Host 'ANTHROPIC_API_KEY is NOT set in the current shell.'
} elseif ($val.Length -lt 8) {
    Write-Host 'ANTHROPIC_API_KEY is SET but looks too short to be valid.'
} else {
    $prefix = $val.Substring(0, 7)
    Write-Host ("ANTHROPIC_API_KEY is SET (length={0}, prefix={1}...)" -f $val.Length, $prefix)
}

$userVal = [Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY', 'User')
if ($null -eq $userVal) {
    Write-Host 'User-level ANTHROPIC_API_KEY: NOT set.'
} else {
    Write-Host ('User-level ANTHROPIC_API_KEY: SET (length={0})' -f $userVal.Length)
}