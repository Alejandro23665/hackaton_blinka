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

    # Despliegue: frontend compilado que sirve FastAPI
    FRONTEND_DIST: Path | None = BACKEND_DIR.parent / "frontend" / "dist"

    # Sesiones (inicio de sesión con la tabla usuarios). Sin SECRET_KEY, se cierran al reiniciar
    SECRET_KEY: str | None = None
    SESSION_HOURS: int = 12
    # Zona horaria del "día" del dashboard
    TIMEZONE: str = "America/Santiago"

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
    # Con segunda lectura: si las dos lecturas ven exactamente el mismo valor, basta esta seguridad.
    # Dos lecturas independientes que coinciden pesan más que la seguridad que declara el modelo
    AGREEMENT_MIN_CONFIDENCE: float = 0.5

    # Lectura con Claude (API de Anthropic). La clave va en CLAUDE_KEY
    CLAUDE_KEY: str | None = None
    AI_MODEL: str = "claude-haiku-5-5"
    # Modelo de cada agente; vacío = AI_MODEL
    SEGMENTER_MODEL: str | None = None
    EXTRACTOR_MODEL: str | None = None
    # Esfuerzo de razonamiento del modelo (low, medium, high, xhigh, max). Más esfuerzo: más tokens
    AI_EFFORT: str = "medium"
    # Tope de tokens de cada respuesta (incluye el razonamiento interno del modelo)
    AI_MAX_TOKENS: int = 16000
    # Message Batches API: mitad de precio, respuesta asíncrona (la mayoría en menos de una hora,
    # máximo 24 h). false = una llamada por solicitud (más rápido para probar)
    AI_BATCH: bool = True
    AI_BATCH_POLL_S: float = 10
    AI_BATCH_MAX_WAIT_S: float = 24 * 3600
    # Precio de AI_MODEL en dólares por millón de tokens (Claude Haiku 5.5 con prompts de hasta 100K
    # tokens), para estimar el costo en las métricas. En tandas se cobra la mitad
    AI_PRICE_INPUT_MTOK: float = 0.10
    AI_PRICE_OUTPUT_MTOK: float = 0.50
    # Reintentos del SDK ante errores pasajeros (429, 5xx, red) y de respuestas incompletas
    AI_MAX_RETRIES: int = 2
    AI_FORMAT_RETRIES: int = 1
    # Segunda lectura independiente de cada documento: los campos en que no coincide quedan ILEGIBLE.
    # Detecta datos "adivinados" (la confianza que declara el modelo no lo hace). Duplica las lecturas.
    EXTRACTION_VERIFY: bool = True

    # Caché de respuestas de la IA en disco: repetir una llamada idéntica (misma imagen, mismas
    # instrucciones, mismo modelo) no gasta cuota. Se comparte entre bases de datos.
    AI_CACHE_ENABLED: bool = True
    AI_CACHE_DIR: Path = BACKEND_DIR / ".ai_cache"

    @field_validator("DATABASE_URL")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        """Render y Railway dan 'postgres://…' o 'postgresql://…': se usa el driver psycopg 3."""
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value


settings = Settings()
