import { useState } from 'react'
import { api } from '../api'
import { Button, Card, Empty, ErrorBox, Field, inputClass, Loading, StatusBadge } from '../components/ui'
import { dateTime, money, shortDate, STATUS } from '../format'
import { useLoad } from '../hooks'

const EMPTY_FORM = { vendor_id: '', invoice_number: '', amount: '', currency: 'USD', due_date: '' }

function NewInvoiceForm({ vendors, currencies, onCreated }) {
  const [form, setForm] = useState(EMPTY_FORM)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (key) => (e) => {
    setForm({ ...form, [key]: e.target.value })
    setError(null)
  }

  async function submit(e) {
    e.preventDefault()
    if (!form.vendor_id || !form.invoice_number.trim() || !form.amount || !form.due_date) {
      setError('Completa todos los campos')
      return
    }
    setBusy(true)
    try {
      const invoice = await api.invoices.create({
        ...form,
        vendor_id: Number(form.vendor_id),
        invoice_number: form.invoice_number.trim(),
        amount: Number(form.amount),
      })
      setForm({ ...EMPTY_FORM, vendor_id: form.vendor_id, currency: form.currency })
      onCreated(invoice)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title="Nueva factura">
      <form className="space-y-4" onSubmit={submit}>
        <Field label="Proveedor">
          <select className={inputClass} value={form.vendor_id} onChange={set('vendor_id')}>
            <option value="">Selecciona…</option>
            {vendors.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}{v.is_allowed ? '' : ' (no autorizado)'}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Número de factura">
          <input className={inputClass} placeholder="INV-0001" value={form.invoice_number} onChange={set('invoice_number')} />
        </Field>
        <div className="grid grid-cols-3 gap-3">
          <div className="col-span-2">
            <Field label="Monto">
              <input className={inputClass} type="number" min="0.01" step="0.01" placeholder="0.00" value={form.amount} onChange={set('amount')} />
            </Field>
          </div>
          <Field label="Moneda">
            <input className={`${inputClass} uppercase`} maxLength={3} list="currencies" value={form.currency} onChange={set('currency')} />
            <datalist id="currencies">
              {currencies.map((c) => <option key={c} value={c} />)}
            </datalist>
          </Field>
        </div>
        <Field label="Vencimiento">
          <input className={inputClass} type="date" value={form.due_date} onChange={set('due_date')} />
        </Field>
        <ErrorBox message={error} />
        <Button type="submit" disabled={busy} className="w-full">
          {busy ? 'Evaluando…' : 'Enviar al agente'}
        </Button>
      </form>
    </Card>
  )
}

export default function Invoices({ version, onChange, openInvoice }) {
  const [filter, setFilter] = useState('')
  const invoices = useLoad(() => api.invoices.list({ status: filter }), `${version}-${filter}`)
  const vendors = useLoad(() => api.vendors.list(), version)
  const policy = useLoad(() => api.policies.active().catch(() => null), version)

  const vendorName = (id) => vendors.data?.find((v) => v.id === id)?.name ?? `#${id}`

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="lg:col-span-1">
        <NewInvoiceForm
          vendors={vendors.data ?? []}
          currencies={policy.data?.allowed_currencies ?? []}
          onCreated={(invoice) => {
            onChange()
            openInvoice(invoice.id)
          }}
        />
      </div>

      <div className="lg:col-span-2">
        <Card
          title="Facturas"
          action={
            <div className="flex flex-wrap gap-1">
              {[['', 'Todas'], ...Object.entries(STATUS).map(([k, v]) => [k, v.label])].map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setFilter(key)}
                  className={`rounded-full px-3 py-1 text-xs font-medium ${
                    filter === key ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          }
        >
          <ErrorBox message={invoices.error} />
          {invoices.loading && !invoices.data && <Loading />}
          {invoices.data?.length === 0 && <Empty>No hay facturas{filter && ' con este estado'}.</Empty>}
          {invoices.data?.length > 0 && (
            <div className="-mx-5 overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="text-left text-xs text-slate-500">
                  <tr className="border-b border-slate-100">
                    <th className="px-5 py-2 font-medium">Número</th>
                    <th className="px-3 py-2 font-medium">Proveedor</th>
                    <th className="px-3 py-2 text-right font-medium">Monto</th>
                    <th className="px-3 py-2 font-medium">Vence</th>
                    <th className="px-3 py-2 font-medium">Estado</th>
                    <th className="hidden px-5 py-2 font-medium xl:table-cell">Recibida</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {invoices.data.map((inv) => (
                    <tr key={inv.id} className="cursor-pointer hover:bg-slate-50" onClick={() => openInvoice(inv.id)}>
                      <td className="whitespace-nowrap px-5 py-3 font-medium text-slate-900">{inv.invoice_number}</td>
                      <td className="px-3 py-3">{vendorName(inv.vendor_id)}</td>
                      <td className="whitespace-nowrap px-3 py-3 text-right font-medium">{money(inv.amount, inv.currency)}</td>
                      <td className="whitespace-nowrap px-3 py-3">{shortDate(inv.due_date)}</td>
                      <td className="px-3 py-3"><StatusBadge status={inv.status} /></td>
                      <td className="hidden whitespace-nowrap px-5 py-3 text-slate-500 xl:table-cell">{dateTime(inv.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
