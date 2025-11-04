# Get logs for the specific settlement attempt at 15:13:09

Write-Host "Fetching detailed logs for settlement attempt at 15:13:09..." -ForegroundColor Cyan

# Target time: 2025-11-03 15:13:09 UTC
# That's around 1762183989000 ms epoch

$targetTime = [Math]::Floor(([datetime]::Parse("2025-11-03 15:13:00").ToUniversalTime() - [datetime]'1970-01-01').TotalMilliseconds)
$endTime = $targetTime + (60 * 1000)  # 1 minute window

Write-Host "Time range: $targetTime to $endTime" -ForegroundColor Yellow
Write-Host ""

# Get ALL logs in that timeframe (no filter)
$output = aws logs filter-log-events `
    --log-group-name "/ecs/facilitator-production" `
    --region us-east-2 `
    --start-time $targetTime `
    --end-time $endTime `
    --max-items 200 2>&1

if ($LASTEXITCODE -eq 0) {
    $json = $output | ConvertFrom-Json
    $events = $json.events

    Write-Host "Found $($events.Count) log entries in timeframe`n" -ForegroundColor Green

    # Strip ANSI codes regex
    $ansiPattern = [regex]::new('\x1B\[[0-9;]*[mGKH]')

    foreach ($event in $events) {
        $timestamp = [DateTimeOffset]::FromUnixTimeMilliseconds($event.timestamp).ToString("yyyy-MM-dd HH:mm:ss.fff")
        $cleanMessage = $ansiPattern.Replace($event.message, '')

        # Highlight important messages
        if ($cleanMessage -match "ERROR|error|failed|Failed") {
            Write-Host "[$timestamp] " -NoNewline -ForegroundColor Red
            Write-Host "ERROR: " -NoNewline -ForegroundColor Red
            Write-Host $cleanMessage.Substring(0, [Math]::Min(300, $cleanMessage.Length))
        }
        elseif ($cleanMessage -match "settle|Settle|transaction|Transaction|signature") {
            Write-Host "[$timestamp] " -NoNewline -ForegroundColor Cyan
            Write-Host $cleanMessage.Substring(0, [Math]::Min(300, $cleanMessage.Length))
        }
        else {
            # Skip trace/debug noise
            if ($cleanMessage -notmatch "TRACE|idle interval") {
                Write-Host "[$timestamp] $($cleanMessage.Substring(0, [Math]::Min(200, $cleanMessage.Length)))" -ForegroundColor Gray
            }
        }
    }

    Write-Host "`n" + "=" * 80 -ForegroundColor Green
    Write-Host "LOG ANALYSIS COMPLETE" -ForegroundColor Green
    Write-Host "=" * 80 -ForegroundColor Green

} else {
    Write-Host "Error querying logs" -ForegroundColor Red
    Write-Host $output
}
