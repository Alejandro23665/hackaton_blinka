# Un solo servicio: FastAPI sirve la API y el frontend compilado.
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
# Definición de la base (archivos SQL): app/db/schema.py los busca en ../db
COPY db/ /app/db/
COPY --from=frontend /app/frontend/dist /app/frontend/dist

# Usuario sin privilegios. STORAGE_DIR debe apuntar a un volumen persistente (docs/04-despliegue.md)
RUN useradd --create-home blinka && mkdir -p /app/backend/storage && chown -R blinka /app
USER blinka

EXPOSE 8000
# Sin DATABASE_URL la app usaría el valor de desarrollo (localhost) y fallaría con un traceback
# confuso: se avisa con un mensaje claro. Después, tablas (solo si la base está vacía) y servidor.
CMD ["sh", "-c", "if [ -z \"$DATABASE_URL\" ]; then echo 'ERROR: falta la variable DATABASE_URL. En Railway o Render, conectala a la base Postgres del proyecto (ver docs/04-despliegue.md).' >&2; exit 1; fi; python -m app.db.schema && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
