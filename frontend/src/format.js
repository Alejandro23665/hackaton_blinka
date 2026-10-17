export const STATUS = {
  pending: { label: 'Pendiente', className: 'bg-slate-100 text-slate-700 ring-slate-300' },
  approved: { label: 'Aprobada', className: 'bg-emerald-50 text-emerald-700 ring-emerald-300' },
  escalated: { label: 'Escalada', className: 'bg-amber-50 text-amber-800 ring-amber-300' },
  blocked: { label: 'Bloqueada', className: 'bg-rose-50 text-rose-700 ring-rose-300' },
  paid: { label: 'Pagada', className: 'bg-sky-50 text-sky-700 ring-sky-300' },
}

export const RULE_LABELS = {
  vendor_allowed: 'Proveedor autorizado',
  active_policy: 'Política activa',
  currency_allowed: 'Moneda permitida',
  max_amount_per_invoice: 'Máximo por factura',
  period_budget: 'Presupuesto del periodo',
  require_human_above: 'Umbral de revisión humana',
}

export function money(amount, currency) {
  const value = Number(amount).toLocaleString('es', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
    useGrouping: 'always', // 'es' no agrupa números de 4 cifras por defecto
  })
  return currency ? `${value} ${currency}` : value
}

/** Fecha sin hora. Se formatea en UTC para que "2026-10-01" no se muestre como 30 sept. */
export function shortDate(value) {
  return new Date(value).toLocaleDateString('es', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' })
}

export function dateTime(value) {
  return new Date(value).toLocaleString('es', { dateStyle: 'short', timeStyle: 'short' })
}

export const PERIOD_LABELS = { monthly: 'Mensual', weekly: 'Semanal' }
