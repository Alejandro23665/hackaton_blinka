import { useState } from 'react'
import { api } from '../api'
import { dateTime, money, shortDate } from '../format'
import { useLoad } from '../hooks'
import ReviewForm from './ReviewForm'
import RulesList from './RulesList'
import { Button, ErrorBox, Loading, StatusBadge } from './ui'

const REEVALUABLE = ['pending', 'escalated', 'blocked']

/** Panel lateral con el detalle de una factura y su historial de decisiones. */
export default function InvoiceDetail({ invoiceId, onClose, onChange }) {
  const { data: invoice, error, loading, reload } = useLoad(() => api.invoices.get(invoiceId), invoiceId)
  const [actionError, setActionError] = useState(null)
  const [busy, setBusy] = useState(false)

  function refresh() {
    reload()
    onChange?.()
  }

  async function reevaluate() {
    setBusy(true)
    setActionError(null)
    try {
      await api.invoices.evaluate(invoiceId)
      refresh()
    } catch (e) {
      setActionError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-20 flex justify-end bg-slate-900/30" onClick={onClose}>
      <aside
        className="h-full w-full max-w-xl overflow-y-auto bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <p className="text-sm text-slate-500">Factura</p>
            <h2 className="text-xl font-semibold text-slate-900">{invoice?.invoice_number ?? '…'}</h2>
          </div>
          <button className="rounded-lg p-1 text-2xl leading-none text-slate-400 hover:text-slate-700" onClick={onClose} aria-label="Cerrar">
            ×
          </button>
        </div>

        {loading && !invoice && <Loading />}
        <ErrorBox message={error} />

        {invoice && (
          <div className="space-y-6">
            <dl className="grid grid-cols-2 gap-4 rounded-xl bg-slate-50 p-4 text-sm">
              <div>
                <dt className="text-slate-500">Proveedor</dt>
                <dd className="font-medium">
                  {invoice.vendor.name}
                  {!invoice.vendor.is_allowed && <span className="ml-1 text-xs text-rose-600">(no autorizado)</span>}
                </dd>
              </div>
              <div>
                <dt className="text-slate-500">Estado</dt>
                <dd><StatusBadge status={invoice.status} /></dd>
              </div>
              <div>
                <dt className="text-slate-500">Monto</dt>
                <dd className="text-lg font-semibold">{money(invoice.amount, invoice.currency)}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Vencimiento</dt>
                <dd className="font-medium">{shortDate(invoice.due_date)}</dd>
              </div>
            </dl>

            {invoice.status === 'escalated' && (
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                <p className="mb-3 text-sm font-medium text-amber-900">Esta factura espera tu decisión</p>
                <ReviewForm invoiceId={invoice.id} onDone={refresh} />
              </div>
            )}

            {REEVALUABLE.includes(invoice.status) && (
              <div className="space-y-2">
                <Button variant="secondary" disabled={busy} onClick={reevaluate}>
                  Reevaluar con la política activa
                </Button>
                <ErrorBox message={actionError} />
              </div>
            )}

            <div>
              <h3 className="mb-3 text-sm font-semibold text-slate-900">Historial de decisiones</h3>
              <ol className="space-y-4">
                {[...invoice.decisions].reverse().map((d) => (
                  <li key={d.id} className="rounded-xl border border-slate-200 p-4">
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      <StatusBadge status={d.outcome} />
                      <span className="text-xs text-slate-500">
                        {d.decided_by === 'agent' ? 'Agente' : 'Humano'} · {dateTime(d.created_at)}
                      </span>
                    </div>
                    <p className="mb-3 text-sm text-slate-700">{d.explanation}</p>
                    <RulesList rules={d.rules_evaluated} />
                  </li>
                ))}
              </ol>
            </div>

            <details className="text-sm">
              <summary className="cursor-pointer text-slate-500">Datos originales (raw_data)</summary>
              <pre className="mt-2 overflow-x-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">
                {JSON.stringify(invoice.raw_data, null, 2)}
              </pre>
            </details>
          </div>
        )}
      </aside>
    </div>
  )
}
