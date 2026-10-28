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
| R3 | Inicio de sesión, dashboard del día y revisión humana (corrección a nombre del usuario) | Hecha |
| R4 | Claude Haiku 5.5 con Message Batches y vista de métricas de IA (tokens, costo, rendimiento) | Hecha |
| 5.7 | Despliegue | Pendiente |

## Base de datos

Se define **solo** con los archivos SQL de [`db/`](db/), que se aplican en orden:

| Tabla | Qué guarda |
|---|---|
| `roles` | `MODELO` (solo el usuario de la IA), `REVISOR` y `ADMINISTRADOR` |
| `usuarios` | Nombre, email (único), hash de la contraseña, rol y `activo` (db/010: un perfil desactivado no inicia sesión). Incluye el usuario "Modelo IA", que no puede iniciar sesión |
| `tipos_documentos` | `id` y `documento`, con solo 3 registros: FC (factura electrónica), CI (control interno), GD (guía de despacho) |
| `carpetas` | Cada carpeta subida (db/009): nombre, fecha de subida y quién la subió. El nombre puede repetirse: cada subida es una carpeta distinta |
| `documentos_procesados` | Una fila por documento: RUT del proveedor, folio, fecha, firma, neto, IVA, impuestos (otros impuestos + exento), total, observaciones (`LEGIBLE`, `NO_LEGIBLE`, `DESCUADRE`), tipo, imagen original, `id_usuario` (el Modelo IA o la persona que lo corrigió), `campos_faltantes` y `campos_dudosos`, `revisado_en`, `id_carpeta` (vacío si se subió suelto) y `requiere_revision` (se calcula sola: no legible o descuadre, y nadie lo ha revisado) |

- Los documentos desconocidos (boletas, notas de crédito…) se descartan: no se guardan.
- El mismo documento (tipo, RUT y folio) no se guarda dos veces; no aplica al RUT ilegible `1-9`.
- Todo el sistema es del proyecto Oxxo: no hay tabla de proyectos.
- `imagen` (db/008): nombre del archivo del documento, `TIPO_RUT_FOLIO` más su extensión (por ejemplo
  `FC_93178000-K_23193169.png`; lo que falta queda vacío, `FC__1458754.png`, y un RUT ilegible se omite). Se
  copia el original con ese nombre al guardar los datos y se renombra si una persona corrige tipo, RUT o
  folio; si el nombre ya existe se agrega `-2`. Para documentos guardados antes: `python -m app.pipeline.rename_images`.
- `llamadas_ia` (db/007): una fila por cada solicitud pagada a la IA (etapa, modelo, tanda, tokens de
  entrada y salida, costo estimado, espera, resultado y documento). Las respuestas de la caché no se registran.
- Un documento corregido por una persona queda a su nombre y sale de la cola de revisión; si el
  documento trae un descuadre real, la persona lo confirma y queda `DESCUADRE` revisado.

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
│   │   ├── auth.py           # Contraseñas (scrypt) y sesiones (token firmado)
│   │   ├── usuarios.py       # Alta de usuarios desde la terminal
│   │   ├── ai/client.py      # Claude (Haiku 5.5): tandas de Message Batches, JSON con esquema y caché
│   │   ├── pipeline/         # preprocess, segmenter (IA), grouper, extractor (IA), normalize,
│   │   │                     # validate, process (guarda la fila), jobs (avance en memoria)
│   │   ├── storage.py        # Almacenamiento de archivos
│   │   └── api/              # auth, trabajos, documentos
│   └── tests/
└── frontend/                 # React + Vite + Tailwind: inicio de sesión, Inicio, Subir, Revisión y Documentos
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
python -m app.usuarios crear     # tu usuario (pide nombre, email, rol y contraseña)
                                 # o define ADMIN_EMAIL y ADMIN_PASSWORD en .env y: python -m app.usuarios admin-inicial
uvicorn app.main:app --reload    # http://localhost:8000/docs
```

Define `SECRET_KEY` en `.env` (cualquier texto largo y secreto): sin ella las sesiones se cierran
cada vez que se reinicia el servidor.

En otra terminal:

```bash
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

