# Despliegue (Railway)

> Se completa en la etapa 5.7. Lo que ya aplica:

El sistema se despliega como **un solo servicio Docker** (FastAPI sirve la API y el frontend
compilado) más **una base PostgreSQL**. Los documentos y las imágenes de páginas se guardan en
disco (`STORAGE_DIR`), así que en producción hace falta un **volumen persistente**: el disco
normal del contenedor se borra en cada despliegue.

## Variables de entorno

| Variable | Obligatoria | Valor |
|---|---|---|
| `DATABASE_URL` | Sí | `${{Postgres.DATABASE_URL}}` (referencia a la base del proyecto) |
| `OPENROUTER_API_KEY` | Sí | Tu clave de OpenRouter |
| `STORAGE_DIR` | Sí | Ruta montada del volumen, por ejemplo `/data/storage` |
| `ACCESS_PASSWORD` | Muy recomendada | Contraseña para entrar (usuario: `blinka`) |
| `OPENROUTER_MODEL` | No | Por defecto `nvidia/nemotron-3.5-super-vl:free` |
| `TOTAL_TOLERANCE_CLP` | No | Diferencia permitida en la suma de montos (por defecto `0`) |

`PORT` lo asigna la plataforma. Las migraciones (`alembic upgrade head`) se ejecutan solas en
cada arranque.

## Railway

1. **New Project → Deploy from GitHub repo**. Railway detecta el `Dockerfile` y `railway.json`.
2. **+ New → Database → PostgreSQL**.
3. En el servicio de la app → **Settings → Volumes → Add volume**, montado en `/data`.
4. En **Variables**: `DATABASE_URL`, `OPENROUTER_API_KEY`, `STORAGE_DIR=/data/storage` y
   `ACCESS_PASSWORD`.
5. **Settings → Networking → Generate Domain**.

Comprobar: `https://tu-app/health` → `{"status":"ok"}` y `https://tu-app/docs` (pide la contraseña).
