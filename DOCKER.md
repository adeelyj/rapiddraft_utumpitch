# Docker Guide (RapidDraft)

## What this does
- Builds the frontend (Vite) and serves it from the FastAPI backend in a single container.
- Installs FreeCAD + pythonocc-core inside the Linux container via **conda-forge** (self‑contained, no Windows FreeCAD needed).

---

## Build the image (local)
From repo root:

```bash
docker build -t rapiddraft:local .
```

Optional: set API base URL during build (usually not needed since FastAPI serves frontend).

```bash
docker build -t rapiddraft:local --build-arg VITE_API_BASE_URL= .
```

---

## Run the container (local)

```bash
docker run --rm -p 8000:8000 rapiddraft:local
```

Open:
- UI: http://localhost:8000
- API docs: http://localhost:8000/docs

---

## Where the image is created
- Docker images are stored in Docker Desktop’s internal VM storage.
- You won’t see a file in the repo; it lives inside Docker’s image store.

Check images from CLI:

```bash
docker images
```

You should see `rapiddraft` with tag `local`.

---

## Where to find it in Docker Desktop
1) Open Docker Desktop
2) Go to **Images**
3) Look for `rapiddraft` (tag `local`)
4) You can run it from there or inspect layers/logs.

---

## How it works (Dockerfile summary)
- Stage 1 (Node): build the frontend into `web/dist`
- Stage 2 (Micromamba/Conda):
  - Create a conda env with `python=3.11`, `freecad`, `pythonocc-core`
  - Install `requirements.txt` via pip inside that env
  - Copy `web/dist`
- FastAPI serves the frontend and API from the same container

Key files:
- `Dockerfile`
- `.dockerignore`
- `server/main.py` (serves `web/dist`)

---

## Render deployment (single container)
1) Push repo to GitHub
2) Render → New Web Service → **Docker**
3) Select this repo
4) Render will build from `Dockerfile`
5) Service will listen on `PORT` (handled in Dockerfile CMD)

Notes:
- Render runs Linux containers, so the FreeCAD install is Linux‑based inside the image.
- Windows portable FreeCAD folder is ignored by `.dockerignore`.

---

## Troubleshooting
### FreeCAD import errors in container
Confirm FreeCAD is installed in the image:

```bash
docker run --rm rapiddraft:local bash -lc "python - <<'PY'\nimport FreeCAD\nprint('FreeCAD OK')\nPY"
```

### No UI at http://localhost:8000
- Check container logs in Docker Desktop or via CLI:
  ```bash
  docker logs <container_id>
  ```

---

## Useful commands
```bash
docker build -t rapiddraft:local .
docker run --rm -p 8000:8000 rapiddraft:local
docker images
docker ps
```
