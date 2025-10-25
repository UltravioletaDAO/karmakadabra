#!/bin/bash
# Quick demo: Test a single agent locally
# No wallet/AVAX needed - just tests HTTP endpoints

echo "=========================================="
echo "Single Agent Demo - elboorja"
echo "=========================================="
echo ""
echo "Starting elboorja agent on port 9044..."
echo ""

cd user-agents/elboorja

# Temporarily comment out blockchain registration for demo
# This allows the agent to start without a wallet
echo "Note: Agent will skip blockchain registration for this demo"

# Start agent in background
python main.py &
AGENT_PID=$!

echo "Agent PID: $AGENT_PID"
echo "Waiting 5 seconds for agent to start..."
sleep 5

echo ""
echo "=========================================="
echo "Testing Agent Endpoints"
echo "=========================================="
echo ""

echo "1. Health Check:"
curl -s http://localhost:9044/health | python -m json.tool
echo ""
echo ""

echo "2. A2A Protocol Agent Card:"
curl -s http://localhost:9044/.well-known/agent-card | python -m json.tool
echo ""
echo ""

echo "3. Service Listing:"
curl -s http://localhost:9044/services | python -m json.tool
echo ""
echo ""

echo "4. User Profile:"
curl -s http://localhost:9044/profile | python -m json.tool
echo ""
echo ""

echo "=========================================="
echo "Demo Complete!"
echo "=========================================="
echo ""
echo "To stop the agent: kill $AGENT_PID"
echo "Or: pkill -f 'python main.py'"
echo ""
