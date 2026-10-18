/**
 * Conversión de monedas en el cliente, con la misma fórmula que el backend (app/services/fx.py):
 * USD es la moneda pivote y cada tipo de cambio dice cuántos USD vale 1 unidad.
 */
export const PIVOT = 'USD'

/** [{ currency, usd_per_unit }] -> { USD: 1, EUR: 1.08, … } */
export function ratesMap(list) {
  const map = { [PIVOT]: 1 }
  ;(list ?? []).forEach((r) => {
    map[r.currency.toUpperCase()] = Number(r.usd_per_unit)
  })
  return map
}

/** Monto convertido (redondeado a 2 decimales) o null si falta el tipo de cambio. */
export function convert(amount, from, to, rates) {
  const source = from.toUpperCase()
  const target = to.toUpperCase()
  if (source === target) return Number(amount)
  if (!(source in rates) || !(target in rates)) return null
  return Math.round(((Number(amount) * rates[source]) / rates[target]) * 100) / 100
}
