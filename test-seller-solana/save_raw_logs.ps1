# Save raw facilitator logs to file for manual inspection
$now = [Math]::Floor(([datetime]::UtcNow - [datetime]'1970-01-01').TotalMilliseconds)
$twoMinAgo = $now - (2 * 60 * 1000)

Write-Host "Fetching raw logs from last 2 minutes..." -ForegroundColor Cyan

# Get JSON output and save directly to file without parsing
aws logs filter-log-events `
    --log-group-name "/ecs/facilitator-production" `
    --region us-east-2 `
    --start-time $twoMinAgo `
    --max-items 100 `
    --output json > facilitator_logs_raw_latest.json 2>&1

Write-Host "Logs saved to: facilitator_logs_raw_latest.json" -ForegroundColor Green

# Now manually extract ERROR lines without PowerShell parsing
Write-Host "`nSearching for ERROR messages..." -ForegroundColor Yellow

$content = Get-Content "facilitator_logs_raw_latest.json" -Raw

# Extract lines that contain "15:22:" (our test time)
$testLines = $content -split "`n" | Where-Object { $_ -match "15:22:" }

Write-Host "Found $($testLines.Count) lines from 15:22 timeframe" -ForegroundColor Green
Write-Host ""

# Show lines with "message" field
foreach ($line in $testLines | Where-Object { $_ -match '"message":' } | Select-Object -First 20) {
    # Extract just the message part
    if ($line -match '"message":\s*"([^"]*)"') {
        $msg = $matches[1]
        # Remove escape codes
        $clean = $msg -replace '\\u001b\[[0-9;]*[mGKH]', '' -replace '\\x1B\[[0-9;]*[mGKH]', ''

        if ($clean.Length -gt 0) {
            Write-Host $clean.Substring(0, [Math]::Min(400, $clean.Length)) -ForegroundColor White
        }
    }
}

Write-Host "`n`nDone!" -ForegroundColor Green
