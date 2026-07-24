# Panduan Setup Variabel Environment (`.env`)

Dokumen ini menjelaskan **cara membuat/mengisi** setiap variabel di `backend/.env`.  
Template: `backend/.env.example` — salin dulu:

```powershell
cd backend
copy .env.example .env
```

Jangan commit file `.env` (sudah di-ignore).

---

## 1. Cek infrastruktur lokal

```powershell
# dari root repo
docker compose -f infra/compose.yaml up -d
docker compose -f infra/compose.yaml ps
```

| Service | Port host | Dipakai untuk |
|---|---|---|
| PostgreSQL | **5434** | Database (bukan 5433 — bentrok PostgreSQL Windows lokal) |
| Redis | **6379** | Session admin, rate limit, Celery |
| MinIO | **9000** / **9001** | Object storage opsional (`s3`) |

---

## 2. Variabel wajib (API jalan tanpa OAuth/LLM/X)

### `APP_ENV`
- **Isi:** `development` | `test` | `production`
- **Lokal:** `development`
- Cookie admin `Secure` hanya aktif di `production`.

### `API_BASE_PATH`
- **Isi:** `/api/v1` (default)
- Prefix semua route publik/admin.

### `FRONTEND_URL`
- **Isi:** URL Vite, contoh `http://localhost:5173`
- Dipakai redirect OAuth admin & konfirmasi alert.

### `CORS_ORIGINS`
- **Isi:** origin frontend, contoh `http://localhost:5173`
- Bisa comma-separated: `http://localhost:5173,http://127.0.0.1:5173`

### `DATABASE_URL`
- **Format:** `postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DB`
- **Lokal Compose:**  
  `postgresql+asyncpg://devradar:devradar@127.0.0.1:5434/devradar`
- Driver **harus** `asyncpg` (bukan `psycopg2`).

### `REDIS_URL`
- **Lokal:** `redis://127.0.0.1:6379/0`

### Secrets (wajib diganti, jangan pakai default repo)

Generate di PowerShell (jalankan 3× untuk 3 secret berbeda):

```powershell
[Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Maximum 256 }) -as [byte[]])
```

| Variable | Kegunaan | Syarat |
|---|---|---|
| `SESSION_SECRET` | HMAC IP hash, hash token konfirmasi alert, material session | ≥ 32 karakter random |
| `EMAIL_ENCRYPTION_KEY` | Enkripsi email subscriber (Fernet dari SHA-256 material) | String rahasia panjang |
| `EMAIL_HMAC_KEY` | Lookup hash email (bukan plaintext) | ≥ 32 karakter random |

**Cara “mendapatkan”:** Anda **buat sendiri** (generate), bukan dari dashboard pihak ketiga.

---

## 3. Object storage (Task 6)

### `OBJECT_STORAGE_BACKEND`
| Nilai | Kapan |
|---|---|
| `local` | **Recommended lokal** — simpan file di disk, tanpa MinIO |
| `s3` | MinIO/AWS S3 |
| `memory` | Hanya testing in-process |

### Mode `local`
```
OBJECT_STORAGE_BACKEND=local
OBJECT_STORAGE_LOCAL_PATH=./data/raw
```
Folder dibuat otomatis; di-ignore git.

### Mode `s3` (MinIO lokal)
1. Pastikan container MinIO up (port 9000).
2. Buat bucket `devradar-raw` di console `http://localhost:9001`  
   - User/password default Compose: lihat `infra/compose.yaml` (`devradar` / `devradar123` jika disetel begitu).
3. Isi:

```
OBJECT_STORAGE_BACKEND=s3
OBJECT_STORAGE_ENDPOINT=http://127.0.0.1:9000
OBJECT_STORAGE_BUCKET=devradar-raw
OBJECT_STORAGE_ACCESS_KEY=devradar
OBJECT_STORAGE_SECRET_KEY=devradar123
OBJECT_STORAGE_REGION=us-east-1
```

**Production:** buat IAM user / access key di AWS (atau R2/GCS S3-compatible); **jangan** pakai key dev.

---

## 4. Fetch policy (opsional)

| Variable | Default | Arti |
|---|---|---|
| `FETCH_TIMEOUT_SECONDS` | `20` | Timeout HTTP fetch |
| `FETCH_MAX_BYTES` | `5242880` | Max body 5 MiB |
| `FETCH_MAX_REDIRECTS` | `5` | Batas redirect |

Biasanya tidak perlu diubah.

---

## 5. Admin GitHub OAuth (Task 5) — isi saat butuh login admin

