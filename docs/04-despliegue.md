# Despliegue (Railway o Render)

Blinka se despliega como **un solo servicio Docker** (FastAPI sirve la API y el frontend
compilado) más **una base PostgreSQL** gestionada. Las facturas subidas se guardan en Postgres,
así que no hace falta disco persistente.

```
Navegador ──► https://tu-app ──► FastAPI ─┬─ /vendors, /invoices… (API)
                                          ├─ /            (frontend compilado)
                                          └─ PostgreSQL   (datos + archivos)
                                   OpenRouter ◄── lectura de facturas
```

## Variables de entorno

| Variable | Obligatoria | Valor |
|---|---|---|
| `DATABASE_URL` | Sí | La da la plataforma al crear Postgres (`postgres://…` sirve tal cual) |
| `OPENROUTER_API_KEY` | Sí | Tu clave de OpenRouter |
| `ACCESS_PASSWORD` | Muy recomendada | Contraseña para entrar (usuario: `blinka`). Sin ella, cualquiera con la URL puede aprobar pagos o gastar tu cuota |
| `OPENROUTER_MODEL` | No | Por defecto `nvidia/nemotron-3.5-super-vl:free` |
| `ACCESS_USER` | No | Usuario de acceso (por defecto `blinka`) |

`PORT` lo asigna la plataforma automáticamente. Las migraciones (`alembic upgrade head`) se
ejecutan solas en cada arranque.

## Opción A · Railway (recomendada para la demo: el servicio no se duerme)

1. En railway.com: **New Project → Deploy from GitHub repo** → elige `hackaton_blinka`.
   Railway detecta el `Dockerfile` y `railway.json`.
2. En el proyecto: **+ New → Database → PostgreSQL**.
3. En el servicio `hackaton_blinka` → **Variables**:
   - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}` (referencia a la base del paso 2)
   - `OPENROUTER_API_KEY` = tu clave
   - `ACCESS_PASSWORD` = una contraseña para la demo
4. **Settings → Networking → Generate Domain** para obtener la URL pública.
5. Cargar la empresa ficticia (una vez): en el servicio, abre una consola (**⋯ → Shell** o
   `railway ssh` con la CLI) y ejecuta:
   ```bash
   python -m app.demo --reset --yes
   ```

## Opción B · Render

1. En render.com: **New → Blueprint** → elige el repositorio. Render lee `render.yaml` y crea
   la base `blinka-db` y el servicio `blinka`.
2. Te pedirá `OPENROUTER_API_KEY` y `ACCESS_PASSWORD`. `DATABASE_URL` se conecta sola.
3. Cuando termine el despliegue, en el servicio → **Shell**: `python -m app.demo --reset --yes`.

> Ojo con el plan gratuito de Render: el servicio se duerme tras un rato sin uso y tarda en
> despertar (mala experiencia en una demo en vivo), y la base gratuita caduca a los pocos días o
> semanas. Revisa las condiciones vigentes de cada plataforma antes de elegir.

## Comprobar el despliegue

- `https://tu-app/health` → `{"status":"ok"}` (sin contraseña: lo usa la plataforma).
- `https://tu-app/` → pide usuario `blinka` y la contraseña → aparece el panel de Andes Digital.
- `https://tu-app/docs` → documentación de la API (también protegida).

## Antes de la demo

- La cuota gratuita de OpenRouter es de **50 lecturas al día** (se renueva a las 00:00 UTC).
  Cada factura subida usa ~1. No ejecutes la evaluación `--mode agente` el mismo día contra
  esa clave, o carga 10 USD de créditos para subir el límite a 1.000/día.
- Para empezar limpio: `python -m app.demo --reset --yes` en la consola del servicio.

## Desarrollo local

Nada cambia: backend con `uvicorn app.main:app --reload` (puerto 8000) y frontend con
`npm run dev` (puerto 5173). Para probar el modo producción en local:

```bash
cd frontend && npm run build
cd ../backend && ACCESS_PASSWORD=prueba uvicorn app.main:app --port 8010
# abre http://localhost:8010 (usuario blinka / prueba)
```
