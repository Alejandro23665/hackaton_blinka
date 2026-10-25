# Diseño

La lectura (fases 1 a 4) se mantiene. La base de datos se rehízo desde cero (R1): ver
[Base de datos](#base-de-datos).

## Qué hace el sistema

Recibe una o varias imágenes, o PDF de varias páginas, con documentos mezclados (proyecto Oxxo);
separa cada documento, lo **clasifica** (guía de despacho, control interno, factura electrónica o
desconocido), **extrae** sus campos, los **normaliza**, **valida** los montos y guarda una fila por
documento en `documentos_procesados`. Los desconocidos se descartan.

Principio central: **la IA lee, el código decide.** La IA transcribe lo que ve y con qué seguridad;
convertir, sumar, validar y asignar estados lo hace código convencional, probado con tests.

## Flujo

```
Archivos ─► Recepción (originales + sha256) ─► Preprocesador ─► páginas
     ─► [IA] Segmentador-clasificador (por página) ─► regiones con tipo y evidencia
     ─► Agrupador (código) ─► documentos
     ─► [IA] Extractor (por documento admitido) ─► texto leído por campo + estado + confianza
     ─► [IA] Segunda lectura independiente ─► los campos que no coinciden quedan ILEGIBLE
     ─► Normalizador (código) ─► Validador (código) ─► una fila en documentos_procesados
```

## Reglas

- **Clasificación:** solo con el título impreso como evidencia ("FACTURA ELECTRONICA",
  "CONTROL INTERNO", "GUIA DE DESPACHO" o "GUIA ELECTRONICA"). Todo lo demás (boletas, facturas exentas, notas de
  crédito, fotos…) es `DESCONOCIDO`.
- **Obligatorios:** RUT del prestador, número, fecha de emisión, monto neto, **IVA** y monto total.
  **Opcionales:** otros impuestos y monto exento. Una guía de despacho sin montos es válida: sus montos
  quedan `AUSENTE` y la validación `NO_APLICA`.
- **Cada campo:** `LEIDO`, `AUSENTE` (no aparece) o `ILEGIBLE` (aparece pero no se lee con
  seguridad). Ausente ≠ 0.
- **RUT ilegible** (o con dígito verificador incorrecto): se guarda `1-9` con `rut_is_substitute`.
- **Suma:** neto + IVA + otros impuestos + exento = total, con tolerancia `TOTAL_TOLERANCE_CLP` (0). Un
  opcional ausente no suma. Uno ilegible se registra en 0 si los demás montos ya suman el total
  (alerta `OPCIONAL_DEDUCIDO`); si no, deja la validación `INCOMPLETA` (nunca `DESCUADRE`).
- **Monto obligatorio ilegible o ausente** (neto, IVA o total): todos los montos del documento se
  guardan en 0 y queda `NO_LEGIBLE` (alerta `MONTOS_EN_CERO`). Lo leído de cada campo se conserva en
  `extracted_fields`. No aplica a la guía sin valorizar, cuyos montos siguen sin valor.
- **IVA y otros impuestos:** el extractor lee cada línea de impuesto por separado y el código las
  clasifica por su nombre: el **IVA** va a `vat_amount` (campo `VAT_AMOUNT`, obligatorio) y los demás
  (IABA 10 %, IABA 18 %, ILA VIN 20,5 %, ILA CER 20,5 %, ILA 31,5 %…) se suman en
  `other_taxes_amount` (`OTHER_TAXES_AMOUNT`, opcional). Si una línea no se lee (por ejemplo, tapada por
  una perforación), su campo queda `ILEGIBLE`: sumar solo las legibles daría un monto falso.

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
Las guías de despacho en ticket se titulan a veces solo **"GUÍA ELECTRÓNICA"** (recuadro con R.U.T. y
N°, timbre del SII abajo) y se clasifican como `GUIA_DESPACHO`.

## Firma

Cada documento admitido guarda `has_signature` (`true`/`false`) y su confianza. Cuenta como firma
cualquier trazo manuscrito de recepción (rúbrica, o nombre, RUT o fecha escritos a mano), normalmente
abajo, en el recuadro "Nombre / RUT / Fecha / Recinto / Firma"; un recuadro vacío es `false`. Con la
segunda lectura, solo es `true` si ambas ven la firma; si no coinciden queda `false` con la alerta
`FIRMA_DUDOSA`. Lo escrito a mano nunca se usa como RUT ni fecha del documento. La firma no cambia el
estado general. En los desconocidos queda `NULL` (no se analiza).

## Estados

El validador trabaja internamente con dimensiones separadas (extracción `COMPLETA`/`INCOMPLETA`,
validación `CUADRA`/`DESCUADRE`/`INCOMPLETA`/`NO_APLICA`) y deriva un estado general
`NO_LEGIBLE` → `DESCUADRE` → `PROCESADO`. Al guardar se convierte en `observaciones`:

| Estado del validador | `observaciones` | `requiere_revision` |
|---|---|---|
| `PROCESADO` | `LEGIBLE` | no |
| `NO_LEGIBLE` | `NO_LEGIBLE` | sí |
| `DESCUADRE` | `DESCUADRE` | sí |
| `DESCONOCIDO` | no se guarda | — |

Decisión: si un campo **opcional** es ilegible y los demás montos no alcanzan para comprobar la
suma, el documento es `NO_LEGIBLE`: marcarlo legible ocultaría que el total no se pudo verificar. Si
los demás montos ya suman el total, el opcional solo puede ser 0 y el documento queda `LEGIBLE`.

Las alertas detalladas del validador (campo ilegible, lectura inconsistente, firma dudosa…) no se
guardan: la base solo registra el resultado.

## Base de datos

Se define solo con los archivos SQL de `db/` (001, 002…), aplicados en orden. Cuatro tablas:

| Tabla | Responsabilidad |
|---|---|
| `roles` | Roles de la aplicación |
| `usuarios` | Nombre, email (único sin distinguir mayúsculas), hash de la contraseña (nunca en texto plano) y rol. Un rol con usuarios no se puede borrar |
| `tipos_documentos` | Solo FC (factura electrónica), CI (control interno) y GD (guía de despacho) |
| `documentos_procesados` | Una fila por documento: `rut_proveedor`, `folio` (texto: conserva ceros), `fecha`, `firma`, `impuestos` (otros impuestos + exento), `total_neto`, `iva`, `total` (pesos, enteros, nunca negativos), `observaciones`, `requiere_revision` (calculada por la base), `id_tipo_documento` e `imagen` (archivo original) |

Reglas que hace cumplir la propia base:
- `observaciones` solo admite `LEGIBLE`, `NO_LEGIBLE` y `DESCUADRE`; `requiere_revision` es
  `observaciones <> 'LEGIBLE'` y nadie la puede escribir.
- El tipo es obligatorio: un documento desconocido no se puede guardar.
- Un documento (tipo, RUT y folio) no se guarda dos veces, salvo con RUT ilegible `1-9`.

Montos: `total_neto + iva + impuestos = total`. Si falta un monto obligatorio, todos quedan en 0 y
el documento `NO_LEGIBLE`; una guía sin valorizar deja sus montos vacíos y es `LEGIBLE`.

## Tecnología

FastAPI · PostgreSQL (definida en `db/*.sql`) + SQLModel · OpenRouter (modelo configurable; hoy
`nvidia/nemotron-3.5-super-vl:free`) · pypdfium2 + Pillow · React + Vite + Tailwind · Docker en
Railway con volumen para los archivos.
