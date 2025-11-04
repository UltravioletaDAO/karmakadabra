# Get settlement-related logs from facilitator

Write-Host "Fetching settlement logs from last 1 hour..." -ForegroundColor Cyan

# Calculate timestamp for 1 hour ago (in milliseconds)
$oneHourAgo = [Math]::Floor(([datetime]::UtcNow.AddHours(-1) - [datetime]'1970-01-01').TotalMilliseconds)

Write-Host "Querying logs since: $oneHourAgo" -ForegroundColor Yellow

# Query for settle events
$output = aws logs filter-log-events `
    --log-group-name "/ecs/facilitator-production" `
    --region us-east-2 `
    --start-time $oneHourAgo `
    --filter-pattern "settle" `
    --max-items 100 2>&1

if ($LASTEXITCODE -eq 0) {
    $json = $output | ConvertFrom-Json
    $events = $json.events

    Write-Host "`nFound $($events.Count) settlement-related log entries`n" -ForegroundColor Green

    foreach ($event in $events) {
        $timestamp = [DateTimeOffset]::FromUnixTimeMilliseconds($event.timestamp).ToString("yyyy-MM-dd HH:mm:ss")
        Write-Host "[$timestamp]" -ForegroundColor Cyan -NoNewline
        Write-Host " $($event.message)"
    }
} else {
    Write-Host "Error querying logs:" -ForegroundColor Red
    Write-Host $output
}
