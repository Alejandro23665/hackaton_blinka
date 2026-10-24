# Diseño aprobado (fases 1 a 4)

## Qué hace el sistema

Recibe **lotes** (una o varias imágenes, o PDF de varias páginas) con documentos mezclados,
separa cada documento, lo **clasifica** (guía de despacho, control interno, factura electrónica o
desconocido), **extrae** sus campos, los **normaliza**, **valida** los montos y guarda todo con
trazabilidad.

Principio central: **la IA lee, el código decide.** La IA transcribe lo que ve y con qué seguridad;
convertir, sumar, validar y asignar estados lo hace código convencional, probado con tests.

## Flujo

```
Lote ─► Recepción (originales + sha256) ─► Preprocesador ─► páginas
     ─► [IA] Segmentador-clasificador (por página) ─► regiones con tipo y evidencia
     ─► Agrupador (código) ─► documentos
     ─► [IA] Extractor (por documento admitido) ─► texto leído por campo + estado + confianza
     ─► [IA] Segunda lectura independiente ─► los campos que no coinciden quedan ILEGIBLE
     ─► Normalizador (código) ─► Validador (código) ─► estados y alertas ─► una transacción
```

## Reglas

- **Clasificación:** solo con el título impreso como evidencia ("FACTURA ELECTRONICA",
  "CONTROL INTERNO", "GUIA DE DESPACHO"). Todo lo demás (boletas, facturas exentas, notas de
  crédito, fotos…) es `DESCONOCIDO`.
- **Obligatorios:** RUT del prestador, número, fecha de emisión, monto neto y monto total.
  **Opcionales:** impuestos y monto exento. Una guía de despacho sin montos es válida: sus montos
  quedan `AUSENTE` y la validación `NO_APLICA`.
- **Cada campo:** `LEIDO`, `AUSENTE` (no aparece) o `ILEGIBLE` (aparece pero no se lee con
  seguridad). Ausente ≠ 0.
- **RUT ilegible** (o con dígito verificador incorrecto): se guarda `1-9` con `rut_is_substitute`.
- **Suma:** neto + impuestos + exento = total, con tolerancia `TOTAL_TOLERANCE_CLP` (0). Un
  opcional ausente no suma; uno ilegible deja la validación `INCOMPLETA` (nunca `DESCUADRE`).

## Lecturas no fiables: doble lectura

La confianza que declara el modelo no es fiable: con una fecha diminuta y borrosa respondió
`10.10.2025` con 90 % de seguridad. Pero un dato que el modelo *adivina* cambia entre lecturas
(`10.10.2025`, `18-10-2026`, `18-10-2016`…), mientras que uno nítido se lee siempre igual. Por eso
cada documento se lee **dos veces** (la segunda con temperatura `VERIFY_TEMPERATURE`) y el código
compara los valores normalizados: si no coinciden, el campo queda `ILEGIBLE` con la alerta
`LECTURA_INCONSISTENTE`. La segunda lectura nunca "rescata" un campo ilegible. Se desactiva con
`EXTRACTION_VERIFY=false` (a cambio, una llamada menos por documento).

**Hoja adjunta tipo ticket:** la tira térmica **sin recuadro de RUT, tipo y N°** ("Informe
Ingreso", lista de productos y "Neto / Iva / Imp Adic. / Total") que a veces viene corcheteada sobre
una factura se ignora: no es un documento y nunca se toman de ella el número ni los montos.

**Control interno en ticket:** los controles internos suelen ser tickets térmicos (por ejemplo de
OXXO) **con** un recuadro "R.U.T. / CONTROL INTERNO / N°" y NETO, EXENTO, IVA y TOTAL. Se clasifican
como `CONTROL_INTERNO` aunque parezcan boletas. Su número puede venir con punto de miles (`2.397`).

## Estados (dimensiones separadas)

| Dimensión | Valores |
|---|---|
| Técnico | `EN_PROCESO` · `COMPLETADO` · `FALLIDO` |
| Tipo | `GUIA_DESPACHO` · `CONTROL_INTERNO` · `FACTURA_ELECTRONICA` · `DESCONOCIDO` |
| Extracción | `COMPLETA` · `INCOMPLETA` · `NO_APLICA` |
| Validación | `CUADRA` · `DESCUADRE` · `INCOMPLETA` · `NO_APLICA` |
| **General** (derivado) | `DESCONOCIDO` → `NO_LEGIBLE` → `DESCUADRE` → `PROCESADO` |

Los problemas secundarios quedan como alertas (`run_issues`): ninguno se pierde por el estado
principal.

Decisión: si un campo **opcional** es ilegible y por eso no se puede comprobar la suma
(validación `INCOMPLETA`), el estado general es `NO_LEGIBLE`, no `PROCESADO`: marcarlo procesado
ocultaría que el total no se pudo verificar.

Alertas: `CAMPO_ILEGIBLE`, `CAMPO_OBLIGATORIO_AUSENTE`, `RUT_SUSTITUTO`, `DESCUADRE`,
`VALIDACION_INCOMPLETA`, `IVA_NO_CORRESPONDE_19` (solo facturas electrónicas, ±1 peso),
`POSIBLE_DUPLICADO` (mismo RUT real, tipo y número), `MONTO_CON_DECIMALES`, `LECTURA_INCONSISTENTE`,
`CLASIFICACION_SIN_EVIDENCIA`, `CLASIFICACION_DUDOSA`, `AGRUPACION_DUDOSA`, `BAJA_CALIDAD_IMAGEN`,
`REGION_INVALIDA`.

## Base de datos

| Tabla | Responsabilidad |
|---|---|
| `submissions` | El lote y su fecha de recepción |
| `stored_files` | Original guardado una vez (sha256 único); los bytes en el almacenamiento |
| `submission_files` | Qué archivos trae cada lote |
| `pages` | Cada página convertida en imagen |
| `page_classifications` | Respuesta del segmentador por página (historial + actual) |
| `documents` | El documento lógico |
| `document_regions` | Un documento dentro de una página (zona o página completa) |
| `processing_runs` | Cada procesamiento: datos normalizados, estados, diferencia; uno actual por documento |
| `extracted_fields` | Por campo: estado, texto original, confianza, región |
| `run_issues` | Alertas |
| `run_steps` | Bitácora: modelo, duración, intentos, respuesta original de la IA |

Las reglas críticas están además como restricciones `CHECK` en la base (por ejemplo, un
`DESCONOCIDO` no puede tener montos y no hay `DESCUADRE` sin diferencia).

Reprocesar crea un procesamiento nuevo sobre las mismas imágenes; si falla, el anterior sigue
siendo el actual.

## Tecnología

FastAPI · PostgreSQL + SQLModel + Alembic · OpenRouter (modelo configurable; hoy
`nvidia/nemotron-3.5-super-vl:free`) · pypdfium2 + Pillow · React + Vite + Tailwind · Docker en
Railway con volumen para los archivos.
