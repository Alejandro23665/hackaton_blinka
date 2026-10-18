# Paso 5 — Subida de facturas y extracción con el agente

## Flujo

```
Archivo (PDF/PNG/JPG/WEBP)
  → POST /documents
  → se guarda en backend/storage/invoices/AAAA/MM/<hash>.<ext>      (tabla documents)
  → el agente lo lee con un modelo multimodal vía OpenRouter          (JSON estructurado)
  → se busca el proveedor (ID fiscal → nombre) o se crea "pendiente"
  → se crea la factura y el motor de reglas decide                   (tabla decisions)
```

Todo ocurre en una sola petición. La interfaz muestra "El agente está leyendo la factura…" y,
al terminar, abre el detalle con lo extraído, la confianza, los avisos y el enlace al original.

## Configuración (`.env`)

| Variable | Por defecto | Uso |
|---|---|---|
| `OPENROUTER_API_KEY` | — | **Obligatoria** para leer facturas |
| `OPENROUTER_MODEL` | `anthropic/claude-sonnet-5.5` | Cualquier modelo de OpenRouter con entrada de imagen y archivo |
| `EXTRACTION_MIN_CONFIDENCE` | `0.8` | Por debajo, la factura se escala |
| `STORAGE_DIR` | `backend/storage` | Carpeta local de los archivos (no va a git) |
| `MAX_UPLOAD_MB` | `10` | Tamaño máximo |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Orígenes del frontend |

Después de cambiar `.env`, reinicia el backend.

## Qué hace el agente con cada caso

| Situación | Resultado |
|---|---|
| Lectura clara, proveedor conocido y autorizado | Reglas normales (aprobada / escalada / bloqueada) |
| Proveedor desconocido | Se crea **pendiente de aprobar** (`needs_review`) y la factura se **escala** |
| Confianza < mínimo o con avisos (moneda deducida, sin vencimiento…) | **Escalada** (regla `document_extraction`) |
| Sin fecha de vencimiento | Se usa la de emisión (o hoy) y se añade un aviso → escalada |
| Falta proveedor, número, total o moneda | Documento `failed`; no se crea factura |
| Misma factura (proveedor + número) ya registrada | Se registra y el agente la **bloquea** (regla `duplicate_invoice`), indicando cuál es la original |
| Mismo archivo ya procesado | `409` sin volver a llamar al modelo |
| Mismo archivo que antes falló | Se **reintenta** (útil tras configurar la API key) |
| Formato no soportado / vacío / demasiado grande | `415` / `422` / `413` |

Al autorizar o bloquear un proveedor pendiente en **Proveedores**, deja de estar pendiente;
luego **Reevaluar** la factura aplica la decisión del agente con el proveedor ya resuelto.

## Endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| POST | `/documents` | Sube un archivo (`multipart/form-data`, campo `file`) |
| GET | `/documents?limit=` | Últimas subidas |
| GET | `/documents/{id}` | Detalle con la extracción |
| GET | `/documents/{id}/file` | Archivo original (se abre en el navegador) |

`GET /invoices/{id}` incluye ahora `document` cuando la factura viene de un archivo.

## Modelo de datos (migración `0002`)

- **documents**: `original_name`, `stored_path`, `content_type`, `size_bytes`, `sha256` (único),
  `status` (`processing`/`processed`/`failed`), `extraction` (JSONB), `error`, `invoice_id`.
- **vendors**: + `tax_id` (único, opcional) y `needs_review`.
- La extracción también se copia en `invoices.raw_data` (`source: "document"`).
