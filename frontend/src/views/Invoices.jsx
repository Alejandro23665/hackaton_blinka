import { useState } from 'react'
import { api } from '../api'
import Icon from '../components/icons'
import UploadCard from '../components/UploadCard'
import { Button, Card, Empty, ErrorBox, Field, Loading, Segmented, StatusBadge } from '../components/ui'
import { dateTime, money, shortDate, STATUS } from '../format'
import { inputClass } from '../components/styles'
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
    <Card title="Ingreso manual" subtitle="Para facturas sin archivo; el agente la evalúa al enviarla">
      <form className="space-y-4" onSubmit={submit} noValidate>
        <Field label="Proveedor">
          <select className={inputClass} value={form.vendor_id} onChange={set('vendor_id')}>
            <option value="">Selecciona un proveedor</option>
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
        <div className="grid grid-cols-[1fr_96px] gap-3">
          <Field label="Monto">
            <input className={`${inputClass} tabular`} type="number" inputMode="decimal" min="0.01" step="0.01" placeholder="0,00" value={form.amount} onChange={set('amount')} />
          </Field>
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
        <Button type="submit" icon="bot" disabled={busy} className="w-full">
          {busy ? 'Evaluando…' : 'Enviar al agente'}
        </Button>
      </form>
    </Card>
  )
}

function VendorCell({ name }) {
  return (
    <span className="flex min-w-0 items-center gap-2.5">
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-100 text-[11px] font-semibold text-brand-800">
        {name.slice(0, 1).toUpperCase()}
      </span>
      <span className="truncate">{name}</span>
    </span>
  )
}

export default function Invoices({ version, onChange, openInvoice }) {
  const [filter, setFilter] = useState('')
  const [manualOpen, setManualOpen] = useState(false)
  // Se cargan todas para mostrar el conteo por estado; el filtro se aplica en cliente
  const invoices = useLoad(() => api.invoices.list(), version)
  const vendors = useLoad(() => api.vendors.list(), version)
  const policy = useLoad(() => api.policies.active().catch(() => null), version)

  const vendorName = (id) => vendors.data?.find((v) => v.id === id)?.name ?? `#${id}`
  const all = invoices.data ?? []
  const rows = filter ? all.filter((i) => i.status === filter) : all
  const filterOptions = [
    { value: '', label: 'Todas', count: all.length },
    ...Object.entries(STATUS).map(([value, s]) => ({ value, label: s.label, count: all.filter((i) => i.status === value).length })),
  ]

  return (
    <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-12">
      <div className="space-y-4 lg:col-span-4">
        <UploadCard version={version} onChange={onChange} openInvoice={openInvoice} />

        <button
          type="button"
          aria-expanded={manualOpen}
          onClick={() => setManualOpen((o) => !o)}
          className="flex w-full items-center justify-between rounded-control px-1 py-1 text-[13px] font-medium text-muted transition-colors hover:text-ink"
        >
          ¿No tienes el archivo? Ingresar los datos a mano
          <Icon name="chevronRight" size={16} className={`transition-transform ${manualOpen ? 'rotate-90' : ''}`} />
        </button>
        {manualOpen && (
          <NewInvoiceForm
            vendors={vendors.data ?? []}
            currencies={policy.data?.allowed_currencies ?? []}
            onCreated={(invoice) => {
              onChange()
              openInvoice(invoice.id)
            }}
          />
        )}
      </div>

      <div className="lg:col-span-8">
        <Card title="Facturas" subtitle="Selecciona una factura para ver las reglas y su historial">
          <Segmented options={filterOptions} value={filter} onChange={setFilter} size="sm" className="mb-4" />
          <ErrorBox message={invoices.error} />
          {invoices.loading && !invoices.data && <Loading rows={5} />}
          {invoices.data && rows.length === 0 && (
            <Empty icon="file" title={filter ? 'Sin facturas con este estado' : 'Aún no hay facturas'}>
              {filter ? 'Prueba con otro filtro.' : 'Sube la primera factura para que el agente la procese.'}
            </Empty>
          )}

          {rows.length > 0 && (
            <>
              {/* Escritorio y tablet: tabla */}
              <div className="-mx-5 hidden sm:-mx-6 sm:block">
                <table className="w-full table-fixed text-sm">
                  <thead>
                    <tr className="border-y border-line bg-surface text-left text-xs font-medium text-muted">
                      <th className="w-[22%] py-2.5 pr-3 pl-6 font-medium">Número</th>
                      <th className="py-2.5 pr-3 font-medium">Proveedor</th>
                      <th className="w-[20%] py-2.5 pr-3 text-right font-medium">Monto</th>
                      <th className="hidden w-[15%] py-2.5 pr-3 font-medium md:table-cell">Vence</th>
                      <th className="w-[17%] py-2.5 pr-6 font-medium">Estado</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {rows.map((inv) => (
                      <tr
                        key={inv.id}
                        tabIndex={0}
                        onClick={() => openInvoice(inv.id)}
                        onKeyDown={(e) => e.key === 'Enter' && openInvoice(inv.id)}
                        className="cursor-pointer transition-colors hover:bg-brand-50/60 focus-visible:bg-brand-50"
                      >
                        <td className="truncate py-3.5 pr-3 pl-6 font-medium text-ink">{inv.invoice_number}</td>
                        <td className="py-3.5 pr-3 text-ink"><VendorCell name={vendorName(inv.vendor_id)} /></td>
                        <td className="py-3.5 pr-3 text-right font-semibold whitespace-nowrap text-ink tabular">
                          {money(inv.amount)} <span className="text-xs font-medium text-subtle">{inv.currency}</span>
                        </td>
                        <td className="hidden py-3.5 pr-3 whitespace-nowrap text-muted md:table-cell">{shortDate(inv.due_date)}</td>
                        <td className="py-3.5 pr-6"><StatusBadge status={inv.status} size="sm" /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Móvil: lista de tarjetas */}
              <ul className="space-y-2 sm:hidden">
                {rows.map((inv) => (
                  <li key={inv.id}>
                    <button
                      onClick={() => openInvoice(inv.id)}
                      className="flex w-full items-center gap-3 rounded-control border border-line p-3 text-left transition-colors active:bg-surface"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate text-sm font-semibold text-ink">{inv.invoice_number}</span>
                          <span className="text-sm font-semibold whitespace-nowrap text-ink tabular">{money(inv.amount, inv.currency)}</span>
                        </div>
                        <div className="mt-1 flex items-center justify-between gap-2">
                          <span className="truncate text-xs text-muted">{vendorName(inv.vendor_id)} · {dateTime(inv.created_at)}</span>
                          <StatusBadge status={inv.status} size="sm" />
                        </div>
                      </div>
                      <Icon name="chevronRight" size={16} className="text-subtle" />
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </Card>
      </div>
    </div>
  )
}
