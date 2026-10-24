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
| 5.3 | Extractor (IA) y normalizador | Hecha |
| 5.4 | Validador, estados y persistencia | Hecha |
| 5.5 | Evaluación con muestras reales | Pendiente |
| 5.6 | Interfaz | Hecha |
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
│   │   ├── pipeline/         # intake, preprocess, segmenter (IA), grouper, extractor (IA),
│   │   │                     # normalize, validate, orchestrator
│   │   ├── storage.py        # Almacenamiento de archivos
│   │   ├── schemas.py        # DTOs de la API
│   │   └── api/              # submissions, documents, files
│   └── tests/
└── frontend/                 # React + Vite + Tailwind: lotes, bandeja de documentos y detalle
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

En otra terminal:

```bash
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

**Interfaz:** *Lotes* (subir imágenes o PDF y ver el progreso de los agentes), *Documentos*
(bandeja con totales por estado, filtros por estado y tipo y búsqueda por RUT o número) y el
detalle de cada documento (imagen con la zona marcada, estados, campos con su texto original,
validación de montos, alertas, pasos y reproceso).

## API

| Método | Ruta | Qué hace |
|---|---|---|
| POST | `/submissions` | Sube un lote (`files`: una o varias imágenes o PDF). Responde al instante y procesa en segundo plano |
| GET | `/submissions` | Lotes recientes con número de archivos y páginas |
| GET | `/submissions/{id}` | Estado del lote, sus archivos, páginas (con su clasificación) y documentos detectados |
| POST | `/submissions/{id}/process` | Reprocesa: retoma lo pendiente y reintenta lo fallido |
| POST | `/submissions/{id}/files/{file_id}/reclassify` | Vuelve a clasificar un archivo desde cero (sus documentos se crean de nuevo) |
| GET | `/documents` | Bandeja: resultado vigente de cada documento (`status`, `doc_type`, `q`) |
| GET | `/documents/stats` | Totales por estado y por tipo |
| GET | `/documents/{id}` | Documento: datos normalizados, estado y texto original de cada campo, alertas, pasos e historial |
| POST | `/documents/{id}/reprocess` | Vuelve a extraer y validar; el resultado actual sigue vigente hasta que el nuevo termine bien |
| GET | `/files/{id}` | Archivo original |
| GET | `/pages/{id}/image` | Imagen de una página (lo que ve la IA) |
| GET | `/regions/{id}/crop` | Recorte de un documento que comparte página con otros |

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
