@echo off
title IG Scraper UI

echo =======================================
echo   IG SCRAPER UI - QUICK START (Windows)
echo =======================================

:: Terminal 1 - FastAPI Bridge
start "FastAPI Bridge" cmd /k "cd /d %~dp0backend && .venv\Scripts\activate && python main.py"

timeout /t 3 /nobreak > nul

:: Terminal 2 - Next.js
start "Next.js UI" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Semua service dimulai!
echo Dashboard : http://localhost:3000
echo FastAPI   : http://localhost:8000
echo API Docs  : http://localhost:8000/docs
echo.
echo Jangan lupa jalankan Flask Engine (instagram_api_server.py) secara terpisah!
pause