### Cara membuat di GitHub
1. Buka [GitHub Developer Settings → OAuth Apps](https://github.com/settings/developers) → **New OAuth App**.
2. **Homepage URL:** `http://localhost:5173` (atau domain prod).
3. **Authorization callback URL (penting):**  
   `http://127.0.0.1:8000/api/v1/admin/auth/github/callback`  
   (production: `https://API_HOST/api/v1/admin/auth/github/callback`)
4. Setelah create, salin **Client ID**.
5. Generate **Client Secret** → salin sekali (tidak ditampilkan lagi).

### Variabel
```
GITHUB_CLIENT_ID=Iv1.xxxxxxxx
GITHUB_CLIENT_SECRET=xxxxxxxxxxxxxxxx
ADMIN_GITHUB_IDS=12345678
```

### Cara dapat `ADMIN_GITHUB_IDS`
1. Login GitHub → buka profil, atau API:  
   `https://api.github.com/users/USERNAME` → field **`id`** (angka).
2. Beberapa admin: `12345678,87654321` (comma-separated).
3. Hanya ID di allowlist yang boleh jadi admin.

Tanpa OAuth, API catalogue/submission tetap jalan; endpoint admin akan gagal login.

---

## 6. Email alerts (Task 10)

```
EMAIL_PROVIDER=console
EMAIL_FROM=alerts@example.test
```

| Provider | Cara setup |
|---|---|
| `console` | Default dev — email “dikirim” ke log, **tidak** butuh akun |
| Production (nanti) | Integrasi SES/SendGrid/dll. di `EmailProvider`; set API key lewat env baru saat diimplementasi |

Konfirmasi alert butuh `SESSION_SECRET` + encryption keys (sudah di bagian 2).

---

## 7. LLM extraction (structured fields only — **bukan** web search)

OpenAI dipakai **hanya** untuk mengisi field kosong setelah fetch+parse halaman (rule-first).  
Search catalogue tetap dari **PostgreSQL**, bukan live OpenAI web_search.

```
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-...
# Alias opsional (jika LLM_API_KEY kosong):
# OPENAI_API_KEY=sk-...
```

| Isi `LLM_PROVIDER` | Perilaku |
|---|---|
| `disabled` / kosong | Rule-based saja, **tidak** call API |
| `openai` | Chat Completions `response_format=json_object` setelah fetch |

### Cara setup OpenAI
1. Buka [OpenAI API keys](https://platform.openai.com/api-keys) → **Create new secret key**.
2. Pastikan akun punya **billing** aktif (pay-as-you-go).
3. Paste key ke `LLM_API_KEY` di `backend/.env` (atau `OPENAI_API_KEY`).
4. Model default: `gpt-4o-mini` (murah, cocok extraction).
5. Restart API/Celery worker agar env ter-load.

### Catatan
- Tanpa key + `LLM_PROVIDER=openai` → otomatis fallback **disabled** (log warning).
- Jangan commit `.env` / key.
- Worker Celery (`fetch` queue) yang menjalankan extract; pastikan worker dijalankan di folder `backend` dengan `.env` yang sama.

---

## 8. X / Twitter discovery (Task 11)

```
X_BEARER_TOKEN=
```

### Cara mendapatkan
1. Daftar [X Developer Platform](https://developer.x.com/) / Twitter Developer.
2. Buat Project + App dengan akses **recent search** (berbayar sesuai tier X).
3. Generate **Bearer Token**.
4. Paste ke `X_BEARER_TOKEN`.

Biarkan kosong sampai Anda siap bayar usage; connector offline tetap ditest dengan fake client.

---

## 9. Checklist setup pertama kali

1. [ ] `docker compose -f infra/compose.yaml up -d`
2. [ ] `copy backend\.env.example backend\.env`
3. [ ] Isi `SESSION_SECRET`, `EMAIL_ENCRYPTION_KEY`, `EMAIL_HMAC_KEY` (generate)
4. [ ] Biarkan `OBJECT_STORAGE_BACKEND=local`
5. [ ] `cd backend` → `uv run alembic upgrade head`
6. [ ] `uv run uvicorn app.main:app --reload --port 8000`
7. [ ] Buka `http://127.0.0.1:8000/health/ready` → `postgres` + `redis` = `ok`
8. [ ] (Opsional) Isi GitHub OAuth + `ADMIN_GITHUB_IDS`
9. [ ] (Opsional) Celery worker:  
    `uv run celery -A app.worker.celery_app.celery_app worker -Q fetch -l info`

---

## 10. Keamanan singkat

| Jangan | Kenapa |
|---|---|
| Commit `.env` | Bocor secret |
| Share `GITHUB_CLIENT_SECRET` / `X_BEARER_TOKEN` / `LLM_API_KEY` | Akses akun berbayar |
| Masukkan secret ke tabel `sources` | Design: hanya `credential_ref` (nama env) |
| Inject secret ke browser worker | Lihat `BROWSER_WORKER_FORBIDDEN_ENV` |

---

## 11. Ringkasan “dari mana nilainya?”

| Variable | Sumber nilai |
|---|---|
| DB / Redis / MinIO local | `infra/compose.yaml` |
| `SESSION_*` / `EMAIL_*` keys | Generate sendiri |
| `GITHUB_*` | GitHub OAuth App |
| `ADMIN_GITHUB_IDS` | GitHub user numeric `id` |
| `OBJECT_STORAGE_*` (prod) | AWS IAM / MinIO admin |
| `LLM_API_KEY` | Dashboard vendor LLM |
| `X_BEARER_TOKEN` | X Developer portal |

Detail teknis env juga ada di `docs/environment.md`.  
Operasi deploy/rollback: `docs/runbook.md`.  
Kontrak API: `docs/backend-api.md`.
