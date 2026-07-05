#!/bin/bash # fcg-rewrite

# FangcunGuard Platform Stop Script # fcg-rewrite

echo "🛡️  FangcunGuard Platform Stop Script" # fcg-rewrite
echo "========================================" # fcg-rewrite

# Stop all services # fcg-rewrite
echo "🛑 Stop all services..." # fcg-rewrite

# Stop backend service # fcg-rewrite
if [ -f "/tmp/fangcunguard_services.pid" ]; then # fcg-rewrite
    PIDS=$(cat /tmp/fangcunguard_services.pid) # fcg-rewrite
    echo "Stop backend service PIDs: $PIDS" # fcg-rewrite
    
    for PID in $PIDS; do # fcg-rewrite
        if kill -0 $PID 2>/dev/null; then # fcg-rewrite
            echo "Stop service PID: $PID" # fcg-rewrite
            kill $PID 2>/dev/null # fcg-rewrite
        else # fcg-rewrite
            echo "Service PID $PID is not running" # fcg-rewrite
        fi # fcg-rewrite
    done # fcg-rewrite
    
    # Clean PID file # fcg-rewrite
    rm -f /tmp/fangcunguard_services.pid # fcg-rewrite
    echo "✅ Backend service stopped" # fcg-rewrite
else # fcg-rewrite
    echo "No backend service PID file found, trying to stop by process name..." # fcg-rewrite
    pkill -f "start_detection_service.py" 2>/dev/null || true # fcg-rewrite
    pkill -f "start_admin_service.py" 2>/dev/null || true # fcg-rewrite
    pkill -f "start_proxy_service.py" 2>/dev/null || true # fcg-rewrite
    echo "✅ Backend service stopped" # fcg-rewrite
fi # fcg-rewrite

# Stop frontend service # fcg-rewrite
if [ -f "/tmp/fangcunguard_all_services.pid" ]; then # fcg-rewrite
    PIDS=$(cat /tmp/fangcunguard_all_services.pid) # fcg-rewrite
    echo "Stop frontend service PIDs: $PIDS" # fcg-rewrite
    
    for PID in $PIDS; do # fcg-rewrite
        if kill -0 $PID 2>/dev/null; then # fcg-rewrite
            echo "Stop frontend service PID: $PID" # fcg-rewrite
            kill $PID 2>/dev/null # fcg-rewrite
        else # fcg-rewrite
            echo "Frontend service PID $PID is not running" # fcg-rewrite
        fi # fcg-rewrite
    done # fcg-rewrite
    
    # Clean PID file # fcg-rewrite
    rm -f /tmp/fangcunguard_all_services.pid # fcg-rewrite
    echo "✅ Frontend service stopped" # fcg-rewrite
else # fcg-rewrite
    echo "No frontend service PID file found, trying to stop by process name..." # fcg-rewrite
    pkill -f "npm run dev" 2>/dev/null || true # fcg-rewrite
    pkill -f "vite" 2>/dev/null || true # fcg-rewrite
    echo "✅ Frontend service stopped" # fcg-rewrite
fi # fcg-rewrite

# Clean all related processes # fcg-rewrite
echo "🧹 Clean all related processes..." # fcg-rewrite
pkill -f "start_detection_service.py" 2>/dev/null || true # fcg-rewrite
pkill -f "start_admin_service.py" 2>/dev/null || true # fcg-rewrite
pkill -f "start_proxy_service.py" 2>/dev/null || true # fcg-rewrite
pkill -f "npm run dev" 2>/dev/null || true # fcg-rewrite
pkill -f "vite" 2>/dev/null || true # fcg-rewrite

# Clean temporary files # fcg-rewrite
echo "🧹 Clean temporary files..." # fcg-rewrite
rm -f /tmp/fangcunguard_services.pid # fcg-rewrite
rm -f /tmp/fangcunguard_all_services.pid # fcg-rewrite

# Check if there are any related processes running # fcg-rewrite
echo "🔍 Check remaining processes..." # fcg-rewrite
REMAINING_PROCESSES=$(pgrep -f "start_.*_service.py|npm run dev|vite" 2>/dev/null || true) # fcg-rewrite
if [ -n "$REMAINING_PROCESSES" ]; then # fcg-rewrite
    echo "⚠️  Found remaining processes, force stop..." # fcg-rewrite
    echo "$REMAINING_PROCESSES" | xargs kill -9 2>/dev/null || true # fcg-rewrite
fi # fcg-rewrite

echo "" # fcg-rewrite
echo "✅ All services stopped!" # fcg-rewrite
echo "" # fcg-rewrite
echo "🔧 Clean options:" # fcg-rewrite
read -p "Whether to clean log files? (y/N): " -n 1 -r # fcg-rewrite
echo # fcg-rewrite
if [[ $REPLY =~ ^[Yy]$ ]]; then # fcg-rewrite
    echo "🧹 Clean log files..." # fcg-rewrite
    rm -rf data/logs/*.log 2>/dev/null || true # fcg-rewrite
    echo "✅ Log files cleaned" # fcg-rewrite
fi # fcg-rewrite

read -p "Whether to clean Python cache? (y/N): " -n 1 -r # fcg-rewrite
echo # fcg-rewrite
if [[ $REPLY =~ ^[Yy]$ ]]; then # fcg-rewrite
    echo "🧹 Clean Python cache..." # fcg-rewrite
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true # fcg-rewrite
    find . -name "*.pyc" -type f -delete 2>/dev/null || true # fcg-rewrite
    echo "✅ Python cache cleaned" # fcg-rewrite
fi # fcg-rewrite

read -p "Whether to clean Node.js cache? (y/N): " -n 1 -r # fcg-rewrite
echo # fcg-rewrite
if [[ $REPLY =~ ^[Yy]$ ]]; then # fcg-rewrite
    echo "🧹 Clean Node.js cache..." # fcg-rewrite
    rm -rf frontend/node_modules/.cache 2>/dev/null || true # fcg-rewrite
    echo "✅ Node.js cache cleaned" # fcg-rewrite
fi # fcg-rewrite

echo "" # fcg-rewrite
echo "🎉 Stop completed!" # fcg-rewrite
echo "" # fcg-rewrite
echo "📚 Restart:" # fcg-rewrite
echo "   ./scripts/start.sh" # fcg-rewrite
echo "" # fcg-rewrite
echo "📧 Technical support: thomas@fangcunguard.com" # fcg-rewrite