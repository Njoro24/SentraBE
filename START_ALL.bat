@echo off
REM Sentra Complete Startup Script for Windows
REM Starts all services: Docker (Kafka, Zookeeper, PostgreSQL), Backend, and initializes database

setlocal enabledelayedexpansion

echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║          SENTRA FRAUD DETECTION SYSTEM - STARTUP              ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

REM Step 1: Check Docker
echo [1/5] Checking Docker installation...
docker --version >nul 2>&1
if errorlevel 1 (
    echo ✗ Docker is not installed
    exit /b 1
)
echo ✓ Docker found
echo.

REM Step 2: Start Docker Compose services
echo [2/5] Starting Docker services (Kafka, Zookeeper, PostgreSQL)...
docker-compose up -d
if errorlevel 1 (
    echo ✗ Docker services failed to start
    docker-compose logs
    exit /b 1
)

echo   Waiting for services to be healthy...
timeout /t 5 /nobreak

echo ✓ Docker services started
echo.

REM Step 3: Initialize Kafka topics
echo [3/5] Initializing Kafka topics...
python init_kafka_topics.py
echo.

REM Step 4: Initialize database
echo [4/5] Initializing database...
python -c "from data.schema import init_db; init_db()"
echo ✓ Database initialized
echo.

REM Step 5: Setup admin user
echo [5/5] Setting up admin user...
python setup_admin.py
echo.

echo ╔════════════════════════════════════════════════════════════════╗
echo ║                    STARTUP COMPLETE                           ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

echo Services running:
echo   • PostgreSQL: localhost:5433
echo   • Kafka: localhost:9092
echo   • Zookeeper: localhost:2181
echo.

echo Next steps:
echo   1. Start the backend:
echo      python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
echo.
echo   2. Start the frontend (in another terminal):
echo      cd ..\SentraFE
echo      npm run dev
echo.
echo   3. Access the application:
echo      Frontend: http://localhost:3000
echo      Admin: http://localhost:3000/admin
echo      API Docs: http://localhost:8000/docs
echo.

echo To stop all services:
echo   docker-compose down
echo.

pause
