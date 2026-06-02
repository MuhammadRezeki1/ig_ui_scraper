@echo off
REM Jalankan FastAPI backend
cd backend
call .venv\Scripts\activate.bat
echo Starting FastAPI on http://localhost:8000
echo API Docs: http://localhost:8000/docs
uvicorn main:app --reload --port 8000
