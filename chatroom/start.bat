@echo off
REM Agent Chatroom — Windows startup script

cd /d "%~dp0"

REM Install deps if needed
if not exist "node_modules" (
  echo [chatroom] Installing dependencies...
  call bun install
)

REM Resolve agent directory
if "%AGENT_DIR%"=="" (
  set "AGENT_DIR=%USERPROFILE%\.claude\plugins\cache\unmassk-claude-toolkit\unmassk-toolkit\1.0.0\agents"
)

echo.
echo   Agent Chatroom
echo   Backend:  http://127.0.0.1:3001
echo   Frontend: http://localhost:4201
echo   AGENT_DIR: %AGENT_DIR%
echo.

REM Kill existing processes on ports
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3001 ^| findstr LISTENING') do taskkill /PID %%a /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :4201 ^| findstr LISTENING') do taskkill /PID %%a /F >nul 2>&1
timeout /t 1 >nul

REM Start backend
start "chatroom-backend" /b cmd /c "cd apps\backend && bun run --hot src/index.ts"
timeout /t 2 >nul

REM Start frontend
start "chatroom-frontend" /b cmd /c "cd apps\frontend && bunx vite --port 4201"
timeout /t 1 >nul

echo.
echo   Open http://localhost:4201 in your browser
echo   Press Ctrl+C to stop
echo.

REM Keep alive
pause
