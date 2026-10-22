# Bop Social — Local Runtime Architecture & Isolation Guide

## 1. Overview & Objectives

In phase **BS-INFRA-1**, Bop Social local runtime was permanently decoupled and isolated from upstream Docker image registries (`ghcr.io/cbsshekhawat18-lab/*`). 

Previously, Compose files referenced upstream image tags, which caused Docker Compose to periodically revert to upstream container layers (such as the legacy Social Stats landing page) whenever containers were rebuilt or pulled.

This guide details the local runtime architecture, image naming standards, host-build workflow for React, operational scripts, and persistence guarantees.

---

## 2. Image Architecture & Naming Standards

All application services in Docker Compose now use strictly local image tags owned by Bop Social:

| Service | Dockerfile | Image Tag | Base Image | Pull Policy |
| :--- | :--- | :--- | :--- | :--- |
| **backend** | `backend/Dockerfile` | `bopsocial-backend:local` | `python:3.12-slim` | `build` |
| **worker** | `backend/Dockerfile` | `bopsocial-backend:local` | `python:3.12-slim` | `build` |
| **beat** | `backend/Dockerfile` | `bopsocial-backend:local` | `python:3.12-slim` | `build` |
| **frontend** | `frontend/Dockerfile.runtime` | `bopsocial-frontend:local` | `nginx:1.27-alpine` | `build` |
| **postgres** | Docker Hub | `postgres:16-alpine` | Official Postgres | Standard |
| **redis** | Docker Hub | `redis:7-alpine` | Official Redis | Standard |

### Pull Policy Enforcement
Both `docker-compose.yml` and `docker-compose.local.yml` define `pull_policy: build` for application services, guaranteeing that Compose never attempts to pull remote images or revert to upstream registry tags.

---

## 3. Frontend Build & Serving Architecture

### WSL / BuildKit Memory Mitigation
Building complex React bundles with Webpack/Babel directly inside Docker on Windows WSL2 often encounters out-of-memory terminations or severe performance degradation.

To ensure fast, reliable, and deterministic builds:
1. **Host Compilation:** React is compiled natively on the host machine via `npm run build` inside `frontend/`. This produces production artifacts in `frontend/build/`.
2. **Lightweight Runtime Container (`frontend/Dockerfile.runtime`):**
   ```dockerfile
   FROM nginx:1.27-alpine
   COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
   EXPOSE 80
   ```
3. **Read-Only Bind Mount in Compose:**
   ```yaml
   volumes:
     - ./frontend/build:/usr/share/nginx/html:ro
     - media:/srv/media:ro
   ```
   The compiled assets in `frontend/build/` are mounted directly into Nginx's document root in read-only mode (`:ro`). Any build generated on the host is immediately authoritative in the running container without requiring container rebuilds or `docker cp` commands.

---

## 4. Reverse Proxy Routing (`docker/nginx.conf`)

The Nginx container (`agencyos-frontend-1`) listens on internal port `80` (mapped to host `3010`) and handles reverse proxying:
- `/` -> Serves static React production bundle from `/usr/share/nginx/html`.
- `/api/` -> Proxied to Django backend `http://backend:8000/api/`.
- `/admin/` -> Proxied to Django backend `http://backend:8000/admin/`.
- `/media/` -> Serves media files directly from persistent volume `/srv/media`.

Direct backend access is also available on host port `8010` (`127.0.0.1:8010 -> 8000`).

---

## 5. Operational Scripts

Two canonical PowerShell scripts in `scripts/` automate stack operations:

### A. Starting the Stack (`scripts/start-bopsocial.ps1`)
```powershell
powershell -File scripts/start-bopsocial.ps1
```
Or with parameter to skip host React build if already built:
```powershell
powershell -File scripts/start-bopsocial.ps1 -SkipFrontendBuild
```

**Execution Pipeline:**
1. Verifies Docker daemon status.
2. Compiles React frontend on host (`npm run build`).
3. Starts databases (`postgres`, `redis`) and waits for healthchecks (`healthy`).
4. Builds local runtime images (`bopsocial-backend:local`, `bopsocial-frontend:local`).
5. Starts backend service (`backend`) and waits for health check (`healthy`).
6. Starts remaining services (`frontend`, `worker`, `beat`).
7. Prints verified service status and endpoints.

### B. Stopping the Stack (`scripts/stop-bopsocial.ps1`)
```powershell
powershell -File scripts/stop-bopsocial.ps1
```
Or to remove containers and network while preserving data volumes:
```powershell
powershell -File scripts/stop-bopsocial.ps1 -Down
```

---

## 6. Data Integrity & Volume Safety

### Persistent Volumes
- `pgdata`: Holds PostgreSQL database records (posts, analytics snapshots, rollups, credentials, tenant configurations).
- `media`: Holds uploaded media files and assets.

### Strict Rules:
- **NEVER** run `docker compose down -v` or `docker volume rm`.
- **NEVER** run un-scoped `docker system prune` that might delete dangling project volumes.
- Both scripts (`start-bopsocial.ps1` and `stop-bopsocial.ps1`) strictly isolate compose commands to prevent data loss.

---

## 7. Developer Workflow & Troubleshooting

### Updating Frontend Code
When modifying code in `frontend/src/`:
1. Compile changes:
   ```powershell
   cd frontend
   npm run build
   cd ..
   ```
2. The changes are immediately served at `http://localhost:3010/` because `./frontend/build` is bind-mounted directly. No Docker container restart is required.

### Updating Backend Code
Code in `backend/` is mounted live into `/app` during local execution:
- Python code changes auto-reload via Gunicorn/Django dev server.
- If dependency changes (`requirements.txt`) are introduced, rebuild local backend image:
   ```powershell
   docker compose build backend
   docker compose up -d backend worker beat
   ```
