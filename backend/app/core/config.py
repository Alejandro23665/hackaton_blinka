from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # Busca .env en backend/ y en la raíz del proyecto
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg://blinka:blinka@localhost:5432/blinka"
    # Orígenes del frontend que pueden llamar a la API (en producción el frontend es el mismo origen)
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # Despliegue: frontend compilado que sirve FastAPI y contraseña de acceso opcional
    FRONTEND_DIST: Path | None = BACKEND_DIR.parent / "frontend" / "dist"
    ACCESS_USER: str = "blinka"
    ACCESS_PASSWORD: str | None = None

    # Tamaño máximo de una factura subida (se guarda en Postgres)
    MAX_UPLOAD_MB: int = 10

    # Extracción con OpenRouter (API compatible con OpenAI)
    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_MODEL: str = "nvidia/nemotron-3.5-super-vl:free"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_TIMEOUT_S: float = 90
    # Reintentos ante errores pasajeros (502, 503, 429…), con espera de 1 s, 2 s, 4 s…
    OPENROUTER_MAX_RETRIES: int = 2
    # Modelos de respaldo separados por coma; OpenRouter los usa si el principal falla
    OPENROUTER_FALLBACK_MODELS: str = ""
    # Confianza mínima de la extracción para que el agente no escale la factura
    EXTRACTION_MIN_CONFIDENCE: float = 0.8

    @field_validator("DATABASE_URL")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        """Render y Railway dan 'postgres://…' o 'postgresql://…': se usa el driver psycopg 3."""
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value


settings = Settings()
