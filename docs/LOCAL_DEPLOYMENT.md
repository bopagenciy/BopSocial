# Bop Social — Local Deployment & Packaging Runbook

## Overview

This runbook defines the official local build, packaging, and deployment workflow for **Bop Social**.

Due to Windows BuildKit multi-stage node limitations and local ecosystem coexistence with other Bop Universe applications (such as BopHub on port 3000), Bop Social uses a decoupled, repeatable local build architecture:
1. **Frontend**: React SPA compiled on the host (`npm run build`), then packaged into a lightweight, high-performance Nginx 1.27 container (`Dockerfile.bopsocial-local`).
2. **Backend**: Django ASGI/Channels/Celery container built from `./backend` using the pinned Python 3.12 environment (`Dockerfile`).
3. **Port Strategy**: Default frontend binding on port **`3010`** (`http://localhost:3010`), ensuring zero collision with BopHub or other ecosystem services. Backend binds to `127.0.0.1:8000`.
4. **Data Isolation**: Persistent PostgreSQL and Redis volumes (`agencyos_pgdata`, `agencyos_media`) remain strictly preserved across deploys.

---

## 1. Local Image Identifiers

All locally compiled images must strictly follow the `bopsocial-*-local` naming convention:
* **Frontend**: `bopsocial-frontend-local:bs-1.1`
* **Backend, Worker & Beat**: `bopsocial-backend-local:bs-1.1`

> [!WARNING]
> Never tag or push local images to the upstream GHCR maintainer namespace (`ghcr.io/cbsshekhawat18-lab/*`).

---

## 2. Build & Packaging Workflow

### Step 1: Frontend Host Build
Run the React build from the `frontend/` directory:
```powershell
cd frontend
npm run build
cd ..
```
*Output*: Optimized production assets generated in `frontend/build/` (excluded from git tracking via `.gitignore`).

### Step 2: Package Frontend Nginx Container
Package the pre-built React bundle and SEC-01 Nginx reverse proxy configuration into the local image:
```powershell
docker build -f Dockerfile.bopsocial-local -t bopsocial-frontend-local:bs-1.1 .
```

### Step 3: Build Backend Container
Build the Bop Social backend image containing SEC-01 tenant media isolation and BS-1 branding:
```powershell
docker build -t bopsocial-backend-local:bs-1.1 ./backend
```

---

## 3. Deploying with Local Compose Override

Bop Social provides `docker-compose.local.yml` to automatically override upstream images with local builds without altering root `docker-compose.yml` defaults.

### Start the Stack:
```powershell
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d
```

### Update Services Granularly:
To update frontend or backend independently without touching databases or other services:
```powershell
# Update only frontend
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d frontend

# Update backend, worker, and beat
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d backend worker beat
```

---

## 4. Verification & Operational Checks

### 4.1 Verify Running Image Identities
Ensure all Bop Social services are running the local BS-1.1 images:
```powershell
docker inspect agencyos-frontend-1 --format '{{.Config.Image}}'
# Expected: bopsocial-frontend-local:bs-1.1

docker inspect agencyos-backend-1 --format '{{.Config.Image}}'
# Expected: bopsocial-backend-local:bs-1.1
```

### 4.2 Verify Backend Security Module Active in Container
Verify that BS-0.1 security controls (`social_stats.media_security`) are active in the running container:
```powershell
docker exec agencyos-backend-1 python -c "import social_stats.media_security; print('SEC-01 active in container')"
```

### 4.3 Verify Frontend Web Serving
```powershell
curl -s -I http://localhost:3010/
# Expected: HTTP/1.1 200 OK
```

### 4.4 Verify Nginx Media Protection
Ensure unauthenticated access to protected internal media is blocked:
```powershell
curl -s -I http://localhost:3010/internal_media/
# Expected: HTTP/1.1 404 Not Found (internal only)
```

---

## 5. Safety & Cleanup Constraints

* **Do NOT run** `docker compose down -v` (destroys PostgreSQL database and media).
* **Do NOT run** `docker system prune -a` or `docker builder prune` (risks deleting cache and unrelated container images).
* Always preserve existing volume mounts (`pgdata`, `media`).
