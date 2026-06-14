# Docker — Build, Push & Deploy

Dua image yang dihasilkan:

| Service  | Image                              | Port |
| -------- | ---------------------------------- | ---- |
| backend  | `rezeki1/ig-scraper-backend:latest`  | 8000 |
| frontend | `rezeki1/ig-scraper-frontend:latest` | 3000 |

---

## 1. Sekali setup

```bash
cp .env.example .env      # lalu sesuaikan kalau perlu
docker login              # login akun Docker Hub "rezeki1"
```

> **Penting (frontend):** `NEXT_PUBLIC_API_URL` di-_bake_ saat **build**, bukan
> saat run. Untuk server, isi dulu di `.env` dengan URL publik backend
> (mis. `https://api.domainmu.com`) **sebelum** `docker compose build`. Kalau
> hanya jalan lokal, biarkan `http://localhost:8000`.

## 2. Build + push image

```bash
docker compose build      # build kedua image dgn tag rezeki1/*
docker compose push       # push ke Docker Hub
```

Mau ngebut: `docker compose build && docker compose push`
(atau jalankan `docker-build-push.bat` di Windows).

## 3. Deploy di server (pakai image yang sudah di-push)

```bash
docker compose pull       # tarik image terbaru, tanpa build ulang
docker compose up -d
```

Cek: `docker compose ps` dan `docker compose logs -f backend`.

---

## Catatan

- **Jaringan `dokploy-network`** bersifat `external` — sudah ada kalau pakai
  Dokploy. Untuk uji coba mandiri tanpa Dokploy, buat dulu:
  `docker network create dokploy-network`.
- **Jalan lokal full (build + run sekaligus)** tanpa Dokploy: pakai
  `docker compose -f docker-compose.local.yml up -d --build`
  (network bridge sendiri + port 8000/3000 langsung ke host).
- **Volume persist:** `backend_data` (snapshot), `backend_session` (cookie login
  IG), `backend_output` (hasil scrape/deep scrape). Aman saat container di-restart.
- **`platform: linux/amd64`** dipasang biar image jalan di VPS x86 walau di-build
  dari mesin ARM. Build dari Windows/Intel = native, tanpa overhead.
- **Login Instagram** dilakukan runtime (cookie tersimpan di volume
  `backend_session`), jadi tidak ikut ter-bundle ke image.
