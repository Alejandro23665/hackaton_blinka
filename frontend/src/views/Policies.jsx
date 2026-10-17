import { useState } from 'react'
import { api } from '../api'
import Icon from '../components/icons'
import { Button, Card, Empty, ErrorBox, Field, Loading, Tag } from '../components/ui'
import { dateTime, money, PERIOD_LABELS } from '../format'
import { inputClass } from '../components/styles'
import { useLoad } from '../hooks'

const EMPTY_FORM = {
  name: '',
  max_amount_per_invoice: '',
  require_human_above: '',
  period_budget: '',
  period: 'monthly',
  allowed_currencies: 'USD',
}

function NewPolicyForm({ onCreated }) {
  const [form, setForm] = useState(EMPTY_FORM)
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
        is_active: true,
      })
      setForm(EMPTY_FORM)
      onCreated()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const number = `${inputClass} tabular`

  return (
    <Card title="Nueva política" subtitle="Al crearla queda activa; la anterior pasa al historial">
      <form className="space-y-4" onSubmit={submit} noValidate>
        <Field label="Nombre">
          <input className={inputClass} placeholder="Política Q4" value={form.name} onChange={set('name')} />
        </Field>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
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
        <Field label="Monedas permitidas" hint="Separadas por coma, ej. USD, EUR">
          <input className={`${inputClass} uppercase`} value={form.allowed_currencies} onChange={set('allowed_currencies')} />
        </Field>
        <ErrorBox message={error} />
        <Button type="submit" icon="shield" disabled={busy} className="w-full">
          {busy ? 'Guardando…' : 'Crear y activar'}
        </Button>
      </form>
    </Card>
  )
}

function Limits({ policy }) {
  const items = [
    ['Máx. por factura', money(policy.max_amount_per_invoice)],
    ['Humano desde', money(policy.require_human_above)],
    [`Presupuesto ${PERIOD_LABELS[policy.period].toLowerCase()}`, money(policy.period_budget)],
    ['Monedas', policy.allowed_currencies.join(', ')],
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

export default function Policies({ version, onChange }) {
  const policies = useLoad(() => api.policies.list(), version)
  const [error, setError] = useState(null)
  const [busyId, setBusyId] = useState(null)

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

  const list = policies.data ?? []
  const active = list.find((p) => p.is_active)
  const history = list.filter((p) => !p.is_active)

  return (
    <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-12">
      <div className="lg:col-span-5 xl:col-span-4">
        <NewPolicyForm onCreated={onChange} />
      </div>

      <div className="space-y-6 lg:col-span-7 xl:col-span-8">
        <ErrorBox message={error ?? policies.error} />
        {policies.loading && !policies.data && <Card><Loading rows={3} /></Card>}

        {policies.data && (
          <section className="rounded-card border border-brand-200 bg-brand-50 p-5 sm:p-6">
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
                  <p className="text-xs text-muted">Creada {dateTime(active.created_at)}</p>
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
                <li key={p.id} className="py-4 first:pt-0 last:pb-0">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-ink">{p.name}</p>
                      <p className="text-xs text-subtle">Creada {dateTime(p.created_at)}</p>
                    </div>
                    <Button variant="secondary" size="sm" disabled={busyId === p.id} onClick={() => activate(p.id)}>
                      {busyId === p.id ? 'Activando…' : 'Activar'}
                    </Button>
                  </div>
                  <Limits policy={p} />
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>
    </div>
  )
}
