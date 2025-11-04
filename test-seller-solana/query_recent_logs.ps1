# Query recent facilitator logs for settlement attempts
$oneHourAgo = [Math]::Floor(([datetime]::UtcNow - [datetime]'1970-01-01').TotalMilliseconds) - 3600000

Write-Host "Querying logs from last hour (since $oneHourAgo)..." -ForegroundColor Cyan
Write-Host ""

# Query for any POST requests
$output = aws logs filter-log-events `
    --log-group-name "/ecs/facilitator-production" `
    --region us-east-2 `
    --start-time $oneHourAgo `
    --filter-pattern "POST" `
    --max-items 50 `
    --output json 2>&1

if ($LASTEXITCODE -eq 0) {
    try {
        $data = $output | ConvertFrom-Json
        $events = $data.events

        Write-Host "Found $($events.Count) POST request log entries" -ForegroundColor Green
        Write-Host ""

        foreach ($event in $events | Select-Object -First 30) {
            $ts = [DateTimeOffset]::FromUnixTimeMilliseconds($event.timestamp).ToString('yyyy-MM-dd HH:mm:ss')
            $msg = $event.message -replace '\x1B\[[0-9;]*[mGKH]', ''

            # Truncate long messages
            if ($msg.Length -gt 200) {
                $msg = $msg.Substring(0, 200) + "..."
            }

            Write-Host "[$ts] $msg" -ForegroundColor White
        }
    } catch {
        Write-Host "Error parsing JSON: $_" -ForegroundColor Red
        Write-Host "Raw output (first 2000 chars):" -ForegroundColor Yellow
        Write-Host ($output | Out-String).Substring(0, [Math]::Min(2000, ($output | Out-String).Length))
    }
} else {
    Write-Host "AWS CLI error:" -ForegroundColor Red
    Write-Host $output
}
