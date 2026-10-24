/** Etiquetas y formatos de la interfaz. Los valores vienen de la API en español (PROCESADO, LEIDO…). */

const TONES = {
  success: { className: 'bg-success-50 text-success-700', dot: 'bg-success-600' },
  warning: { className: 'bg-warning-50 text-warning-700', dot: 'bg-warning-600' },
  danger: { className: 'bg-danger-50 text-danger-700', dot: 'bg-danger-600' },
  brand: { className: 'bg-brand-100 text-brand-800', dot: 'bg-brand-600' },
  neutral: { className: 'bg-surface text-muted', dot: 'bg-subtle' },
}

function status(label, tone) {
  return { label, ...TONES[tone] }
}

export const STATUS = {
  // Estado general de un documento
  PROCESADO: status('Procesado', 'success'),
  NO_LEGIBLE: status('No legible', 'warning'),
  DESCUADRE: status('Descuadre', 'danger'),
  DESCONOCIDO: status('Desconocido', 'neutral'),
  // Estado técnico
  EN_PROCESO: status('En proceso', 'brand'),
  FALLIDO: status('Falló', 'danger'),
  COMPLETADO: status('Completado', 'success'),
  // Lote
  RECIBIDO: status('Recibido', 'neutral'),
  COMPLETADO_CON_ERRORES: status('Con errores', 'warning'),
  // Extracción y validación
  COMPLETA: status('Completa', 'success'),
  INCOMPLETA: status('Incompleta', 'warning'),
  CUADRA: status('Cuadra', 'success'),
  NO_APLICA: status('No aplica', 'neutral'),
  // Campos
  LEIDO: status('Leído', 'success'),
  AUSENTE: status('Ausente', 'neutral'),
  ILEGIBLE: status('Ilegible', 'warning'),
  // Pasos y páginas
  OK: status('OK', 'success'),
  ERROR: status('Error', 'danger'),
  OMITIDO: status('Omitido', 'neutral'),
  PENDIENTE: status('Pendiente', 'neutral'),
  LISTO: status('Listo', 'success'),
}

/** Estado que se muestra: el general si el documento terminó; si no, el técnico (en proceso / falló). */
export function documentStatus(doc) {
  return doc.overall_status ?? doc.technical_status
}

export const DOC_TYPES = {
  FACTURA_ELECTRONICA: 'Factura electrónica',
  GUIA_DESPACHO: 'Guía de despacho',
  CONTROL_INTERNO: 'Control interno',
  DESCONOCIDO: 'Desconocido',
}

export const FIELD_LABELS = {
  PROVIDER_RUT: 'RUT del prestador',
  DOCUMENT_NUMBER: 'Número',
  ISSUE_DATE: 'Fecha de emisión',
  NET_AMOUNT: 'Monto neto',
  VAT_AMOUNT: 'IVA',
  OTHER_TAXES_AMOUNT: 'Otros impuestos',
  EXEMPT_AMOUNT: 'Monto exento',
  TOTAL_AMOUNT: 'Monto total',
}

export const STEP_LABELS = {
  EXTRACCION: 'Extracción (IA)',
  VERIFICACION: 'Verificación (2.ª lectura IA)',
  NORMALIZACION: 'Normalización',
  VALIDACION: 'Validación',
}

export const SEVERITY_TONE = { ERROR: 'danger', ADVERTENCIA: 'warning', INFO: 'neutral' }

/** Pesos chilenos: $ 1.190.000 (con decimales solo si los hay). */
export function clp(amount) {
  if (amount == null) return '—'
  const value = Number(amount)
  const decimals = Number.isInteger(value) ? 0 : 2
  return `$ ${value.toLocaleString('es-CL', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`
}

/** 76123456-0 → 76.123.456-0 */
export function rut(value) {
  if (!value) return '—'
  const [body, check] = value.split('-')
  return `${Number(body).toLocaleString('es-CL')}-${check}`
}

/** Fecha sin hora. Se formatea en UTC para que "2026-10-01" no se muestre como 30 sept. */
export function shortDate(value) {
  if (!value) return '—'
  return new Date(value).toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' })
}

export function dateTime(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString('es-CL', { dateStyle: 'short', timeStyle: 'short' })
}

export function duration(ms) {
  if (ms == null) return '—'
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toLocaleString('es-CL', { maximumFractionDigits: 1 })} s`
}

export function percent(value) {
  if (value == null) return '—'
  return `${Math.round(Number(value) * 100)} %`
}

export function fileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toLocaleString('es-CL', { maximumFractionDigits: 1 })} MB`
}
