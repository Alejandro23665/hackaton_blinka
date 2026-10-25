# Procesamiento de documentos con agentes de IA (Oxxo)

Recibe imágenes o PDF con guías de despacho, controles internos y facturas electrónicas; separa y
clasifica cada documento, extrae sus datos, valida los montos y guarda una fila por documento en
`documentos_procesados`. Los no legibles y los descuadrados quedan marcados para revisión humana.
Diseño en [docs/01-diseno.md](docs/01-diseno.md).

> El proyecto anterior (Rekreuz, aprobación de pagos) se conserva en la rama `rekreuz-final`.

## Estado

| Etapa | Contenido | Estado |
|---|---|---|
| 5.1–5.4 | Lectura con IA: segmentar, clasificar, extraer (doble lectura), normalizar y validar | Hecha |
| 5.5 | Evaluación con muestras reales | En curso (58 imágenes) |
| R1 | Base de datos desde cero (4 tablas, `db/*.sql`) y backend adaptado | Hecha |
| R2 | Interfaz adaptada a la base nueva | Hecha |
| 5.7 | Despliegue | Pendiente |

## Base de datos

Se define **solo** con los archivos SQL de [`db/`](db/), que se aplican en orden:

| Tabla | Qué guarda |
|---|---|
| `roles` | Roles de la aplicación |
| `usuarios` | Nombre, email (único), hash de la contraseña y rol |
| `tipos_documentos` | Solo 3 registros: FC (factura electrónica), CI (control interno), GD (guía de despacho) |
| `documentos_procesados` | Una fila por documento: RUT del proveedor, folio, fecha, firma, neto, IVA, impuestos (otros impuestos + exento), total, observaciones (`LEGIBLE`, `NO_LEGIBLE`, `DESCUADRE`), `requiere_revision` (se calcula sola), tipo e imagen original |

- Los documentos desconocidos (boletas, notas de crédito…) se descartan: no se guardan.
- El mismo documento (tipo, RUT y folio) no se guarda dos veces; no aplica al RUT ilegible `1-9`.
- Todo el sistema es del proyecto Oxxo: no hay tabla de proyectos.

```bash
python -m app.db.schema               # crea las tablas si la base está vacía
python -m app.db.schema ../db/005_x.sql   # aplica un archivo nuevo a una base existente
```

## Estructura

```
hackaton_blinka/
├── db/                       # Definición de la base: 001_..., 002_... (en orden)
├── docs/                     # Diseño y despliegue
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI
│   │   ├── core/config.py    # Configuración (.env)
│   │   ├── models.py         # Las 4 tablas (para leer y escribir; no las crea)
│   │   ├── db/schema.py      # Aplica db/*.sql
│   │   ├── ai/client.py      # OpenRouter: reintentos, JSON estricto y caché de respuestas
│   │   ├── pipeline/         # preprocess, segmenter (IA), grouper, extractor (IA), normalize,
│   │   │                     # validate, process (guarda la fila), jobs (avance en memoria)
│   │   ├── storage.py        # Almacenamiento de archivos
│   │   └── api/              # trabajos, documentos
│   └── tests/
└── frontend/                 # React + Vite + Tailwind: Subir, Documentos y detalle
```

## Puesta en marcha

```bash
cp .env.example .env
docker compose up -d db          # o un PostgreSQL local

cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements-dev.txt
python -m app.db.schema
uvicorn app.main:app --reload    # http://localhost:8000/docs
```

En otra terminal:

```bash
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

**Interfaz:** *Subir* (imágenes o PDF y el avance de cada trabajo: documentos guardados,
descartados, duplicados o con error), *Documentos* (totales, filtros por tipo, observaciones y
"requieren revisión", búsqueda por RUT o folio) y el detalle de cada documento (archivo original con
zoom, datos guardados y suma de montos).

## API

| Método | Ruta | Qué hace |
|---|---|---|
| POST | `/trabajos` | Sube imágenes o PDF (`files`). Responde al instante con el trabajo y procesa en segundo plano, de a un trabajo por vez |
| GET | `/trabajos` | Trabajos recientes (desde que arrancó el servidor) |
| GET | `/trabajos/{id}` | Avance: estado de cada archivo y qué pasó con cada documento (guardado, descartado, duplicado o error) |
| GET | `/documentos` | Documentos, los más recientes primero. Filtros: `tipo`, `observaciones`, `requiere_revision`, `q` (RUT o folio), `limite`, `desde` |
| GET | `/documentos/resumen` | Totales por observaciones y por tipo, y cuántos requieren revisión |
| GET | `/documentos/{id}` | Un documento |
| GET | `/documentos/{id}/imagen` | El archivo original del que salió |
| GET | `/tipos-documentos` | FC, CI y GD |

El avance de los trabajos vive en memoria: si el servidor se reinicia se pierde, pero los documentos
ya guardados quedan en la base. Si se agota la cuota de la IA el trabajo se detiene y los archivos
restantes quedan como omitidos; al volver a subirlos, la caché evita repetir llamadas y los ya
guardados se informan como duplicados.

**Caché de la IA:** cada respuesta del modelo se guarda en `backend/.ai_cache/` (excluida de git).
Una llamada idéntica (misma imagen, mismas instrucciones, mismo modelo) no vuelve a gastar cuota.

## Evaluación con muestras reales

Las imágenes van en `muestras/imagenes/` (excluida de git: son documentos reales).

```bash
cd backend
python -m app.evaluation.run                 # procesa las pendientes y genera el informe
python -m app.evaluation.run --limite 10     # como mucho 10 imágenes nuevas
python -m app.evaluation.run --solo-informe  # solo compara, sin llamar a la IA
```

- Usa una base aparte (`<tu base>_evaluacion`, con las mismas tablas) y `backend/storage_eval/`: no toca tus datos.
- Si se agota la cuota se detiene; al volver a ejecutarlo retoma donde quedó (la caché evita repetir llamadas).
- `muestras/respuestas.json`: las respuestas correctas, con otros impuestos y exento por separado; al
  comparar se suman en `impuestos`. Un valor `null` significa que el documento no permite obtenerlo.
- `muestras/resultados/informe.md`: clasificación, observaciones, firma y, por campo, correctos,
  omitidos e **inventados** (un valor distinto del correcto: el error grave).

## Tests

```bash
cd backend
pytest                                         # sin base: lectura, normalizador y validador
TEST_DATABASE_URL=postgresql+psycopg://…/test pytest   # todos (la base de pruebas se crea con db/*.sql)
```

Los tests usan documentos **sintéticos**. Las muestras reales van en `muestras/` (excluida de git).
