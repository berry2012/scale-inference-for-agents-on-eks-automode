#!/bin/bash
# Quick Start Script for SummitAssistant Local Development

set -e

echo "🚀 SummitAssistant Quick Start"
echo "============================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker and try again.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker is running${NC}"

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ docker-compose not found. Please install docker-compose.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ docker-compose is available${NC}"
echo ""

# Stop any existing containers
echo "🛑 Stopping any existing containers..."
docker-compose down -v 2>/dev/null || true
echo ""

# Start services
echo "🏗️  Building and starting services..."
echo "   This may take a few minutes on first run..."
docker-compose up -d --build

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check service health
echo ""
echo "🔍 Checking service health..."

# Check S3 (LocalStack)
if curl -s http://localhost:4566/_localstack/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ S3 (LocalStack) is healthy${NC}"
else
    echo -e "${YELLOW}⚠ S3 (LocalStack) is not ready yet${NC}"
fi

# Check Calendar MCP Server
if curl -s http://localhost:8081/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Calendar MCP Server is healthy${NC}"
else
    echo -e "${YELLOW}⚠ Calendar MCP Server is not ready yet${NC}"
fi

# Check Chat UI
if curl -s http://localhost:3000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Chat UI is healthy${NC}"
else
    echo -e "${YELLOW}⚠ Chat UI is not ready yet${NC}"
fi

echo ""
echo "📦 Setting up S3 bucket..."
export S3_ENDPOINT_URL=http://localhost:4566
export S3_BUCKET_NAME=SummitAssistant-demo-bucket
export S3_REGION=us-east-2

# Wait a bit more for LocalStack
sleep 5

# Create S3 bucket
if ./scripts/setup_s3_bucket.sh 2>/dev/null; then
    echo -e "${GREEN}✓ S3 bucket created${NC}"
else
    echo -e "${YELLOW}⚠ S3 bucket creation failed (may already exist)${NC}"
fi

echo ""
echo "📝 Initializing mock data..."
export S3_ENDPOINT=http://localhost:4566

if python scripts/initialize_mock_data.py 2>/dev/null; then
    echo -e "${GREEN}✓ Mock data initialized${NC}"
else
    echo -e "${YELLOW}⚠ Mock data initialization failed (may already exist)${NC}"
fi

echo ""
echo "✅ SummitAssistant is ready!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🌐 Access Points:"
echo ""
echo "   Chat UI:              http://localhost:3000"
echo "   SummitAssistant Agent:  http://localhost:8080"
echo "   Calendar MCP Server:  http://localhost:8081"
echo "   vLLM Service:         http://localhost:8000"
echo "   LocalStack S3:        http://localhost:4566"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📚 Quick Tests:"
echo ""
echo "   # Test Calendar MCP Server"
echo "   curl -X POST http://localhost:8081/schedule \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"date\":\"2026-03-15\",\"time\":\"14:00\",\"duration_minutes\":60,\"attendees\":[\"test@example.com\"],\"title\":\"Test\"}'"
echo ""
echo "   # View logs"
echo "   docker-compose logs -f SummitAssistant"
echo ""
echo "   # Stop services"
echo "   docker-compose down"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 Tips:"
echo "   - Open http://localhost:3000 in your browser to use the Chat UI"
echo "   - The vLLM service may take a few minutes to download the model"
echo "   - Check logs with: docker-compose logs -f [service-name]"
echo "   - Services: SummitAssistant, calendar-mcp-server, chat-ui, vllm, s3"
echo ""
echo "🎉 Happy coding!"
