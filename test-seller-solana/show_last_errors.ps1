# Show last 20 error/settlement messages from facilitator

Write-Host "Fetching last error/settlement logs..." -ForegroundColor Cyan

$now = [Math]::Floor(([datetime]::UtcNow - [datetime]'1970-01-01').TotalMilliseconds)
$thirtyMinAgo = $now - (30 * 60 * 1000)

$output = aws logs filter-log-events `
    --log-group-name /ecs/facilitator-production `
    --region us-east-2 `
    --start-time $thirtyMinAgo `
    --max-items 300 2>&1

$json = $output | ConvertFrom-Json
$events = $json.events

# Filter for settle/error messages
$relevantEvents = $events | Where-Object {
    $_.message -match 'settle|error|invalid|failed|signature|transaction|ERROR'
}

Write-Host "Found $($relevantEvents.Count) relevant messages`n" -ForegroundColor Green

# Take last 30 and display
$relevantEvents | Select-Object -Last 30 | ForEach-Object {
    $ts = [DateTimeOffset]::FromUnixTimeMilliseconds($_.timestamp).ToString('HH:mm:ss')

    # Clean ANSI codes
    $clean = $_.message -replace '\x1B\[[0-9;]*[mGKH]', ''
    $clean = $clean -replace '\s+', ' '

    # Truncate
    if ($clean.Length > 300) {
        $clean = $clean.Substring(0, 300) + "..."
    }

    # Color based on content
    if ($clean -match 'ERROR|error|failed') {
        Write-Host "[$ts] " -NoNewline -ForegroundColor Red
        Write-Host $clean
    } else {
        Write-Host "[$ts] $clean" -ForegroundColor White
    }
}

Write-Host "`n Done!" -ForegroundColor Green
