#!/bin/bash

# FangcunGuard Platform Quick Start Script

echo "🛡️  FangcunGuard Platform Quick Start"
echo "========================================"

# 检查Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not installed, please install Docker first"
    exit 1
fi

# Create necessary directories
echo "📁 Create necessary directories..."
mkdir -p data logs

# Set permissions
chmod 755 data logs

# Start frontend (development mode)
echo "🚀 Start frontend service..."
cd frontend
npm install
npm run dev &
FRONTEND_PID=$!
cd ..

# Start backend services (development mode)
echo "🚀 Start backend services..."
cd backend
pip install -r requirements.txt

# Start admin service
python start_admin_service.py &
ADMIN_PID=$!

# Start detection service
python start_detection_service.py &
DETECTION_PID=$!

# Start proxy service
python start_proxy_service.py &
PROXY_PID=$!

cd ..

echo ""
echo "✅ Service starting..."
echo ""
echo "📊 Access Address:"
echo "   Frontend Management Interface: http://localhost:3000"
echo "   Admin Service (Port 5000): http://localhost:5000/docs"
echo "   Detection Service (Port 5001): http://localhost:5001/v1/guardrails"
echo "   Proxy Service (Port 5002): http://localhost:5002/v1/chat/completions"
echo ""
echo "🔧 Stop Service:"
echo "   Ctrl+C or run: kill $FRONTEND_PID $ADMIN_PID $DETECTION_PID $PROXY_PID"
echo ""
echo "📧 Technical Support: thomas@fangcunguard.com"

# Wait for user interrupt
wait