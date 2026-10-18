# Blinka

Agente que revisa facturas y decide si pagarlas, bloquearlas o escalarlas según políticas configurables.

## Estructura

```
hackaton_blinka/
├── docker-compose.yml        # PostgreSQL 16
├── .env.example
├── docs/                     # Diseño: datos, reglas, API y subida de facturas
├── backend/
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/         # Migraciones
│   └── app/
│       ├── main.py           # FastAPI
│       ├── core/config.py    # Settings (DATABASE_URL)
│       ├── db/session.py     # Engine y sesión
│       ├── models/           # Tablas SQLModel
│       ├── schemas/          # DTOs de la API
│       ├── api/              # Routers
│       ├── services/         # Reglas, agente, extracción (OpenRouter) y almacenamiento
│   └── storage/              # Facturas subidas (local, ignorado por git)
│       └── seed.py           # Datos de ejemplo para la demo
└── frontend/                 # React + Vite + Tailwind
    └── src/
        ├── api.js            # Cliente de la API
        ├── components/       # UI, detalle de factura, reglas, revisión
        └── views/            # Panel, Facturas, Proveedores, Políticas
```

## Puesta en marcha

```bash
cp .env.example .env
docker compose up -d db

cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
alembic upgrade head
python -m app.seed               # opcional: datos de ejemplo
uvicorn app.main:app --reload    # http://localhost:8000/docs
```

En otra terminal:

```bash
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

Para que el agente lea facturas subidas, añade tu clave de OpenRouter en `.env`
(`OPENROUTER_API_KEY=...`) y reinicia el backend. Detalles en
[docs/03-document-upload.md](docs/03-document-upload.md).

El frontend usa `VITE_API_URL` (por defecto `http://localhost:8000`); ver `frontend/.env.example`.

## Evaluación (set de facturas simuladas)

18 facturas ficticias de **Andes Digital LLC** con los casos trampa del reto (duplicado,
beneficiario nuevo, no cuadra con lo acordado, supera el límite, presupuesto insuficiente…).
Detalles en [dataset/README.md](dataset/README.md).

```bash
cd backend
python -m app.evaluation.run                 # motor de reglas aislado (sin modelo)
python -m app.evaluation.run --mode agente   # flujo completo con OpenRouter
```

Usa una base aparte (`<tu base>_eval`) y deja el informe en `dataset/results/`.

> **Limitación conocida del MVP:** la lectura usa un modelo gratuito de OpenRouter, que puede
> equivocarse o fallar por saturación. El diseño lo tiene en cuenta: el modelo solo extrae datos y
> las reglas deciden; ante cualquier duda la factura se escala a una persona. Un error de lectura
> cuesta autonomía, no pagos indebidos. Más en
> [dataset/README.md](dataset/README.md#sobre-el-modelo-de-lectura-limitaciones-conocidas).

## Limpiar facturas subidas

Borra los archivos de `backend/storage` y lo que se creó a partir de ellos (documentos,
facturas, decisiones y proveedores que creó el agente). No toca políticas, proveedores
creados a mano ni facturas ingresadas manualmente.

```bash
cd backend
python -m app.cleanup --dry-run   # ver qué se borraría
python -m app.cleanup             # pide confirmación
python -m app.cleanup --yes       # sin preguntar
```

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest                                   # motor de reglas (sin BD)
```

Los tests de API necesitan una base Postgres **vacía y dedicada** (se borran sus tablas):

```bash
docker compose exec db createdb -U blinka blinka_test
set TEST_DATABASE_URL=postgresql+psycopg://blinka:blinka@localhost:5432/blinka_test
pytest
```

Ver [docs/02-rules-and-api.md](docs/02-rules-and-api.md) para las reglas y los endpoints.

## Migraciones

```bash
alembic revision --autogenerate -m "descripcion"   # tras cambiar un modelo
alembic upgrade head
alembic downgrade -1
```
