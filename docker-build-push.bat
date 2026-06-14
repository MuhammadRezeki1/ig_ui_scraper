@echo off
REM ===========================================================================
REM Build + push kedua image ke Docker Hub (rezeki1/*).
REM Pakai: klik dobel, atau jalankan `docker-build-push.bat` di terminal.
REM ===========================================================================
setlocal

echo [1/3] Cek login Docker Hub...
docker login || goto :err

echo [2/3] Build image (backend + frontend)...
docker compose build || goto :err

echo [3/3] Push image ke Docker Hub...
docker compose push || goto :err

echo.
echo Selesai. Image sudah ter-push:
echo   - rezeki1/ig-scraper-backend:latest
echo   - rezeki1/ig-scraper-frontend:latest
echo Di server tinggal: docker compose pull ^&^& docker compose up -d
goto :eof

:err
echo.
echo GAGAL. Lihat pesan error di atas.
exit /b 1
