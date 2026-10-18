# Blinka en un solo servicio: FastAPI sirve la API y el frontend compilado.
# Sirve igual para Render y Railway (ver docs/04-despliegue.md).

# ---- 1) Frontend: se compila y solo se conserva dist/ ----
FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- 2) Backend: Python + el frontend ya compilado ----
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

COPY backend/ ./
COPY --from=frontend /app/frontend/dist /app/frontend/dist
# Set ficticio: permite cargar la demo en el servidor con `python -m app.demo --reset`
COPY dataset/ /app/dataset/

# Usuario sin privilegios
RUN useradd --create-home blinka && chown -R blinka /app
USER blinka

EXPOSE 8000
# Migraciones en cada arranque (idempotentes) y servidor en el puerto que asigna la plataforma
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
