import { useEffect, useState } from 'react'
import { api } from '../api'
import { dateTime, money, RULE_LABELS, shortDate } from '../format'
import { useLoad } from '../hooks'
import Icon from './icons'
import ReviewForm from './ReviewForm'
import RulesList from './RulesList'
import { Button, ConfirmDelete, ErrorBox, IconButton, Loading, StatusBadge } from './ui'

const REEVALUABLE = ['pending', 'escalated', 'blocked']
// Las aprobadas/pagadas son dinero comprometido: no se borran (igual que en la API)
const DELETABLE = ['pending', 'escalated', 'blocked']

const VERDICT = {
  approved: {
    title: 'Aprobada para pago',
    icon: 'check',
    box: 'border-success-600/20 bg-success-50',
    badge: 'bg-success-600 text-white',
    text: 'text-success-700',
  },
  blocked: {
    title: 'Rechazada',
    icon: 'x',
    box: 'border-danger-600/20 bg-danger-50',
    badge: 'bg-danger-600 text-white',
    text: 'text-danger-700',
  },
  escalated: {
    title: 'Escalada a revisión humana',
    icon: 'user',
    box: 'border-warning-600/20 bg-warning-50',
    badge: 'bg-warning-600 text-white',
    text: 'text-warning-700',
  },
}

/** Quita el prefijo "Bloqueada: …" que ya expresa el título. */
const reasonText = (explanation) =>
  explanation.replace(/^(Aprobada|Bloqueada|Escalada a revisión humana)\s*:\s*/i, '')

/* ------------------------------------------------------------------ */

