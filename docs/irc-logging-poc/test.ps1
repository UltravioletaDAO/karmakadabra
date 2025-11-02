# Quick test script for IRC logging POC (PowerShell)
#
# Usage: .\test.ps1 [channel_name]
#
# This will:
# 1. Build the POC
# 2. Run it with IRC enabled
# 3. Send test logs to specified channel on irc.dal.net
#
# Example: .\test.ps1                    # Uses #karmacadabra
#          .\test.ps1 test-myname        # Uses #test-myname

param(
    [string]$Channel = "karmacadabra"
)

$ErrorActionPreference = "Stop"

# Ensure channel starts with #
if (-not $Channel.StartsWith("#")) {
    $Channel = "#$Channel"
}

Write-Host "🔨 Building IRC logging POC..." -ForegroundColor Cyan
cargo build --release

Write-Host ""
Write-Host "🚀 Starting POC - logs will appear in $Channel on irc.dal.net" -ForegroundColor Green
Write-Host ""
Write-Host "📋 IMPORTANT - Follow these steps:" -ForegroundColor Yellow
Write-Host ""
Write-Host "   FIRST - In your IRC client:" -ForegroundColor White
Write-Host "   1. Connect to irc.dal.net"
Write-Host "   2. Join $Channel (create it if needed: /join $Channel)"
Write-Host "   3. Wait for bot 'x402-poc' to join"
Write-Host ""
Write-Host "   THEN - Watch for messages:" -ForegroundColor White
Write-Host "   • <x402-poc> IRC logging initialized"
Write-Host "   • <x402-poc> [INFO] Processing request #1"
Write-Host "   • etc."
Write-Host ""
Write-Host "   If nothing appears, see TROUBLESHOOTING_DALNET.md" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""
Write-Host "Console will show: [IRC->$Channel] for each message sent" -ForegroundColor Cyan
Write-Host ""

$env:IRC_ENABLED = "true"
$env:IRC_CHANNEL = $Channel
cargo run --release
