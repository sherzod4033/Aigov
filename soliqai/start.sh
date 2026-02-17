#!/bin/bash

# SoliqAI Quick Start Script

echo "🚀 Starting SoliqAI..."
echo

POSTGRES_HOST="${POSTGRES_SERVER:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"

check_postgres() {
    if command -v pg_isready >/dev/null 2>&1; then
        pg_isready -q -h "$POSTGRES_HOST" -p "$POSTGRES_PORT"
        return $?
    fi

    if command -v nc >/dev/null 2>&1; then
        nc -z "$POSTGRES_HOST" "$POSTGRES_PORT" >/dev/null 2>&1
        return $?
    fi

    # Fallback when pg_isready/nc are unavailable.
    (echo >"/dev/tcp/$POSTGRES_HOST/$POSTGRES_PORT") >/dev/null 2>&1
}

# Check if postgres is running
if ! check_postgres; then
    echo "❌ PostgreSQL is not running. Please start it first:"
    echo "   sudo service postgresql start"
    if ! command -v pg_isready >/dev/null 2>&1; then
        echo "ℹ️  Optional: install pg_isready for better checks:"
        echo "   sudo apt install postgresql-client"
    fi
    exit 1
fi

echo "✅ PostgreSQL is running ($POSTGRES_HOST:$POSTGRES_PORT)"

# Check if ollama is running
if ! curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "⚠️  Ollama is not running. Please start it:"
    echo "   ollama serve"
else
    echo "✅ Ollama is running (http://localhost:11434)"
fi

# Start backend
echo "🐍 Starting Backend..."
cd backend
source venv/bin/activate
python run.py --reload &
BACKEND_PID=$!
cd ..

sleep 2

# Start frontend
echo "⚛️  Starting Frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo
echo "═══════════════════════════════════════════════════════════"
echo "  SoliqAI is starting up..."
echo "═══════════════════════════════════════════════════════════"
echo
echo "  Backend:  http://localhost:8001"
echo "  Frontend: http://localhost:5173"
echo "  API Docs: http://localhost:8001/api/v1/docs"
echo
echo "  Press Ctrl+C to stop"
echo "═══════════════════════════════════════════════════════════"

# Wait for interrupt
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
