#!/bin/bash # fcg-rewrite

# FangcunGuard Platform Start Script # fcg-rewrite

echo "🛡️  FangcunGuard Platform Start Script" # fcg-rewrite
echo "========================================" # fcg-rewrite

# Check Python environment # fcg-rewrite
if ! command -v python3 &> /dev/null; then # fcg-rewrite
    echo "❌ Python3 not installed, please install Python3" # fcg-rewrite
    echo "   Installation guide: https://www.python.org/downloads/" # fcg-rewrite
    exit 1 # fcg-rewrite
fi # fcg-rewrite

# Check pip # fcg-rewrite
if ! command -v pip3 &> /dev/null; then # fcg-rewrite
    echo "❌ pip3 not installed, please install pip3" # fcg-rewrite
    exit 1 # fcg-rewrite
fi # fcg-rewrite

# Check Node.js environment (for frontend) # fcg-rewrite
if ! command -v node &> /dev/null; then # fcg-rewrite
    echo "❌ Node.js not installed, please install Node.js" # fcg-rewrite
    echo "   Installation guide: https://nodejs.org/" # fcg-rewrite
    exit 1 # fcg-rewrite
fi # fcg-rewrite

# Check npm # fcg-rewrite
if ! command -v npm &> /dev/null; then # fcg-rewrite
    echo "❌ npm not installed, please install npm" # fcg-rewrite
    exit 1 # fcg-rewrite
fi # fcg-rewrite

# Create necessary directories # fcg-rewrite
echo "📁 Create necessary directories..." # fcg-rewrite
mkdir -p logs backend/config data/logs # fcg-rewrite

# Set permissions # fcg-rewrite
chmod 755 logs backend/config data/logs # fcg-rewrite

# Check port occupancy # fcg-rewrite
echo "🔍 Check port occupancy..." # fcg-rewrite
if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null 2>&1; then # fcg-rewrite
echo "⚠️  Port 3000 is occupied, please stop related services or modify configuration" # fcg-rewrite
fi # fcg-rewrite

if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null 2>&1; then # fcg-rewrite
    echo "⚠️  Port 5000 is occupied, please stop related services or modify configuration" # fcg-rewrite
fi # fcg-rewrite

if lsof -Pi :5001 -sTCP:LISTEN -t >/dev/null 2>&1; then # fcg-rewrite
    echo "⚠️  Port 5001 is occupied, please stop related services or modify configuration" # fcg-rewrite
fi # fcg-rewrite

if lsof -Pi :5002 -sTCP:LISTEN -t >/dev/null 2>&1; then # fcg-rewrite
    echo "⚠️  Port 5002 is occupied, please stop related services or modify configuration" # fcg-rewrite
fi # fcg-rewrite

# Stop possible running services # fcg-rewrite
echo "🧹 Stop possible running services..." # fcg-rewrite
if [ -f "/tmp/fangcunguard_services.pid" ]; then # fcg-rewrite
    PIDS=$(cat /tmp/fangcunguard_services.pid) # fcg-rewrite
    for PID in $PIDS; do # fcg-rewrite
        if kill -0 $PID 2>/dev/null; then # fcg-rewrite
            echo "Stop service PID: $PID" # fcg-rewrite
            kill $PID 2>/dev/null # fcg-rewrite
        fi # fcg-rewrite
    done # fcg-rewrite
    rm -f /tmp/fangcunguard_services.pid # fcg-rewrite
fi # fcg-rewrite

# Stop possible running Python processes # fcg-rewrite
pkill -f "start_detection_service.py" 2>/dev/null || true # fcg-rewrite
pkill -f "start_admin_service.py" 2>/dev/null || true # fcg-rewrite
pkill -f "start_proxy_service.py" 2>/dev/null || true # fcg-rewrite

# Enter backend directory # fcg-rewrite
cd backend # fcg-rewrite

# Set environment variable # fcg-rewrite
export PYTHONPATH="$PWD:$PYTHONPATH" # fcg-rewrite

# Check Python dependencies # fcg-rewrite
echo "📦 Check Python dependencies..." # fcg-rewrite
if [ ! -f "requirements.txt" ]; then # fcg-rewrite
    echo "❌ requirements.txt file not found" # fcg-rewrite
    exit 1 # fcg-rewrite
fi # fcg-rewrite

# Install Python dependencies # fcg-rewrite
echo "📦 Install Python dependencies..." # fcg-rewrite
pip3 install -r requirements.txt # fcg-rewrite

# Start all services # fcg-rewrite
echo "🚀 Start all services..." # fcg-rewrite
bash start_all_services.sh & # fcg-rewrite
SERVICES_PID=$! # fcg-rewrite

# Wait for services to start # fcg-rewrite
echo "⏳ Wait for services to start..." # fcg-rewrite
sleep 5 # fcg-rewrite

