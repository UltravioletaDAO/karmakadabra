#!/bin/bash
# Start Karmacadabra agent stack with Docker Compose

set -e

echo "🚀 Starting Karmacadabra Agent Stack..."

# Check if .env files exist
MISSING_ENV=0
for agent in validator karma-hello abracadabra skill-extractor voice-extractor; do
    if [ ! -f "agents/$agent/.env" ]; then
        echo "❌ Missing agents/$agent/.env"
        MISSING_ENV=1
    fi
done

if [ $MISSING_ENV -eq 1 ]; then
    echo ""
    echo "⚠️  Create .env files from .env.example:"
    echo "   cp agents/validator/.env.example agents/validator/.env"
    echo "   cp agents/karma-hello/.env.example agents/karma-hello/.env"
    echo "   cp agents/abracadabra/.env.example agents/abracadabra/.env"
    echo "   cp agents/skill-extractor/.env.example agents/skill-extractor/.env"
    echo "   cp agents/voice-extractor/.env.example agents/voice-extractor/.env"
    echo ""
    echo "   Then edit each .env file with your configuration."
    exit 1
fi

# Check if AWS credentials exist
if [ ! -f "$HOME/.aws/credentials" ]; then
    echo "⚠️  AWS credentials not found at ~/.aws/credentials"
    echo "   Agents will not be able to fetch private keys from AWS Secrets Manager"
    echo "   You can either:"
    echo "   1. Configure AWS CLI: aws configure"
    echo "   2. Add PRIVATE_KEY to each .env file (for testing only)"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Determine which compose file to use
if [ "$1" == "dev" ]; then
    echo "📝 Starting in DEVELOPMENT mode (hot reload enabled)"
    docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
else
    echo "🏭 Starting in PRODUCTION mode"
    docker-compose up -d
fi

echo ""
echo "✅ Agent stack started!"
echo ""
echo "📊 Service Status:"
docker-compose ps

echo ""
echo "🔗 Agent Endpoints:"
echo "   Validator:        http://localhost:9001/health"
echo "   Karma-Hello:      http://localhost:9002/health"
echo "   Abracadabra:      http://localhost:9003/health"
echo "   Skill-Extractor:  http://localhost:9004/health"
echo "   Voice-Extractor:  http://localhost:9005/health"
echo ""
echo "📈 Metrics:"
echo "   Validator:        http://localhost:9090/metrics"
echo ""
echo "📋 View Logs:"
echo "   All agents:       docker-compose logs -f"
echo "   Single agent:     docker-compose logs -f karma-hello"
echo ""
echo "🛑 Stop Stack:"
echo "   docker-compose down"
