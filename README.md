# Procesamiento de documentos con agentes de IA

Recibe lotes de imágenes o PDF con guías de despacho, controles internos y facturas electrónicas;
separa y clasifica cada documento, extrae sus datos, valida los montos y lo guarda todo con
trazabilidad. Diseño completo en [docs/01-diseno.md](docs/01-diseno.md).

> El proyecto anterior (Rekreuz, aprobación de pagos) se conserva en la rama `rekreuz-final`.

## Estado

| Etapa | Contenido | Estado |
|---|---|---|
| 5.1 Base | Modelos, migración, almacenamiento, preprocesador, subida de lotes | Hecha |
| 5.2 | Segmentador-clasificador (IA) y agrupador | Hecha |
| 5.3 | Extractor (IA) y normalizador | Pendiente |
| 5.4 | Validador, estados y persistencia | Pendiente |
| 5.5 | Evaluación con muestras reales | Pendiente |
| 5.6 | Interfaz | Pendiente |
| 5.7 | Despliegue | Pendiente |

## Estructura

```
hackaton_blinka/
├── docs/                     # Diseño y despliegue
├── backend/
│   ├── alembic/versions/     # Migraciones (0008: esquema actual)
│   ├── app/
│   │   ├── main.py           # FastAPI
│   │   ├── core/config.py    # Configuración (.env)
│   │   ├── models/           # Tablas: lotes, archivos, páginas, documentos, procesamientos…
│   │   ├── ai/client.py      # OpenRouter: reintentos, JSON estricto y caché de respuestas
│   │   ├── pipeline/         # intake, preprocess, segmenter (IA), grouper, orchestrator
│   │   ├── storage.py        # Almacenamiento de archivos
│   │   ├── schemas.py        # DTOs de la API
│   │   └── api/              # submissions, files
│   └── tests/
└── frontend/                 # React + Vite + Tailwind (interfaz en la etapa 5.6)
```

## Puesta en marcha

```bash
cp .env.example .env
docker compose up -d db          # o un PostgreSQL local

cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload    # http://localhost:8000/docs
```

## API

| Método | Ruta | Qué hace |
|---|---|---|
| POST | `/submissions` | Sube un lote (`files`: una o varias imágenes o PDF). Responde al instante y procesa en segundo plano |
| GET | `/submissions` | Lotes recientes con número de archivos y páginas |
| GET | `/submissions/{id}` | Estado del lote, sus archivos, páginas (con su clasificación) y documentos detectados |
| POST | `/submissions/{id}/process` | Reprocesa: retoma lo pendiente y reintenta lo fallido |
| GET | `/files/{id}` | Archivo original |
| GET | `/pages/{id}/image` | Imagen de una página (lo que ve la IA) |

Un archivo repetido (mismo contenido) no se guarda dos veces: el lote lo reutiliza y lo avisa.

**Caché de la IA:** cada respuesta del modelo se guarda en `backend/.ai_cache/` (excluida de git).
Una llamada idéntica (misma imagen, mismas instrucciones, mismo modelo) no vuelve a gastar cuota.
Si se agota la cuota o la clave es rechazada, el lote se detiene; `POST /submissions/{id}/process`
lo retoma sin repetir lo ya clasificado.

## Tests

```bash
cd backend
pytest                                         # sin base: solo preprocesador y almacenamiento
TEST_DATABASE_URL=postgresql+psycopg://…/test pytest   # todos (usa una base de pruebas vacía)
```

Los tests usan documentos **sintéticos**. Las muestras reales van en `muestras/` (excluida de git).
