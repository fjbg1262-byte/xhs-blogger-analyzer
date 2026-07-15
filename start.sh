#!/bin/bash
# XHS Blogger Analyzer — Quick Start
# Usage: bash start.sh

echo "=== XHS Blogger Analyzer ==="
echo ""

# Check prerequisites
command -v python >/dev/null 2>&1 || { echo "❌ Python not found"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "❌ Node.js not found"; exit 1; }

# Check Spider_XHS
if [ ! -d "spider_xhs" ]; then
    echo "⚠️  Spider_XHS not found. Data collection will not work."
    echo "   Clone it: git clone https://github.com/cv-cat/Spider_XHS.git spider_xhs"
    echo ""
fi

# Install Python deps
echo "[1/4] Installing Python dependencies..."
pip install -r requirements.txt 2>/dev/null || pip install fastapi uvicorn sqlalchemy pydantic httpx python-dotenv

# Install frontend deps
echo "[2/4] Installing frontend dependencies..."
cd frontend && npm install && cd ..

# Init database
echo "[3/4] Initializing database..."
python -c "from backend.database import init_db; import os; os.makedirs('data/tasks', exist_ok=True); os.makedirs('reports', exist_ok=True); init_db(); print('✅ Database ready')"

# Start servers (backend in background)
echo "[4/4] Starting servers..."
echo ""

python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

cd frontend && npx vite --host 0.0.0.0 --port 5173 &
FRONTEND_PID=$!

echo ""
echo "✅ Backend:  http://localhost:8000"
echo "✅ API Docs: http://localhost:8000/docs"
echo "✅ Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
