export const STATUS = {
  pending: { label: 'Pendiente', className: 'bg-surface text-muted', dot: 'bg-subtle' },
  approved: { label: 'Aprobada', className: 'bg-success-50 text-success-700', dot: 'bg-success-600' },
  escalated: { label: 'Escalada', className: 'bg-warning-50 text-warning-700', dot: 'bg-warning-600' },
  blocked: { label: 'Bloqueada', className: 'bg-danger-50 text-danger-700', dot: 'bg-danger-600' },
  paid: { label: 'Pagada', className: 'bg-brand-100 text-brand-800', dot: 'bg-brand-600' },
}

/** Colores de serie para gráficos: morado para lo principal, lavanda y neutros para lo secundario. */
export const OUTCOME_SERIES = [
  { key: 'approved', label: 'Aprobadas', color: 'var(--color-brand-600)' },
  { key: 'escalated', label: 'Escaladas', color: 'var(--color-brand-300)' },
  { key: 'blocked', label: 'Bloqueadas', color: 'var(--color-line-strong)' },
]

export const RULE_LABELS = {
  vendor_allowed: 'Proveedor autorizado',
  active_policy: 'Política activa',
  currency_allowed: 'Moneda permitida',
  max_amount_per_invoice: 'Máximo por factura',
  period_budget: 'Presupuesto del periodo',
  require_human_above: 'Umbral de revisión humana',
  document_extraction: 'Lectura del documento',
}

export function money(amount, currency) {
  const value = Number(amount).toLocaleString('es', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
    useGrouping: 'always', // 'es' no agrupa números de 4 cifras por defecto
  })
  return currency ? `${value} ${currency}` : value
}

/** Número abreviado para ejes: 1.200 → 1,2 k */
export function compact(value) {
  return Number(value).toLocaleString('es', { notation: 'compact', maximumFractionDigits: 1 })
}

/** Fecha sin hora. Se formatea en UTC para que "2026-10-01" no se muestre como 30 sept. */
export function shortDate(value) {
  return new Date(value).toLocaleDateString('es', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' })
}

export function dateTime(value) {
  return new Date(value).toLocaleString('es', { dateStyle: 'short', timeStyle: 'short' })
}

export const PERIOD_LABELS = { monthly: 'Mensual', weekly: 'Semanal' }

export function fileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toLocaleString('es', { maximumFractionDigits: 1 })} MB`
}
