/** Etiquetas y formatos de la interfaz. Los valores vienen de la API (LEGIBLE, FC…). */

/** Cada tono: fondo y texto de la etiqueta, borde fino y color del icono. */
const TONES = {
  success: { className: 'bg-success-50 text-success-700 ring-success-600/20', dot: 'bg-success-600', icon: 'text-success-600' },
  warning: { className: 'bg-warning-50 text-warning-700 ring-warning-600/25', dot: 'bg-warning-600', icon: 'text-warning-600' },
  danger: { className: 'bg-danger-50 text-danger-700 ring-danger-600/20', dot: 'bg-danger-600', icon: 'text-danger-600' },
  info: { className: 'bg-info-50 text-info-700 ring-info-600/20', dot: 'bg-info-600', icon: 'text-info-600' },
  slate: { className: 'bg-slate-50 text-slate-700 ring-slate-600/25', dot: 'bg-slate-600', icon: 'text-slate-600' },
  brand: { className: 'bg-brand-50 text-brand-700 ring-brand-600/20', dot: 'bg-brand-600', icon: 'text-brand-600' },
  neutral: { className: 'bg-surface text-muted ring-line-strong', dot: 'bg-subtle', icon: 'text-subtle' },
}

/** El icono acompaña al color: cada estado se distingue también sin verlo (daltonismo, impresión). */
function status(label, tone, icon) {
  return { label, tone, icon, ...TONES[tone] }
}

export const STATUS = {
  // Observaciones de un documento
  LEGIBLE: status('Legible', 'success', 'checkCircle'),
  NO_LEGIBLE: status('No legible', 'warning', 'eyeOff'),
  DESCUADRE: status('Descuadre', 'danger', 'notEqual'),
  DESCONOCIDO: status('Desconocido', 'slate', 'help'),
  // Trabajos y archivos
  EN_COLA: status('En cola', 'neutral', 'clock'),
  PENDIENTE: status('Pendiente', 'neutral', 'clock'),
  EN_PROCESO: status('En proceso', 'info', 'loader'),
  TERMINADO: status('Terminado', 'success', 'check'),
  DETENIDO: status('Detenido', 'warning', 'pause'),
  ERROR: status('Error', 'danger', 'alert'),
  OMITIDO: status('Omitido', 'neutral', 'minus'),
  // Resultado de cada documento encontrado
  GUARDADO: status('Guardado', 'success', 'check'),
  DESCARTADO: status('Descartado', 'neutral', 'minus'),
  DUPLICADO: status('Duplicado', 'warning', 'copy'),
}

export const DOC_TYPES = {
  FC: 'Factura electrónica',
  CI: 'Control interno',
  GD: 'Guía de despacho',
  DESC: 'Desconocido',
}

/** RUT de proveedor que más se repiten por tipo de documento (el primero es el más habitual). */
export const FREQUENT_RUTS = {
  CI: ['76084682-1'],
  GD: ['76084682-1', '94851000-6'],
  FC: ['91144000-8', '99501760-1', '94528000-K', '91041000-8', '88502900-0', '84472400-4', '82623500-4', '78450685-1'],
}

/** Por qué un documento requiere revisión humana. */
export const REVIEW_REASONS = {
  NO_LEGIBLE:
    'Falta un dato obligatorio o las dos lecturas de la IA no coincidieron. Si falta el neto, el IVA o el total, todos los montos se guardan en $ 0.',
  DESCUADRE: 'Los montos se leyeron, pero neto + IVA + impuestos no da el total.',
  DESCONOCIDO:
    'No se reconoció el tipo de documento. Indica si es una factura, un control interno o una guía, o acéptalo tal como está.',
}

/** El motivo que se muestra para un documento en revisión. Uno legible solo llega a la cola porque
 * su tipo se dedujo sin ver el título. */
export function reviewReason(doc) {
  if (doc.observaciones === 'LEGIBLE') return 'El tipo se dedujo sin ver el título del documento: confirma que sea el correcto.'
  return REVIEW_REASONS[doc.observaciones]
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
