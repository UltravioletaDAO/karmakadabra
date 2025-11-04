# Get detailed settlement logs without Unicode issues
$oneHourAgo = [Math]::Floor(([datetime]::UtcNow - [datetime]'1970-01-01').TotalMilliseconds) - 3600000

Write-Host "Querying for Solana settlement attempts..." -ForegroundColor Cyan

# Query for settlement-related messages
$patterns = @("settle", "Settlement", "transaction signature", "confirmed", "timeout")

foreach ($pattern in $patterns) {
    Write-Host "`n=== Pattern: $pattern ===" -ForegroundColor Yellow

    $output = aws logs filter-log-events `
        --log-group-name "/ecs/facilitator-production" `
        --region us-east-2 `
        --start-time $oneHourAgo `
        --filter-pattern "$pattern" `
        --max-items 20 `
        --output text 2>&1

    if ($LASTEXITCODE -eq 0) {
        # Output is in text format, parse it
        $lines = $output -split "`n"

        # Find lines with actual log content (skip AWS CLI metadata)
        $logLines = $lines | Where-Object { $_ -match "^\d{13}" }

        if ($logLines.Count -gt 0) {
            Write-Host "Found $($logLines.Count) matches" -ForegroundColor Green

            foreach ($line in $logLines | Select-Object -First 10) {
                # Parse: timestamp \t logStreamName \t message
                $parts = $line -split "`t", 3

                if ($parts.Count -ge 3) {
                    $ts = [DateTimeOffset]::FromUnixTimeMilliseconds([long]$parts[0]).ToString('HH:mm:ss.fff')
                    $msg = $parts[2]

                    # Remove ANSI codes from message
                    $cleanMsg = $msg -replace '\\x1B\[[0-9;]*[mGKH]', '' -replace '\x1B\[[0-9;]*[mGKH]', ''

                    # Truncate long messages
                    if ($cleanMsg.Length -gt 500) {
                        $cleanMsg = $cleanMsg.Substring(0, 500) + "..."
                    }

                    Write-Host "  [$ts] $cleanMsg" -ForegroundColor White
                }
            }
        } else {
            Write-Host "No matches" -ForegroundColor Gray
        }
    } else {
        Write-Host "Query error: $output" -ForegroundColor Red
    }
}

Write-Host "`n`nDone!" -ForegroundColor Green
