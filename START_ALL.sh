#!/bin/bash

# Sentra Complete Startup Script
# Starts all services: Docker (Kafka, Zookeeper, PostgreSQL), Backend, and initializes database

set -e

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║          SENTRA FRAUD DETECTION SYSTEM - STARTUP              ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Check Docker
echo -e "${YELLOW}[1/5]${NC} Checking Docker installation..."
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker found${NC}"

# Step 2: Start Docker Compose services
echo ""
echo -e "${YELLOW}[2/5]${NC} Starting Docker services (Kafka, Zookeeper, PostgreSQL)..."
docker-compose up -d

# Wait for services to be healthy
echo "  Waiting for services to be healthy..."
sleep 5

# Check if services are running
if docker-compose ps | grep -q "Up"; then
    echo -e "${GREEN}✓ Docker services started${NC}"
else
    echo -e "${RED}✗ Docker services failed to start${NC}"
    docker-compose logs
    exit 1
fi

# Step 3: Initialize Kafka topics
echo ""
echo -e "${YELLOW}[3/5]${NC} Initializing Kafka topics..."
python init_kafka_topics.py

# Step 4: Initialize database
echo ""
echo -e "${YELLOW}[4/5]${NC} Initializing database..."
python -c "from data.schema import init_db; init_db()"
echo -e "${GREEN}✓ Database initialized${NC}"

# Step 5: Setup admin user
echo ""
echo -e "${YELLOW}[5/5]${NC} Setting up admin user..."
python setup_admin.py

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    STARTUP COMPLETE                           ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo -e "${GREEN}Services running:${NC}"
echo "  • PostgreSQL: localhost:5433"
echo "  • Kafka: localhost:9092"
echo "  • Zookeeper: localhost:2181"
echo ""
echo -e "${GREEN}Next steps:${NC}"
echo "  1. Start the backend:"
echo "     python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "  2. Start the frontend (in another terminal):"
echo "     cd ../SentraFE && npm run dev"
echo ""
echo "  3. Access the application:"
echo "     Frontend: http://localhost:3000"
echo "     Admin: http://localhost:3000/admin"
echo "     API Docs: http://localhost:8000/docs"
echo ""
echo -e "${YELLOW}To stop all services:${NC}"
echo "  docker-compose down"
echo ""
