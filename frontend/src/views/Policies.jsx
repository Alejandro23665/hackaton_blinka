import { useState } from 'react'
import { api } from '../api'
import { Button, Card, Empty, ErrorBox, Field, inputClass, Loading } from '../components/ui'
import { dateTime, money, PERIOD_LABELS } from '../format'
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

  return (
    <Card title="Nueva política">
      <p className="mb-4 text-sm text-slate-500">
        Las políticas no se editan: al crear una nueva queda activa y la anterior se guarda en el historial.
      </p>
      <form className="space-y-4" onSubmit={submit}>
        <Field label="Nombre">
          <input className={inputClass} placeholder="Política Q4" value={form.name} onChange={set('name')} />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Máximo por factura" hint="Por encima → bloqueada">
            <input className={inputClass} type="number" min="0.01" step="0.01" value={form.max_amount_per_invoice} onChange={set('max_amount_per_invoice')} />
          </Field>
          <Field label="Revisión humana desde" hint="Por encima → escalada">
            <input className={inputClass} type="number" min="0.01" step="0.01" value={form.require_human_above} onChange={set('require_human_above')} />
          </Field>
          <Field label="Presupuesto del periodo">
            <input className={inputClass} type="number" min="0.01" step="0.01" value={form.period_budget} onChange={set('period_budget')} />
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
        <Button type="submit" disabled={busy} className="w-full">Crear y activar</Button>
      </form>
    </Card>
  )
}

export default function Policies({ version, onChange }) {
  const policies = useLoad(() => api.policies.list(), version)
  const [error, setError] = useState(null)

  async function activate(id) {
    try {
      await api.policies.activate(id)
      onChange()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-5">
      <div className="lg:col-span-2">
        <NewPolicyForm onCreated={onChange} />
      </div>
      <div className="lg:col-span-3">
        <Card title="Historial de políticas">
          <ErrorBox message={error ?? policies.error} />
          {policies.loading && !policies.data && <Loading />}
          {policies.data?.length === 0 && <Empty>Crea la primera política para que el agente pueda aprobar facturas.</Empty>}
          <ul className="space-y-3">
            {policies.data?.map((p) => (
              <li key={p.id} className={`rounded-xl border p-4 ${p.is_active ? 'border-indigo-300 bg-indigo-50/50' : 'border-slate-200'}`}>
                <div className="mb-3 flex items-center justify-between gap-2">
                  <div>
                    <p className="font-medium text-slate-900">{p.name}</p>
                    <p className="text-xs text-slate-500">Creada {dateTime(p.created_at)}</p>
                  </div>
                  {p.is_active ? (
                    <span className="rounded-full bg-indigo-600 px-2.5 py-0.5 text-xs font-medium text-white">Activa</span>
                  ) : (
                    <Button variant="secondary" onClick={() => activate(p.id)}>Activar</Button>
                  )}
                </div>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-4">
                  <div><dt className="text-xs text-slate-500">Máx. factura</dt><dd>{money(p.max_amount_per_invoice)}</dd></div>
                  <div><dt className="text-xs text-slate-500">Humano desde</dt><dd>{money(p.require_human_above)}</dd></div>
                  <div><dt className="text-xs text-slate-500">Presupuesto</dt><dd>{money(p.period_budget)} · {PERIOD_LABELS[p.period]}</dd></div>
                  <div><dt className="text-xs text-slate-500">Monedas</dt><dd>{p.allowed_currencies.join(', ')}</dd></div>
                </dl>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  )
}
