# Blinka

Agente que revisa facturas y decide si pagarlas, bloquearlas o escalarlas según políticas configurables.

## Estructura

```
hackaton_blinka/
├── docker-compose.yml        # PostgreSQL 16
├── .env.example
├── docs/                     # Diseño (01-database.md)
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
│       └── services/         # Motor de reglas / agente
└── frontend/                 # React + Vite + Tailwind (próximo paso)
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
uvicorn app.main:app --reload    # http://localhost:8000/docs
```

## Migraciones

```bash
alembic revision --autogenerate -m "descripcion"   # tras cambiar un modelo
alembic upgrade head
alembic downgrade -1
```
