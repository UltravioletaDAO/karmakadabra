# Extract ERROR messages from facilitator logs
$oneHourAgo = [Math]::Floor(([datetime]::UtcNow - [datetime]'1970-01-01').TotalMilliseconds) - 3600000

Write-Host "Querying for ERROR logs from last hour..." -ForegroundColor Cyan
Write-Host ""

# Save raw output to file
$rawOutput = aws logs filter-log-events `
    --log-group-name "/ecs/facilitator-production" `
    --region us-east-2 `
    --start-time $oneHourAgo `
    --filter-pattern "ERROR" `
    --max-items 50 `
    --output json 2>&1

# Save to file for inspection
$rawOutput | Out-File -FilePath "facilitator_error_logs_raw.json" -Encoding UTF8

# Try to parse
try {
    $data = $rawOutput | ConvertFrom-Json
    $events = $data.events

    Write-Host "Found $($events.Count) ERROR log entries" -ForegroundColor Green
    Write-Host ""

    foreach ($event in $events) {
        $ts = [DateTimeOffset]::FromUnixTimeMilliseconds($event.timestamp).ToString('yyyy-MM-dd HH:mm:ss.fff')

        # Strip ANSI codes
        $msg = $event.message -replace '\x1B\[[0-9;]*[mGKH]', ''

        Write-Host "================================================" -ForegroundColor Red
        Write-Host "Timestamp: $ts" -ForegroundColor Yellow
        Write-Host "Log Stream: $($event.logStreamName)" -ForegroundColor Yellow
        Write-Host ""
        Write-Host $msg -ForegroundColor White
        Write-Host ""
    }
} catch {
    Write-Host "JSON parsing failed. Raw output saved to facilitator_error_logs_raw.json" -ForegroundColor Yellow
    Write-Host "Error: $_" -ForegroundColor Red

    # Try to extract ERROR lines manually
    $lines = $rawOutput -split "`n"
    $errorLines = $lines | Where-Object { $_ -match "ERROR" }

    Write-Host "`nExtracted ERROR lines (manual parse):" -ForegroundColor Cyan
    foreach ($line in $errorLines | Select-Object -First 20) {
        # Remove ANSI codes
        $clean = $line -replace '\\x1B\[[0-9;]*[mGKH]', '' -replace '\\u001b\[[0-9;]*[mGKH]', ''
        Write-Host $clean -ForegroundColor White
    }
}
