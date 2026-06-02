@echo off
REM ================================================================
REM  IG Scraper - Setup Backend (Windows)
REM ================================================================
echo ===============================================
echo   SETUP BACKEND - Instagram Scraper
echo ===============================================

cd backend

echo.
echo [1/4] Membuat virtual environment...
python -m venv .venv

echo.
echo [2/4] Mengaktifkan venv...
call .venv\Scripts\activate.bat

echo.
echo [3/4] Install dependencies...
pip install --upgrade pip
pip install -r requirements.txt

echo.
echo [4/4] Install Playwright browser...
playwright install chromium

echo.
echo ===============================================
echo   SETUP SELESAI!
echo ===============================================
echo.
echo Jalankan backend dengan:
echo   cd backend
echo   .venv\Scripts\activate
echo   uvicorn main:app --reload --port 8000
echo.
pause
