/** Etiquetas y formatos de la interfaz. Los valores vienen de la API (LEGIBLE, FC…). */

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
  // Observaciones de un documento
  LEGIBLE: status('Legible', 'success'),
  NO_LEGIBLE: status('No legible', 'warning'),
  DESCUADRE: status('Descuadre', 'danger'),
  // Trabajos y archivos
  EN_COLA: status('En cola', 'neutral'),
  PENDIENTE: status('Pendiente', 'neutral'),
  EN_PROCESO: status('En proceso', 'brand'),
  TERMINADO: status('Terminado', 'success'),
  DETENIDO: status('Detenido', 'warning'),
  ERROR: status('Error', 'danger'),
  OMITIDO: status('Omitido', 'neutral'),
  // Resultado de cada documento encontrado
  GUARDADO: status('Guardado', 'success'),
  DESCARTADO: status('Descartado', 'neutral'),
  DUPLICADO: status('Duplicado', 'warning'),
}

export const DOC_TYPES = {
  FC: 'Factura electrónica',
  CI: 'Control interno',
  GD: 'Guía de despacho',
  DESCONOCIDO: 'Desconocido',
}

/** Por qué un documento requiere revisión humana. */
export const REVIEW_REASONS = {
  NO_LEGIBLE:
    'Falta un dato obligatorio o las dos lecturas de la IA no coincidieron. Si falta el neto, el IVA o el total, todos los montos se guardan en $ 0.',
  DESCUADRE: 'Los montos se leyeron, pero neto + IVA + impuestos no da el total.',
}

/** Pesos chilenos: $ 1.190.000 */
export function clp(amount) {
  if (amount == null) return '—'
  return `$ ${Number(amount).toLocaleString('es-CL')}`
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

export function fileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toLocaleString('es-CL', { maximumFractionDigits: 1 })} MB`
}

/** "2026-10-25" → "domingo, 25 de octubre de 2026" */
export function longDate(value) {
  if (!value) return '—'
  return new Date(value).toLocaleDateString('es-CL', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC',
  })
}

/** Nombre de cada columna en el formulario de corrección. */
export const FIELD_LABELS = {
  rut_proveedor: 'RUT del proveedor',
  folio: 'Folio',
  fecha: 'Fecha',
  firma: 'Firma',
  total_neto: 'Neto',
  iva: 'IVA',
  impuestos: 'Impuestos (otros + exento)',
  total: 'Total',
}
