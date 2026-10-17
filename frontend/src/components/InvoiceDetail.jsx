import { useEffect, useState } from 'react'
import { api } from '../api'
import { dateTime, money, shortDate } from '../format'
import { useLoad } from '../hooks'
import Icon from './icons'
import ReviewForm from './ReviewForm'
import RulesList from './RulesList'
import { Button, ErrorBox, IconButton, Loading, StatusBadge, Tile } from './ui'

const REEVALUABLE = ['pending', 'escalated', 'blocked']

/** Panel lateral con el detalle de una factura y su historial de decisiones. */
export default function InvoiceDetail({ invoiceId, onClose, onChange }) {
  const { data: invoice, error, loading, reload } = useLoad(() => api.invoices.get(invoiceId), invoiceId)
  const [actionError, setActionError] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = overflow
    }
  }, [onClose])

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
    <div className="fixed inset-0 z-30 flex justify-end bg-ink/20 backdrop-blur-[2px]" onClick={onClose}>
      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="invoice-title"
        className="flex h-full w-full max-w-xl flex-col bg-canvas shadow-pop sm:rounded-l-[24px]"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-start justify-between gap-4 border-b border-line px-5 py-5 sm:px-7">
          <div className="min-w-0">
            <p className="text-xs font-medium text-subtle">Factura</p>
            <h2 id="invoice-title" className="truncate text-xl font-semibold tracking-tight text-ink">
              {invoice?.invoice_number ?? '…'}
            </h2>
          </div>
          <div className="flex items-center gap-3">
            {invoice && <StatusBadge status={invoice.status} />}
            <IconButton icon="x" label="Cerrar" onClick={onClose} />
          </div>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-6 sm:px-7">
          {loading && !invoice && <Loading rows={4} />}
          <ErrorBox message={error} />

          {invoice && (
            <div className="space-y-7">
              <div className="grid grid-cols-2 gap-3">
                <Tile className="col-span-2">
                  <p className="text-xs text-muted">Monto</p>
                  <p className="mt-1 text-3xl font-semibold tracking-tight text-ink tabular">{money(invoice.amount, invoice.currency)}</p>
                </Tile>
                <Tile>
                  <p className="text-xs text-muted">Proveedor</p>
                  <p className="mt-1 truncate text-sm font-semibold text-ink">{invoice.vendor.name}</p>
                  <p className={`mt-0.5 text-xs ${invoice.vendor.is_allowed ? 'text-success-700' : 'text-danger-600'}`}>
                    {invoice.vendor.is_allowed ? 'Autorizado' : 'No autorizado'}
                  </p>
                </Tile>
                <Tile>
                  <p className="text-xs text-muted">Vencimiento</p>
                  <p className="mt-1 text-sm font-semibold text-ink">{shortDate(invoice.due_date)}</p>
                  <p className="mt-0.5 text-xs text-subtle">Recibida {dateTime(invoice.created_at)}</p>
                </Tile>
              </div>

              {invoice.status === 'escalated' && (
                <section className="rounded-card border border-warning-600/20 bg-warning-50 p-4">
                  <p className="mb-3 flex items-center gap-2 text-sm font-semibold text-warning-700">
                    <Icon name="user" size={16} />
                    Esta factura espera tu decisión
                  </p>
                  <ReviewForm invoiceId={invoice.id} onDone={refresh} />
                </section>
              )}

              {REEVALUABLE.includes(invoice.status) && (
                <div className="space-y-2">
                  <Button variant="secondary" icon="refresh" disabled={busy} onClick={reevaluate}>
                    {busy ? 'Reevaluando…' : 'Reevaluar con la política activa'}
                  </Button>
                  <ErrorBox message={actionError} />
                </div>
              )}

              <section>
                <h3 className="mb-4 text-sm font-semibold text-ink">Historial de decisiones</h3>
                <ol className="relative space-y-6 border-l border-line pl-6">
                  {[...invoice.decisions].reverse().map((d) => (
                    <li key={d.id} className="relative">
                      <span className="absolute top-1 -left-[31px] flex h-4 w-4 items-center justify-center rounded-full border-2 border-canvas bg-brand-600 ring-1 ring-brand-200" />
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        <StatusBadge status={d.outcome} size="sm" />
                        <span className="flex items-center gap-1 text-xs text-subtle">
                          <Icon name={d.decided_by === 'agent' ? 'bot' : 'user'} size={13} />
                          {d.decided_by === 'agent' ? 'Agente' : 'Humano'} · {dateTime(d.created_at)}
                        </span>
                      </div>
                      <p className="mb-3 text-sm leading-relaxed text-ink">{d.explanation}</p>
                      <RulesList rules={d.rules_evaluated} />
                    </li>
                  ))}
                </ol>
              </section>

              <details className="group rounded-control border border-line">
                <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-[13px] font-medium text-muted hover:text-ink">
                  <Icon name="code" size={16} />
                  Datos originales (raw_data)
                  <Icon name="chevronRight" size={14} className="ml-auto transition-transform group-open:rotate-90" />
                </summary>
                <pre className="overflow-x-auto border-t border-line bg-surface px-4 py-3 text-xs leading-relaxed text-ink">
                  {JSON.stringify(invoice.raw_data, null, 2)}
                </pre>
              </details>
            </div>
          )}
        </div>
      </aside>
    </div>
  )
}
