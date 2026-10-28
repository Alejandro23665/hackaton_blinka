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
| `CLAUDE_KEY` | Sí | Tu clave de la API de Claude (Anthropic) |
| `STORAGE_DIR` | Sí | Ruta montada del volumen, por ejemplo `/data/storage` |
| `SECRET_KEY` | Sí | Texto largo y secreto que firma las sesiones (sin ella, se cierran en cada reinicio) |
| `ADMIN_EMAIL` y `ADMIN_PASSWORD` | Sí, la primera vez | Administrador inicial: se crea al arrancar si su email no existe (`ADMIN_NOMBRE` opcional). Después, los perfiles se administran en la pantalla *Perfiles* |
| `AI_MODEL` | No | Por defecto `claude-haiku-5-5` |
| `AI_BATCH` | No | `true` (por defecto): Message Batches, mitad de precio y respuesta asíncrona; `false`: una llamada por solicitud |
| `TOTAL_TOLERANCE_CLP` | No | Diferencia permitida en la suma de montos (por defecto `0`) |

`PORT` lo asigna la plataforma. Al arrancar, si la base está vacía, se crean las tablas con los
archivos `db/*.sql` (`python -m app.db.schema`). Un archivo SQL nuevo se aplica a mano en una base
que ya existe.

## Railway

1. **New Project → Deploy from GitHub repo**. Railway detecta el `Dockerfile` y `railway.json`.
2. **+ New → Database → PostgreSQL**.
3. En el servicio de la app → **Settings → Volumes → Add volume**, montado en `/data`.
4. En **Variables**: `DATABASE_URL`, `CLAUDE_KEY`, `STORAGE_DIR=/data/storage` y
   `SECRET_KEY`, `ADMIN_EMAIL` y `ADMIN_PASSWORD`. Con ese administrador se inicia sesión y se crean
   los demás perfiles en *Perfiles*.
5. **Settings → Networking → Generate Domain**.

Comprobar: `https://tu-app/health` → `{"status":"ok"}` y `https://tu-app/docs` (pide la contraseña).
