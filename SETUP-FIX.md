# 🔧 Cara Fix Error & Setup Backend

## Kenapa Muncul Error `reportMissingImports`?

Error itu **bukan error di kode kamu** — itu cuma VS Code (Pylance) yang belum
menemukan package Python. Penyebabnya:

1. **fastapi, uvicorn, pydantic** belum di-`pip install`
2. **session_manager** ada di folder berbeda, jadi Pylance bingung

Kedua masalah ini hilang setelah setup di bawah.

---

## 📁 Struktur File yang Benar

Semua kode Python masuk ke folder `backend/`:

```
ig-scraper-ui/
├── backend/
│   ├── main.py                       ← FastAPI (sudah saya buatkan)
│   ├── requirements.txt              ← semua dependencies
│   ├── pyrightconfig.json            ← fix Pylance
│   ├── .env
│   │
│   └── engine/                       ← PINDAHKAN SEMUA FILE SCRAPER KE SINI
│       ├── __init__.py
│       ├── scraper_post.py           ← (file kamu)
│       ├── profile_scraper.py        ← (file kamu)
│       ├── sentiment_analyzer_v2.py  ← (file kamu)
│       ├── session_manager.py        ← (file kamu)
│       ├── cookie_injector.py        ← (file kamu)
│       ├── storage_manager.py        ← (kalau ada)
│       └── followers_tracker.py      ← (kalau ada)
│
├── frontend/                         ← Next.js
└── .vscode/settings.json             ← fix Pylance global
```

---

## 🚀 Langkah Setup (Windows)

### 1. Pindahkan file scraper ke `backend/engine/`

Copy semua file `.py` scraper kamu (scraper_post.py, session_manager.py, dll)
ke dalam folder `backend/engine/`.

### 2. Jalankan setup otomatis

Double-click **`setup-backend.bat`** ATAU manual:

```cmd
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### 3. Pilih Python Interpreter di VS Code

Setelah venv dibuat, error Pylance hilang dengan cara:

1. Tekan `Ctrl + Shift + P`
2. Ketik: **Python: Select Interpreter**
3. Pilih: `.\backend\.venv\Scripts\python.exe`

Sekarang fastapi, uvicorn, pydantic, session_manager semua **terdeteksi** ✅

### 4. Jalankan backend

Double-click **`run-backend.bat`** ATAU:

```cmd
cd backend
.venv\Scripts\activate
uvicorn main:app --reload --port 8000
```

Buka: http://localhost:8000/docs → harusnya muncul Swagger API docs.

### 5. Jalankan frontend (terminal baru)

```cmd
cd frontend
npm install
npm run dev
```

Buka: http://localhost:3000

---

## ⚠️ Penting: Sesuaikan Import di Engine

File scraper kamu saling import begini:
```python
from sentiment_analyzer_v2 import SentimentAnalyzerV2
from cookie_injector import inject_cookies_sync
```

Karena sekarang semua ada dalam folder `engine/` yang sama, **import ini tetap
jalan** TANPA perlu diubah — selama dijalankan dengan `cwd=engine/` (sudah
diatur otomatis di `main.py`).

---

## 🎯 Arsitektur Baru (Lebih Simpel)

Versi lama: 3 proses (Next.js + FastAPI + Flask)
**Versi ini: 2 proses saja** (Next.js + FastAPI)

```
Browser (:3000) → FastAPI (:8000) → subprocess → scraper_post.py
```

FastAPI memanggil scraper langsung via subprocess. Tidak perlu Flask server
terpisah lagi. Lebih mudah di-deploy.

---

## 🌐 Untuk Deploy Nanti

- **Backend**: deploy `backend/` ke VPS / Railway / Render
  - Set env `HEADLESS=True` (server tidak punya display)
  - Jalankan: `uvicorn main:app --host 0.0.0.0 --port 8000`
- **Frontend**: deploy `frontend/` ke Vercel
  - Set env `NEXT_PUBLIC_API_URL` ke URL backend production
  - Update `next.config.ts` rewrites ke URL backend production

> ⚠️ Catatan: Playwright butuh browser Chromium di server. Untuk deploy,
> pertimbangkan Docker dengan base image `mcr.microsoft.com/playwright/python`.