function DocumentPreview({ document }) {
  const url = api.documents.fileUrl(document.id)
  const isPdf = document.content_type === 'application/pdf'
  const isText = document.content_type === 'text/plain'
  const text = useLoad(() => (isText ? fetch(url).then((r) => r.text()) : Promise.resolve(null)), url)
  const [zoom, setZoom] = useState(false)

  return (
    <div className="flex h-full min-h-0 flex-col bg-surface">
      <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5">
        <p className="flex min-w-0 items-center gap-2 text-[13px] font-medium text-ink">
          <Icon name="file" size={16} className="shrink-0 text-subtle" />
          <span className="truncate" title={document.original_name}>{document.original_name}</span>
        </p>
        <div className="flex shrink-0 items-center gap-1">
          {!isPdf && !isText && (
            <button
              type="button"
              onClick={() => setZoom((z) => !z)}
              className="h-8 rounded-control px-2.5 text-xs font-medium text-muted transition-colors hover:bg-canvas hover:text-ink"
            >
              {zoom ? 'Ajustar' : 'Ampliar'}
            </button>
          )}
          <a
            href={url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-8 items-center gap-1.5 rounded-control px-2.5 text-xs font-medium text-muted transition-colors hover:bg-canvas hover:text-ink"
          >
            <Icon name="external" size={14} />
            Abrir
          </a>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto p-3 sm:p-4">
        {isText ? (
          <pre className="h-full min-h-[200px] overflow-auto whitespace-pre-wrap break-words rounded-control border border-line bg-canvas p-4 font-mono text-[13px] leading-relaxed text-ink">
            {text.data ?? (text.error ? 'No se pudo cargar el mensaje.' : 'Cargando…')}
          </pre>
        ) : isPdf ? (
          <>
            {/* Los navegadores móviles no muestran PDF incrustados: ahí se ofrece abrirlo */}
            <iframe
              title={`Factura ${document.original_name}`}
              src={url}
              className="hidden h-full min-h-[420px] w-full rounded-control border border-line bg-canvas lg:block"
            />
            <a
              href={url}
              target="_blank"
              rel="noreferrer"
              className="flex h-full flex-col items-center justify-center gap-3 rounded-control border border-dashed border-line-strong bg-canvas p-6 text-center lg:hidden"
            >
              <span className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-100 text-brand-700">
                <Icon name="file" size={22} />
              </span>
              <span className="text-sm font-semibold text-ink">Ver la factura en PDF</span>
              <span className="text-xs text-muted">Se abre en una pestaña nueva</span>
            </a>
          </>
        ) : (
          <img
            src={url}
            alt={`Factura ${document.original_name}`}
            onClick={() => setZoom((z) => !z)}
            className={`mx-auto rounded-control border border-line bg-canvas shadow-card transition-[max-width] ${
              zoom ? 'max-w-none cursor-zoom-out' : 'max-h-full max-w-full cursor-zoom-in object-contain'
            }`}
          />
        )}
      </div>
    </div>
  )
}

function DecisionPanel({ invoice }) {
  const latest = invoice.decisions.at(-1)
  if (!latest) return null
  const v = VERDICT[latest.outcome]
  const failed = latest.rules_evaluated.filter((r) => !r.passed)
  const total = latest.rules_evaluated.length

  return (
    <section className={`rounded-card border p-4 sm:p-5 ${v.box}`} aria-labelledby="decision-title">
      <div className="flex items-start gap-3">
        <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${v.badge}`}>
          <Icon name={v.icon} size={20} strokeWidth={2.25} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.06em] text-muted">
            <Icon name={latest.decided_by === 'agent' ? 'bot' : 'user'} size={13} />
            {latest.decided_by === 'agent' ? 'Decisión del agente' : `Decisión de ${latest.reviewer ?? 'una persona'}`} ·{' '}
            {dateTime(latest.created_at)}
          </p>
          <h3 id="decision-title" className={`mt-0.5 text-lg font-semibold tracking-tight ${v.text}`}>{v.title}</h3>
          {/* Si hay reglas incumplidas, el motivo es la lista de abajo; si no, el texto de la decisión */}
          <p className="mt-1 text-sm leading-relaxed text-ink">
            <span className="font-medium">Por qué: </span>
            {failed.length > 0
              ? `${failed.length === 1 ? 'no cumple una regla' : `no cumple ${failed.length} reglas`} de la política.`
              : reasonText(latest.explanation)}
          </p>
        </div>
      </div>

      {failed.length > 0 && (
        <ul className="mt-4 space-y-2.5 border-t border-ink/5 pt-4">
          {failed.map((r) => (
            <li key={r.rule} className="flex items-start gap-2 text-[13px]">
              <span
                className={`mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                  r.severity === 'hard' ? 'bg-danger-600/10 text-danger-700' : 'bg-warning-600/10 text-warning-700'
                }`}
              >
                {r.severity === 'hard' ? 'Bloquea' : 'Escala'}
              </span>
              <span className="min-w-0">
                <span className="font-medium text-ink">{RULE_LABELS[r.rule] ?? r.rule}: </span>
                <span className="text-muted">{r.detail}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
      {latest.outcome === 'approved' && total > 0 && (
        <p className="mt-3 text-[13px] text-success-700">Cumple las {total} reglas de la política.</p>
      )}
    </section>
  )
}

function ReadField({ label, value, hint, emphasis = false, wide = false }) {
  return (
    <div className={wide ? 'sm:col-span-2' : ''}>
      <p className="mb-1 text-xs font-medium text-muted">{label}</p>
      <div
        className={`flex min-h-10 items-center rounded-control border border-line bg-surface px-3 py-2 text-ink tabular ${
          emphasis ? 'text-lg font-semibold' : 'text-sm'
        } ${value == null || value === '' ? 'text-subtle' : ''}`}
      >
        <span className="min-w-0 break-words">{value == null || value === '' ? 'No figura en la factura' : value}</span>
      </div>
      {hint && <p className="mt-1 text-[11px] text-warning-700">{hint}</p>}
    </div>
  )
}

/** Formulario (de solo lectura) con todos los datos de la factura, extraídos o registrados. */
function InvoiceForm({ invoice }) {
  const extraction = invoice.document?.extraction
  const data = extraction?.data ?? {}
  const vendor = invoice.vendor
  const confidence = extraction ? Math.round((extraction.confidence ?? 0) * 100) : null
  const warnings = extraction?.warnings ?? []
  const vendorState = vendor.is_allowed ? 'Autorizado' : vendor.needs_review ? 'Nuevo · pendiente de aprobar' : 'No autorizado'
  const amountOrNull = (v) => (v == null ? null : money(v, invoice.currency))

  return (
    <section aria-labelledby="form-title">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 id="form-title" className="text-sm font-semibold text-ink">Datos de la factura</h3>
        {extraction ? (
          <span className="flex items-center gap-1.5 text-xs text-muted">
            <Icon name="sparkles" size={13} className="text-brand-600" />
            Extraídos por el agente
          </span>
        ) : (
          <span className="text-xs text-muted">Ingresada manualmente</span>
        )}
      </div>

      {confidence != null && (
        <div className="mb-4 flex items-center gap-3 rounded-control border border-line px-3 py-2.5">
          <span className="text-xs text-muted">Confianza de lectura</span>
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface">
            <div className={`h-full rounded-full ${confidence >= 80 ? 'bg-brand-600' : 'bg-warning-600'}`} style={{ width: `${confidence}%` }} />
          </div>
          <span className="text-xs font-semibold text-ink tabular">{confidence}%</span>
        </div>
      )}

      <div className="grid grid-cols-1 gap-x-4 gap-y-3 sm:grid-cols-2">
        <ReadField label="Proveedor" value={vendor.name} wide />
        <ReadField label="ID fiscal" value={data.vendor_tax_id ?? vendor.tax_id} />
        <ReadField label="Estado del proveedor" value={vendorState} />
        <ReadField label="Número de factura" value={invoice.invoice_number} />
        <ReadField label="Moneda" value={invoice.currency} />
        <ReadField label="Fecha de emisión" value={data.issue_date ? shortDate(data.issue_date) : null} />
        <ReadField
          label="Fecha de vencimiento"
          value={shortDate(invoice.due_date)}
          hint={extraction && !data.due_date ? 'No figura en la factura; se tomó otra fecha' : null}
        />
        <ReadField label="Subtotal" value={amountOrNull(data.subtotal)} />
        <ReadField label="Impuestos" value={amountOrNull(data.tax_amount)} />
        <ReadField label="Total a pagar" value={money(invoice.amount, invoice.currency)} emphasis wide />
      </div>

      {warnings.length > 0 && (
        <ul className="mt-4 space-y-1.5">
          {warnings.map((raw) => {
            // Avisos antiguos son texto suelto: se muestran como críticos, igual que los trata el agente
            const w = typeof raw === 'string' ? { text: raw, critical: true } : raw
            return (
              <li
                key={w.text}
                className={`flex gap-1.5 rounded-control px-3 py-2 text-xs ${
                  w.critical ? 'bg-warning-50 text-warning-700' : 'bg-surface text-muted'
                }`}
              >
                <Icon name="alert" size={13} className="mt-px shrink-0" />
                <span>
                  <span className="font-semibold">{w.critical ? 'Duda en la lectura: ' : 'Aviso informativo: '}</span>
                  {w.text}
                </span>
              </li>
            )
          })}
        </ul>
      )}
      <p className="mt-3 text-[11px] text-subtle">
        Recibida {dateTime(invoice.created_at)}
        {extraction?.model ? ` · Modelo ${extraction.model}` : ''}
      </p>
    </section>
  )
}

function DetailBody({ invoice, refresh, onDeleted }) {
  const [actionError, setActionError] = useState(null)
  const [busy, setBusy] = useState(false)
  const latestAgent = [...invoice.decisions].reverse().find((d) => d.decided_by === 'agent')
  const history = [...invoice.decisions].reverse()

  async function remove() {
    setActionError(null)
    try {
      await api.invoices.remove(invoice.id)
      onDeleted()
    } catch (e) {
      setActionError(e.message)
    }
  }

  async function reevaluate() {
    setBusy(true)
    setActionError(null)
    try {
      await api.invoices.evaluate(invoice.id)
      refresh()
    } catch (e) {
      setActionError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-7">
      <DecisionPanel invoice={invoice} />

      {invoice.status === 'escalated' && (
        <section className="rounded-card border border-line p-4">
          <p className="mb-3 text-sm font-semibold text-ink">Tu decisión</p>
          <ReviewForm invoiceId={invoice.id} onDone={refresh} />
        </section>
      )}

      <InvoiceForm invoice={invoice} />

      {latestAgent && (
        <section>
          <h3 className="mb-3 text-sm font-semibold text-ink">Reglas evaluadas por el agente</h3>
          <RulesList rules={latestAgent.rules_evaluated} />
          {REEVALUABLE.includes(invoice.status) && (
            <div className="mt-3 space-y-2">
              <Button variant="secondary" size="sm" icon="refresh" disabled={busy} onClick={reevaluate}>
                {busy ? 'Reevaluando…' : 'Reevaluar con la política activa'}
              </Button>
              <ErrorBox message={actionError} />
            </div>
          )}
        </section>
      )}

      {history.length > 1 && (
        <details className="group rounded-control border border-line">
          <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-[13px] font-medium text-muted hover:text-ink">
            <Icon name="refresh" size={15} />
            Historial de decisiones ({history.length})
            <Icon name="chevronRight" size={14} className="ml-auto transition-transform group-open:rotate-90" />
          </summary>
          <ol className="space-y-4 border-t border-line px-4 py-4">
            {history.map((d) => (
              <li key={d.id}>
                <div className="mb-1 flex flex-wrap items-center gap-2">
                  <StatusBadge status={d.outcome} size="sm" />
                  <span className="flex items-center gap-1 text-xs text-subtle">
                    <Icon name={d.decided_by === 'agent' ? 'bot' : 'user'} size={12} />
                    {d.decided_by === 'agent' ? 'Agente' : d.reviewer ?? 'Humano'} · {dateTime(d.created_at)}
                  </span>
                </div>
                <p className="text-[13px] text-ink">{d.explanation}</p>
              </li>
            ))}
          </ol>
        </details>
      )}

      {DELETABLE.includes(invoice.status) && (
        <section className="relative flex items-center justify-between gap-3 rounded-control border border-line px-4 py-3">
          <div className="min-w-0">
            <p className="text-[13px] font-medium text-ink">Eliminar factura</p>
            <p className="text-xs text-muted">Borra también sus decisiones{invoice.document ? ' y el archivo subido' : ''}.</p>
          </div>
          <ConfirmDelete
            label={`Eliminar la factura ${invoice.invoice_number}`}
            warning={`¿Eliminar la factura ${invoice.invoice_number} y su historial?`}
            onConfirm={remove}
          />
        </section>
      )}

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
  )
}

/**
 * Detalle de factura. Si viene de un archivo, se muestra en vista dividida:
 * el documento a la izquierda y la decisión + los datos a la derecha.
 */
export default function InvoiceDetail({ invoiceId, onClose, onChange }) {
  const { data: invoice, error, loading, reload } = useLoad(() => api.invoices.get(invoiceId), invoiceId)

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

  const split = Boolean(invoice?.document)

  const header = (
    <header className="flex shrink-0 items-start justify-between gap-4 border-b border-line px-5 py-4 sm:px-6">
      <div className="min-w-0">
        <p className="text-xs font-medium text-subtle">Factura{invoice ? ` · ${invoice.vendor.name}` : ''}</p>
        <h2 id="invoice-title" className="truncate text-xl font-semibold tracking-tight text-ink">
          {invoice?.invoice_number ?? '…'}
        </h2>
      </div>
      <div className="flex items-center gap-3">
        {invoice && <span className="hidden text-lg font-semibold text-ink tabular sm:inline">{money(invoice.amount, invoice.currency)}</span>}
        {invoice && <StatusBadge status={invoice.status} />}
        <IconButton icon="x" label="Cerrar" onClick={onClose} />
      </div>
    </header>
  )

  const body = (
    <>
      {loading && !invoice && <Loading rows={4} />}
      <ErrorBox message={error} />
      {invoice && (
        <DetailBody
          invoice={invoice}
          refresh={refresh}
          onDeleted={() => {
            onChange?.()
            onClose()
          }}
        />
      )}
    </>
  )

  return (
    <div
      className={`fixed inset-0 z-30 flex bg-ink/25 backdrop-blur-[2px] ${split ? 'items-stretch justify-center sm:p-4 lg:p-6' : 'justify-end'}`}
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="invoice-title"
        onClick={(e) => e.stopPropagation()}
        className={`flex w-full flex-col overflow-hidden bg-canvas shadow-pop ${
          split ? 'max-w-[1400px] sm:rounded-[24px]' : 'h-full max-w-xl sm:rounded-l-[24px]'
        }`}
      >
        {header}
        {split ? (
          // Móvil: todo en una columna con un solo scroll. Escritorio: dos columnas con scroll propio.
          <div className="min-h-0 flex-1 overflow-y-auto lg:grid lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] lg:overflow-hidden">
            <div
              className={`border-b border-line lg:h-auto lg:min-h-0 lg:border-r lg:border-b-0 ${
                invoice.document.content_type === 'application/pdf' ? 'h-56' : 'h-[55vh]'
              }`}
            >
              <DocumentPreview document={invoice.document} />
            </div>
            <div className="px-5 py-6 sm:px-6 lg:min-h-0 lg:overflow-y-auto">{body}</div>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto px-5 py-6 sm:px-6">{body}</div>
        )}
      </div>
    </div>
  )
}