**Interfaz** (pide iniciar sesión):
- *Inicio:* el día (hoy o el que se elija) con los documentos subidos, los procesados por la IA,
  los que requieren revisión humana y los revisados por una persona.
- *Subir:* imágenes o PDF sueltos, (hasta 50) o una carpeta completa (hasta 500, con subcarpetas; se ignora lo que no sea imagen o PDF), y el avance de cada trabajo (guardado, descartado, duplicado o error).
- *Revisión:* los pendientes, los más antiguos primero. Al abrir uno: la imagen a la izquierda y a
  la derecha el formulario con lo que leyó la IA, los campos que faltan (rojo) y los dudosos
  (ámbar), y la suma de montos en vivo. Al guardar pasa al siguiente pendiente.
- *Documentos:* totales, filtros por tipo, observaciones y "requieren revisión", búsqueda por RUT o
  folio, filtro por carpeta, y el detalle de cada documento (quién lo procesó o revisó).
- *Perfiles* (solo administradores): los perfiles del sistema; crear uno, cambiar su rol y
  activarlo o desactivarlo. Un perfil desactivado no puede iniciar sesión y sus sesiones abiertas se cierran.
- *Métricas* (7, 30 o 90 días): tokens de entrada y salida por día, costo estimado (total y por
  documento leído) y por etapa; % de documentos legibles sin intervención, pendientes y revisados,
  campos que más faltan o generan dudas; tandas, espera de Claude y tasa de errores.

## API

Todas las rutas, salvo `/health` y `/auth/login`, piden `Authorization: Bearer <token>`.

| Método | Ruta | Qué hace |
|---|---|---|
| POST | `/auth/login` | Email y contraseña → token de sesión y datos del usuario |
| GET | `/auth/yo` | El usuario de la sesión |
| POST | `/trabajos` | Sube imágenes o PDF (`files`); con `carpeta` (su nombre) la subida queda como una carpeta nueva y sus documentos asociados a ella. Responde al instante con el trabajo y procesa en segundo plano, de a un trabajo por vez |
| GET | `/trabajos` | Trabajos recientes (desde que arrancó el servidor) |
| GET | `/trabajos/{id}` | Avance: estado de cada archivo y qué pasó con cada documento (guardado, descartado, duplicado o error) |
| GET | `/documentos` | Documentos (`orden`: `recientes` o `antiguos`). Filtros: `tipo`, `observaciones`, `requiere_revision`, `carpeta` (id), `q` (RUT o folio), `limite`, `desde` |
| GET | `/carpetas` | Carpetas subidas, la más reciente primero, con sus documentos guardados y cuántos requieren revisión |
| GET | `/documentos/resumen` | Totales por observaciones y por tipo, y cuántos requieren revisión |
| GET | `/documentos/dia` | Totales de un día (`fecha`, por defecto hoy en `TIMEZONE`): subidos, procesados por la IA, pendientes y revisados |
| GET | `/documentos/{id}` | Un documento |
| PUT | `/documentos/{id}/correccion` | Una persona corrige o confirma los datos. Valida RUT y suma; un descuadre se guarda solo con `confirmar_descuadre` |
| GET | `/documentos/{id}/imagen` | El archivo original del que salió |
| GET | `/tipos-documentos` | FC, CI y GD |
| GET | `/usuarios` | Perfiles (sin el Modelo IA). **Solo administradores**, como las tres siguientes |
| GET | `/usuarios/roles` | REVISOR y ADMINISTRADOR |
| POST | `/usuarios` | Crea un perfil activo (nombre, email, rol y contraseña de al menos 8 caracteres) |
| PATCH | `/usuarios/{id}` | Cambia el rol o activa/desactiva. Un administrador no puede desactivarse ni quitarse el rol a sí mismo |
| GET | `/metricas` | Uso de IA (tokens, costo por día y por etapa) y rendimiento de la IA y del sistema de los últimos `dias` |

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
python -m app.evaluation.run --corrida claude2  # corrida aparte (base y resultados propios), para comparar
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