# Check service status # fcg-rewrite
echo "🔍 Check service status..." # fcg-rewrite
for i in {1..30}; do # fcg-rewrite
    if curl -f http://localhost:5000/health >/dev/null 2>&1; then # fcg-rewrite
        echo "✅ Management service started (port 5000)" # fcg-rewrite
        break # fcg-rewrite
    fi # fcg-rewrite
    if [ $i -eq 30 ]; then # fcg-rewrite
        echo "❌ Management service startup timeout" # fcg-rewrite
    fi # fcg-rewrite
    sleep 2 # fcg-rewrite
done # fcg-rewrite

for i in {1..30}; do # fcg-rewrite
    if curl -f http://localhost:5001/health >/dev/null 2>&1; then # fcg-rewrite
        echo "✅ Detection service started (port 5001)" # fcg-rewrite
        break # fcg-rewrite
    fi # fcg-rewrite
    if [ $i -eq 30 ]; then # fcg-rewrite
        echo "❌ Detection service startup timeout" # fcg-rewrite
    fi # fcg-rewrite
    sleep 2 # fcg-rewrite
done # fcg-rewrite

for i in {1..30}; do # fcg-rewrite
    if curl -f http://localhost:5002/health >/dev/null 2>&1; then # fcg-rewrite
        echo "✅ Proxy service started (port 5002)" # fcg-rewrite
        break # fcg-rewrite
    fi # fcg-rewrite
    if [ $i -eq 30 ]; then # fcg-rewrite
        echo "❌ Proxy service startup timeout" # fcg-rewrite
    fi # fcg-rewrite
    sleep 2 # fcg-rewrite
done # fcg-rewrite

# Start frontend service # fcg-rewrite
echo "🌐 Start frontend service..." # fcg-rewrite
cd ../frontend # fcg-rewrite

# Check frontend dependencies # fcg-rewrite
if [ ! -f "package.json" ]; then # fcg-rewrite
    echo "❌ package.json file not found" # fcg-rewrite
    exit 1 # fcg-rewrite
fi # fcg-rewrite

# Install frontend dependencies # fcg-rewrite
echo "📦 Install frontend dependencies..." # fcg-rewrite
npm install # fcg-rewrite

# Start frontend service # fcg-rewrite
echo "🚀 Start frontend service..." # fcg-rewrite
npm run dev & # fcg-rewrite
FRONTEND_PID=$! # fcg-rewrite

# Wait for frontend service to start # fcg-rewrite
echo "⏳ Wait for frontend service to start..." # fcg-rewrite
for i in {1..30}; do # fcg-rewrite
    if curl -f http://localhost:3000 >/dev/null 2>&1; then # fcg-rewrite
        echo "✅ Frontend service started (port 3000)" # fcg-rewrite
        break # fcg-rewrite
    fi # fcg-rewrite
    if [ $i -eq 30 ]; then # fcg-rewrite
        echo "⚠️  Frontend service may take longer to start" # fcg-rewrite
    fi # fcg-rewrite
    sleep 2 # fcg-rewrite
done # fcg-rewrite

# Save all PIDs # fcg-rewrite
echo "$SERVICES_PID $FRONTEND_PID" > /tmp/fangcunguard_all_services.pid # fcg-rewrite

echo "" # fcg-rewrite
echo "🎉 All services started!" # fcg-rewrite
echo "" # fcg-rewrite
echo "📊 Access address:" # fcg-rewrite
echo "   🌐 Frontend management interface: http://localhost:3000" # fcg-rewrite
echo "   📖 Management API documentation: http://localhost:5000/docs" # fcg-rewrite
echo "   🛡️ Detection API: http://localhost:5001/v1/guardrails" # fcg-rewrite
echo "   🔄 Proxy API: http://localhost:5002/v1/chat/completions" # fcg-rewrite
echo "" # fcg-rewrite
echo "🔑 Default admin account:" # fcg-rewrite
echo "   Email: admin@fangcunguard.com" # fcg-rewrite
echo "   Password: admin123456" # fcg-rewrite
echo "   ⚠️  Please modify the default password in the production environment!" # fcg-rewrite
echo "" # fcg-rewrite
echo "🔧 Common commands:" # fcg-rewrite
echo "   View service logs: tail -f data/logs/*.log" # fcg-rewrite
echo "   Stop all services: ./scripts/stop.sh" # fcg-rewrite
echo "   Restart all services: ./scripts/stop.sh && ./scripts/start.sh" # fcg-rewrite
echo "" # fcg-rewrite
echo "📚 Documentation:" # fcg-rewrite
echo "   Project documentation: https://github.com/fangcunguard/fangcunguard" # fcg-rewrite
echo "   API documentation: http://localhost:5000/docs" # fcg-rewrite
echo "" # fcg-rewrite
echo "📧 Technical support: thomas@fangcunguard.com" # fcg-rewrite