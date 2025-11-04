# Check facilitator logs for Solana settlement attempts

Write-Host "Fetching facilitator logs from AWS CloudWatch..." -ForegroundColor Cyan
Write-Host "Log Group: /ecs/facilitator-production" -ForegroundColor Yellow
Write-Host "Region: us-east-2" -ForegroundColor Yellow
Write-Host ""

# Get logs from last 30 minutes
$logs = aws logs tail /ecs/facilitator-production --region us-east-2 --since 30m --format short 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error fetching logs:" -ForegroundColor Red
    Write-Host $logs
    exit 1
}

# Filter for Solana-related entries
Write-Host "=== SOLANA-RELATED LOGS ===" -ForegroundColor Green
$logs | Select-String -Pattern "solana|Solana|SOLANA" -Context 0,2

Write-Host ""
Write-Host "=== SETTLEMENT LOGS ===" -ForegroundColor Green
$logs | Select-String -Pattern "settlement|Settlement|SETTLEMENT" -Context 0,2

Write-Host ""
Write-Host "=== TRANSACTION LOGS ===" -ForegroundColor Green
$logs | Select-String -Pattern "transaction|Transaction|signature" -Context 0,2

Write-Host ""
Write-Host "=== ERROR LOGS ===" -ForegroundColor Green
$logs | Select-String -Pattern "error|Error|ERROR|failed|Failed|FAILED|timeout|Timeout|TIMEOUT" -Context 0,2
