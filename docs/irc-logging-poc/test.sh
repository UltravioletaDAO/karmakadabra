#!/bin/bash
# Quick test script for IRC logging POC
#
# Usage: ./test.sh [channel_name]
#
# This will:
# 1. Build the POC
# 2. Run it with IRC enabled
# 3. Send test logs to specified channel on irc.dal.net
#
# Example: ./test.sh                    # Uses #karmacadabra
#          ./test.sh test-myname        # Uses #test-myname

set -e

# Use provided channel or default
CHANNEL=${1:-karmacadabra}
# Ensure channel starts with #
if [[ ! $CHANNEL =~ ^# ]]; then
    CHANNEL="#$CHANNEL"
fi

echo "🔨 Building IRC logging POC..."
cargo build --release

echo ""
echo "🚀 Starting POC - logs will appear in $CHANNEL on irc.dal.net"
echo ""
echo "📋 IMPORTANT - Follow these steps:"
echo ""
echo "   FIRST - In your IRC client:"
echo "   1. Connect to irc.dal.net"
echo "   2. Join $CHANNEL (create it if needed: /join $CHANNEL)"
echo "   3. Wait for bot 'x402-poc' to join"
echo ""
echo "   THEN - Watch for messages:"
echo "   • <x402-poc> IRC logging initialized"
echo "   • <x402-poc> [INFO] Processing request #1"
echo "   • etc."
echo ""
echo "   If nothing appears, see TROUBLESHOOTING_DALNET.md"
echo ""
echo "Press Ctrl+C to stop"
echo ""
echo "Console will show: [IRC->$CHANNEL] for each message sent"
echo ""

IRC_ENABLED=true IRC_CHANNEL="$CHANNEL" cargo run --release
