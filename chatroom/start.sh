#!/bin/bash
# Agent Chatroom — Mac/Linux startup script
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Install deps if needed
if [ ! -d "node_modules" ]; then
  echo "[chatroom] Installing dependencies..."
  bun install
fi

# Resolve agent directory
AGENT_DIR="${AGENT_DIR:-$(find "$HOME/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-toolkit" -maxdepth 1 -name "*/agents" -type d 2>/dev/null | sort -r | head -1)}"
if [ -z "$AGENT_DIR" ]; then
  AGENT_DIR="$HOME/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-toolkit/1.0.0/agents"
fi
export AGENT_DIR

echo ""
echo "  ┌─────────────────────────────────────┐"
echo "  │  Agent Chatroom                     │"
echo "  │  Backend:  http://127.0.0.1:3001    │"
echo "  │  Frontend: http://localhost:4201    │"
echo "  │  AGENT_DIR: $AGENT_DIR"
echo "  └─────────────────────────────────────┘"
echo ""

# Kill existing processes on our ports
lsof -ti:3001 2>/dev/null | xargs kill 2>/dev/null || true
lsof -ti:4201 2>/dev/null | xargs kill 2>/dev/null || true
sleep 1

# Start backend
cd apps/backend
bun run --hot src/index.ts &
BACKEND_PID=$!
cd "$DIR"

sleep 2

# Start frontend
cd apps/frontend
bunx vite --port 4201 &
FRONTEND_PID=$!
cd "$DIR"

sleep 1

echo ""
echo "  Backend PID:  $BACKEND_PID"
echo "  Frontend PID: $FRONTEND_PID"
echo ""
echo "  Open http://localhost:4201 in your browser"
echo "  Press Ctrl+C to stop both servers"
echo ""

# Cleanup on exit
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo ''; echo 'Servers stopped.'" EXIT

# Wait for either to exit
wait
