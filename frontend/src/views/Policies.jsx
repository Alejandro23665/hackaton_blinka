import { useState } from 'react'
import { api } from '../api'
import Icon from '../components/icons'
import { Button, Card, ConfirmDelete, Empty, ErrorBox, Field, IconButton, Loading, Tag } from '../components/ui'
import { dateTime, money, PERIOD_LABELS } from '../format'
import { inputClass } from '../components/styles'
import { PIVOT } from '../fx'
import { useLoad } from '../hooks'

const EMPTY_FORM = {
  name: '',
  max_amount_per_invoice: '',
  require_human_above: '',
  period_budget: '',
  period: 'monthly',
  allowed_currencies: 'USD',
  base_currency: 'USD',
}

/** Valores de una política existente para prellenar el formulario. */
function policyToForm(p) {
  return {
    name: p.name,
    max_amount_per_invoice: String(p.max_amount_per_invoice),
    require_human_above: String(p.require_human_above),
    period_budget: String(p.period_budget),
    period: p.period,
    allowed_currencies: p.allowed_currencies.join(', '),
    base_currency: p.base_currency,
  }
}

/**
 * Crea una política. Con `source`, parte de sus valores: las políticas no se modifican en sitio
 * (las decisiones pasadas apuntan a ellas), así que "editar" guarda una nueva versión activa.
 */
