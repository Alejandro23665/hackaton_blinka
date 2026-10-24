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

    # Archivos originales e imágenes de páginas (en producción, un volumen persistente)
    STORAGE_DIR: Path = BACKEND_DIR / "storage"

    # Límites de un lote
    MAX_UPLOAD_MB: int = 25
    MAX_FILES_PER_SUBMISSION: int = 50
    MAX_PAGES_PER_FILE: int = 300

    # Imagen de cada página: resolución al convertir PDF y lado máximo (lo que ve la IA)
    PAGE_RENDER_DPI: int = 200
    PAGE_MAX_SIDE_PX: int = 2000

    # Reglas de validación
    TOTAL_TOLERANCE_CLP: int = 0
    CLASSIFICATION_MIN_CONFIDENCE: float = 0.7
    FIELD_MIN_CONFIDENCE: float = 0.8

    # Lectura con OpenRouter (API compatible con OpenAI)
    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_MODEL: str = "nvidia/nemotron-3.5-super-vl:free"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_TIMEOUT_S: float = 90
    # Reintentos ante errores pasajeros (502, 503, 429…), con espera de 1 s, 2 s, 4 s…
    OPENROUTER_MAX_RETRIES: int = 2
    # Modelos de respaldo separados por coma; OpenRouter los usa si el principal falla
    OPENROUTER_FALLBACK_MODELS: str = ""

    @field_validator("DATABASE_URL")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        """Render y Railway dan 'postgres://…' o 'postgresql://…': se usa el driver psycopg 3."""
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value


settings = Settings()
