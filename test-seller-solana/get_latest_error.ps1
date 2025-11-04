# Get the most recent error from facilitator logs
# Test ran at approximately 15:22:12 UTC (2025-11-03)

Write-Host "Querying facilitator logs for MOST RECENT settlement attempt..." -ForegroundColor Cyan
Write-Host ""

# Last 2 minutes only
$now = [Math]::Floor(([datetime]::UtcNow - [datetime]'1970-01-01').TotalMilliseconds)
$twoMinAgo = $now - (2 * 60 * 1000)

Write-Host "Time range: last 2 minutes" -ForegroundColor Yellow
Write-Host ""

# Get all logs from last 2 minutes, no filter
$output = aws logs filter-log-events `
    --log-group-name "/ecs/facilitator-production" `
    --region us-east-2 `
    --start-time $twoMinAgo `
    --max-items 100 `
    --output text 2>&1

if ($LASTEXITCODE -eq 0) {
    $lines = $output -split "`n"

    # Find lines with ERROR, settle, or POST
    $relevantLines = $lines | Where-Object {
        $_ -match "ERROR|settle|Settlement|failed|invalid"
    }

    Write-Host "Found $($relevantLines.Count) relevant log lines" -ForegroundColor Green
    Write-Host ""

    foreach ($line in $relevantLines | Select-Object -Last 30) {
        # Parse: EVENTS \t eventId \t timestamp \t logStream \t message
        $parts = $line -split "`t"

        if ($parts.Count -ge 5 -and $parts[2] -match "^\d{13}$") {
            $ts = [DateTimeOffset]::FromUnixTimeMilliseconds([long]$parts[2]).ToString('yyyy-MM-dd HH:mm:ss.fff')
            $msg = $parts[4]

            # Remove ANSI codes
            $cleanMsg = $msg -replace '\[0m|\[2m|\[31m|\[34m|\[1m|\[3m|\[35m', ''

            # Highlight errors
            if ($cleanMsg -match "ERROR|failed|invalid") {
                Write-Host "[$ts] ERROR: " -NoNewline -ForegroundColor Red
                Write-Host $cleanMsg.Substring(0, [Math]::Min(300, $cleanMsg.Length)) -ForegroundColor White
            } else {
                Write-Host "[$ts] " -NoNewline -ForegroundColor Yellow
                Write-Host $cleanMsg.Substring(0, [Math]::Min(200, $cleanMsg.Length)) -ForegroundColor Gray
            }
        }
    }
} else {
    Write-Host "Query failed: $output" -ForegroundColor Red
}

Write-Host "`nDone!" -ForegroundColor Green