function PolicyForm({ onCreated, baseOptions, source, onCancel }) {
  const [form, setForm] = useState(source ? policyToForm(source) : EMPTY_FORM)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (key) => (e) => {
    setForm({ ...form, [key]: e.target.value })
    setError(null)
  }

  async function submit(e) {
    e.preventDefault()
    const currencies = form.allowed_currencies.split(',').map((c) => c.trim()).filter(Boolean)
    if (!form.name.trim() || !form.max_amount_per_invoice || !form.require_human_above || !form.period_budget || !currencies.length) {
      setError('Completa todos los campos')
      return
    }
    setBusy(true)
    try {
      await api.policies.create({
        name: form.name.trim(),
        max_amount_per_invoice: Number(form.max_amount_per_invoice),
        require_human_above: Number(form.require_human_above),
        period_budget: Number(form.period_budget),
        period: form.period,
        allowed_currencies: currencies,
        base_currency: form.base_currency,
        is_active: true,
      })
      setForm(EMPTY_FORM)
      onCreated()
      onCancel?.()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const number = `${inputClass} tabular`
  const options = [...new Set([...baseOptions, form.base_currency])]

  return (
    <Card
      title={source ? `Editar «${source.name}»` : 'Nueva política'}
      subtitle={
        source
          ? 'Se guarda como una nueva versión activa. La actual pasa al historial y sus decisiones siguen explicándose con los límites de entonces.'
          : 'Al crearla queda activa; la anterior pasa al historial'
      }
      className={source ? 'ring-2 ring-brand-200' : ''}
    >
      <form className="space-y-4" onSubmit={submit} noValidate>
        <Field label="Nombre">
          <input className={inputClass} placeholder="Política Q4" value={form.name} onChange={set('name')} />
        </Field>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Moneda base" hint="Límites y presupuesto se expresan en ella">
            <select className={inputClass} value={form.base_currency} onChange={set('base_currency')}>
              {options.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </Field>
          <Field label="Máximo por factura" hint="Por encima → se bloquea">
            <input className={number} type="number" inputMode="decimal" min="0.01" step="0.01" value={form.max_amount_per_invoice} onChange={set('max_amount_per_invoice')} />
          </Field>
          <Field label="Revisión humana desde" hint="Por encima → se escala">
            <input className={number} type="number" inputMode="decimal" min="0.01" step="0.01" value={form.require_human_above} onChange={set('require_human_above')} />
          </Field>
          <Field label="Presupuesto del periodo">
            <input className={number} type="number" inputMode="decimal" min="0.01" step="0.01" value={form.period_budget} onChange={set('period_budget')} />
          </Field>
          <Field label="Periodo">
            <select className={inputClass} value={form.period} onChange={set('period')}>
              <option value="monthly">Mensual</option>
              <option value="weekly">Semanal</option>
            </select>
          </Field>
        </div>
        <p className="-mt-1 text-xs text-muted">
          Los montos de arriba están en <strong className="text-ink">{form.base_currency}</strong>; las facturas en otras
          monedas se convierten con los tipos de cambio antes de compararlas.
        </p>
        <Field label="Monedas permitidas" hint="Separadas por coma, ej. USD, EUR">
          <input className={`${inputClass} uppercase`} value={form.allowed_currencies} onChange={set('allowed_currencies')} />
        </Field>
        <ErrorBox message={error} />
        <div className="flex gap-2">
          {source && (
            <Button type="button" variant="secondary" onClick={onCancel} disabled={busy}>
              Cancelar
            </Button>
          )}
          <Button type="submit" icon="shield" disabled={busy} className="flex-1">
            {busy ? 'Guardando…' : source ? 'Guardar nueva versión' : 'Crear y activar'}
          </Button>
        </div>
      </form>
    </Card>
  )
}

function Limits({ policy }) {
  const base = policy.base_currency
  const items = [
    ['Máx. por factura', money(policy.max_amount_per_invoice, base)],
    ['Humano desde', money(policy.require_human_above, base)],
    [`Presupuesto ${PERIOD_LABELS[policy.period].toLowerCase()}`, money(policy.period_budget, base)],
    ['Monedas permitidas', policy.allowed_currencies.join(', ')],
  ]
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
      {items.map(([label, value]) => (
        <div key={label} className="min-w-0">
          <dt className="truncate text-xs text-muted">{label}</dt>
          <dd className="mt-0.5 text-sm font-semibold text-ink tabular">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

/** Tipos de cambio que usa el agente para llevar cada factura a la moneda base. */
function ExchangeRates({ rates, policy, onChange }) {
  const [currency, setCurrency] = useState('')
  const [value, setValue] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [editing, setEditing] = useState(null) // { currency, value }

  const configured = new Set([PIVOT, ...rates.map((r) => r.currency)])
  const needed = policy ? [...new Set([...policy.allowed_currencies, policy.base_currency])] : []
  const missing = needed.filter((c) => !configured.has(c))

  async function save(e) {
    e.preventDefault()
    const code = currency.trim().toUpperCase()
    if (!/^[A-Z]{3}$/.test(code) || !(Number(value) > 0)) {
      setError('Indica un código de 3 letras y un valor mayor que 0')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await api.exchangeRates.save(code, Number(value))
      setCurrency('')
      setValue('')
      onChange()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function saveEdit(e) {
    e.preventDefault()
    if (!(Number(editing.value) > 0)) {
      setError('El valor debe ser mayor que 0')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await api.exchangeRates.save(editing.currency, Number(editing.value))
      setEditing(null)
      onChange()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function remove(code) {
    setError(null)
    try {
      await api.exchangeRates.remove(code)
      onChange()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <Card
      title="Tipos de cambio"
      subtitle="Cuántos USD vale 1 unidad de cada moneda. El agente convierte cada factura a la moneda base antes de aplicar límites y presupuesto."
    >
      {missing.length > 0 && (
        <p className="mb-4 flex items-start gap-2 rounded-control bg-warning-50 px-3 py-2.5 text-[13px] text-warning-700">
          <Icon name="alert" size={16} className="mt-px" />
          Falta el tipo de cambio de {missing.join(', ')}: las facturas en esa moneda se escalarán a revisión humana.
        </p>
      )}

      <ul className="mb-4 divide-y divide-line rounded-control border border-line">
        <li className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm">
          <span className="font-semibold text-ink">USD</span>
          <span className="text-xs text-subtle">Moneda de referencia · 1 USD = 1 USD</span>
        </li>
        {rates.map((r) =>
          editing?.currency === r.currency ? (
            <li key={r.currency} className="bg-brand-50/60 px-4 py-2.5">
              <form onSubmit={saveEdit} noValidate className="flex flex-wrap items-center gap-2 text-sm">
                <label htmlFor={`rate-${r.currency}`} className="font-semibold text-ink">
                  1 {r.currency} =
                </label>
                <input
                  id={`rate-${r.currency}`}
                  autoFocus
                  className={`${inputClass} !h-8 w-32 tabular`}
                  type="number"
                  inputMode="decimal"
                  min="0"
                  step="any"
                  value={editing.value}
                  onChange={(e) => {
                    setEditing({ ...editing, value: e.target.value })
                    setError(null)
                  }}
                  onKeyDown={(e) => e.key === 'Escape' && setEditing(null)}
                />
                <span className="text-muted">USD</span>
                <div className="ml-auto flex gap-1.5">
                  <Button type="button" variant="ghost" size="sm" onClick={() => setEditing(null)} disabled={busy}>
                    Cancelar
                  </Button>
                  <Button type="submit" size="sm" disabled={busy}>
                    {busy ? 'Guardando…' : 'Guardar'}
                  </Button>
                </div>
              </form>
            </li>
          ) : (
            <li key={r.currency} className="relative flex items-center gap-2 px-4 py-2.5 text-sm">
              <span className="font-semibold text-ink">{r.currency}</span>
              <span className="ml-auto text-ink tabular">
                1 {r.currency} = {Number(r.usd_per_unit).toLocaleString('es', { maximumFractionDigits: 8 })} USD
              </span>
              <span className="hidden text-xs text-subtle sm:inline">{dateTime(r.updated_at)}</span>
              <IconButton
                icon="pencil"
                label={`Editar el tipo de cambio de ${r.currency}`}
                className="!h-8 !w-8 border-transparent"
                onClick={() => {
                  setEditing({ currency: r.currency, value: String(r.usd_per_unit) })
                  setError(null)
                }}
              />
              <ConfirmDelete label={`Eliminar el tipo de cambio de ${r.currency}`} onConfirm={() => remove(r.currency)} />
            </li>
          ),
        )}
      </ul>

      <form onSubmit={save} noValidate className="grid grid-cols-[96px_1fr_auto] items-end gap-2">
        <Field label="Moneda">
          <input
            className={`${inputClass} uppercase`}
            maxLength={3}
            placeholder="EUR"
            value={currency}
            onChange={(e) => {
              setCurrency(e.target.value)
              setError(null)
            }}
          />
        </Field>
        <Field label="1 unidad = … USD">
          <input
            className={`${inputClass} tabular`}
            type="number"
            inputMode="decimal"
            min="0"
            step="any"
            placeholder="1.08"
            value={value}
            onChange={(e) => {
              setValue(e.target.value)
              setError(null)
            }}
          />
        </Field>
        <Button type="submit" variant="secondary" disabled={busy}>
          Guardar
        </Button>
      </form>
      <p className="mt-2 text-xs text-subtle">Para cambiar un valor existente usa el lápiz de su fila.</p>
      <div className="mt-3">
        <ErrorBox message={error} />
      </div>
    </Card>
  )
}

export default function Policies({ version, onChange }) {
  const policies = useLoad(() => api.policies.list(), version)
  const rates = useLoad(() => api.exchangeRates.list(), version)
  const [error, setError] = useState(null)
  const [busyId, setBusyId] = useState(null)
  const [editing, setEditing] = useState(null) // política que se usa como base de la nueva versión

  function startEdit(policy) {
    setEditing(policy)
    // En móvil el formulario queda arriba: llevar al usuario hasta él
    document.getElementById('policy-form')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  async function activate(id) {
    setBusyId(id)
    setError(null)
    try {
      await api.policies.activate(id)
      onChange()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  async function remove(id) {
    setError(null)
    try {
      await api.policies.remove(id)
      onChange()
    } catch (err) {
      setError(err.message)
    }
  }

  const list = policies.data ?? []
  const active = list.find((p) => p.is_active)
  const history = list.filter((p) => !p.is_active)

  return (
    <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-12">
      <div id="policy-form" className="scroll-mt-28 lg:col-span-5 xl:col-span-4">
        <PolicyForm
          key={editing?.id ?? 'new'}
          source={editing}
          onCancel={() => setEditing(null)}
          onCreated={onChange}
          baseOptions={[PIVOT, ...(rates.data ?? []).map((r) => r.currency)]}
        />
      </div>

      <div className="space-y-6 lg:col-span-7 xl:col-span-8">
        <ErrorBox message={error ?? policies.error} />
        {policies.loading && !policies.data && <Card><Loading rows={3} /></Card>}

        {policies.data && (
          <section className="relative rounded-card border border-brand-200 bg-brand-50 p-5 sm:p-6">
            {active ? (
              <>
                <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-600 text-white">
                      <Icon name="shield" size={19} />
                    </span>
                    <div>
                      <p className="text-xs font-medium text-brand-700">Política activa</p>
                      <h2 className="text-lg font-semibold tracking-tight text-ink">{active.name}</h2>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <p className="text-xs text-muted">Creada {dateTime(active.created_at)}</p>
                    <Button variant="secondary" size="sm" icon="pencil" onClick={() => startEdit(active)}>
                      Editar
                    </Button>
                    <ConfirmDelete
                      label={`Eliminar la política ${active.name}`}
                      warning="Sin política activa, el agente escalará todas las facturas. ¿Eliminar?"
                      onConfirm={() => remove(active.id)}
                    />
                  </div>
                </div>
                <div className="rounded-control bg-canvas p-4">
                  <Limits policy={active} />
                </div>
              </>
            ) : (
              <Empty icon="shield" title="No hay política activa">
                Crea una política para que el agente pueda aprobar facturas automáticamente.
              </Empty>
            )}
          </section>
        )}

        {history.length > 0 && (
          <Card title="Historial" subtitle="Puedes volver a activar cualquier versión anterior" action={<Tag tone="neutral">{history.length}</Tag>}>
            <ul className="divide-y divide-line">
              {history.map((p) => (
                <li key={p.id} className="relative py-4 first:pt-0 last:pb-0">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-ink">{p.name}</p>
                      <p className="text-xs text-subtle">Creada {dateTime(p.created_at)}</p>
                    </div>
                    <div className="flex shrink-0 items-center gap-1.5">
                      <IconButton icon="pencil" label={`Editar la política ${p.name}`} className="!h-8 !w-8" onClick={() => startEdit(p)} />
                      <Button variant="secondary" size="sm" disabled={busyId === p.id} onClick={() => activate(p.id)}>
                        {busyId === p.id ? 'Activando…' : 'Activar'}
                      </Button>
                      <ConfirmDelete label={`Eliminar la política ${p.name}`} onConfirm={() => remove(p.id)} />
                    </div>
                  </div>
                  <Limits policy={p} />
                </li>
              ))}
            </ul>
          </Card>
        )}

        <ExchangeRates rates={rates.data ?? []} policy={active} onChange={onChange} />
      </div>
    </div>
  )
}
