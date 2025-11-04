# Run test and immediately check facilitator logs

Write-Host "=== STARTING SOLANA LOAD TEST ===" -ForegroundColor Cyan
Write-Host "This will run the test and then check facilitator logs" -ForegroundColor Yellow
Write-Host ""

# Run the test in background
$testJob = Start-Job -ScriptBlock {
    Set-Location "Z:\ultravioleta\dao\karmacadabra\test-seller-solana"
    python load_test_solana_v4.py --seller Ez4frLQzDbV1AT9BNJkQFEjyTFRTsEwJ5YFaSGG8nRGB --num-requests 1
}

Write-Host "Test started (Job ID: $($testJob.Id))" -ForegroundColor Green
Write-Host "Waiting 5 seconds for test to reach facilitator..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "=== CHECKING FACILITATOR LOGS (LIVE) ===" -ForegroundColor Cyan

# Get current timestamp
$now = [Math]::Floor(([datetime]::UtcNow - [datetime]'1970-01-01').TotalMilliseconds)
$fiveMinutesAgo = $now - (5 * 60 * 1000)

Write-Host "Querying logs from last 5 minutes..." -ForegroundColor Yellow

# Query for ANY Solana activity
$patterns = @("solana", "Solana", "SOLANA", "POST /settle", "ERROR")

foreach ($pattern in $patterns) {
    Write-Host "`n--- Searching for: $pattern ---" -ForegroundColor Magenta

    $output = aws logs filter-log-events `
        --log-group-name "/ecs/facilitator-production" `
        --region us-east-2 `
        --start-time $fiveMinutesAgo `
        --filter-pattern "$pattern" `
        --max-items 10 2>&1

    if ($LASTEXITCODE -eq 0) {
        try {
            $json = $output | ConvertFrom-Json
            $events = $json.events

            if ($events.Count -gt 0) {
                Write-Host "  Found $($events.Count) log entries" -ForegroundColor Green

                foreach ($event in $events | Select-Object -Last 3) {
                    $timestamp = [DateTimeOffset]::FromUnixTimeMilliseconds($event.timestamp).ToString("yyyy-MM-dd HH:mm:ss")
                    # Strip ANSI codes
                    $cleanMessage = $event.message -replace '\x1B\[[0-9;]*[mGKH]', ''
                    Write-Host "  [$timestamp] $($cleanMessage.Substring(0, [Math]::Min(200, $cleanMessage.Length)))" -ForegroundColor White
                }
            } else {
                Write-Host "  No entries found" -ForegroundColor Yellow
            }
        } catch {
            Write-Host "  Error parsing response: $_" -ForegroundColor Red
        }
    } else {
        Write-Host "  Query error" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=== WAITING FOR TEST TO COMPLETE ===" -ForegroundColor Cyan
$testJob | Wait-Job | Out-Null
$testOutput = Receive-Job -Job $testJob
Remove-Job -Job $testJob

Write-Host ""
Write-Host "=== TEST OUTPUT ===" -ForegroundColor Cyan
Write-Host $testOutput
