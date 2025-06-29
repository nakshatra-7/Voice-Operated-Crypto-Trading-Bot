#!/bin/bash

echo "🎙️ Starting Voice Trading Bot..."
echo "=================================="

# Function to check if a port is in use
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null ; then
        echo "❌ Port $1 is already in use. Please stop the service using port $1 first."
        return 1
    fi
    return 0
}

# Check if ports are available
echo "🔍 Checking ports..."
if ! check_port 8000; then
    exit 1
fi
if ! check_port 3000; then
    exit 1
fi

echo "✅ Ports are available"

# Start backend
echo "🚀 Starting backend server..."
cd backend
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

echo "📦 Installing backend dependencies..."
source venv/bin/activate
pip install -r requirements.txt

echo "🌐 Starting backend on http://localhost:8000"
python main.py &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 3

# Start frontend
echo "🎨 Starting frontend server..."
cd ../frontend/goq
echo "📦 Installing frontend dependencies..."
npm install

echo "🌐 Starting frontend on http://localhost:3000"
npm start &
FRONTEND_PID=$!

echo ""
echo "🎉 Voice Trading Bot is starting up!"
echo "=================================="
echo "📱 Frontend: http://localhost:3000"
echo "🔧 Backend:  http://localhost:8000"
echo "📊 API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both services"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping services..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo "✅ Services stopped"
    exit 0
}

# Set up signal handler
trap cleanup SIGINT SIGTERM

# Wait for both processes
wait 