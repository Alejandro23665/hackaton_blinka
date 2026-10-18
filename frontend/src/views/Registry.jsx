import { useState } from 'react'
import { api } from '../api'
import Icon from '../components/icons'
import { inputClass } from '../components/styles'
import { Card, Empty, ErrorBox, Loading, Segmented, StatusBadge } from '../components/ui'
import { dateTime, money, RULE_LABELS } from '../format'
import { useLoad } from '../hooks'

const OUTCOMES = [
  { value: '', label: 'Todas' },
  { value: 'approved', label: 'Aprobadas' },
  { value: 'escalated', label: 'Escaladas' },
  { value: 'blocked', label: 'Bloqueadas' },
]
const DECIDERS = [
  { value: '', label: 'Todos' },
  { value: 'agent', label: 'Agente' },
  { value: 'human', label: 'Humano' },
]

/**
 * Registro de todas las decisiones: qué se pagó, frenó o escaló, quién lo decidió y por qué.
 * Sustituye la hoja de cálculo de conciliación (se exporta a CSV con los mismos filtros).
 */
export default function Registry({ version, openInvoice }) {
  const [outcome, setOutcome] = useState('')
  const [decidedBy, setDecidedBy] = useState('')
  const [q, setQ] = useState('')
  const params = { outcome, decided_by: decidedBy, q: q.trim() }
  const log = useLoad(() => api.decisions.log(params), `${version}|${outcome}|${decidedBy}|${q.trim()}`)
  const rows = log.data ?? []

  return (
    <Card
      title="Registro de decisiones"
      subtitle="Cada factura que el agente pagó, frenó o escaló, y las decisiones humanas, con su motivo"
      action={
        <a
          href={api.decisions.exportUrl(params)}
          className="inline-flex h-8 items-center gap-1.5 rounded-control border border-line-strong bg-canvas px-3 text-[13px] font-medium text-ink shadow-control transition-colors hover:border-brand-300 hover:bg-brand-50"
        >
          <Icon name="download" size={15} />
          Exportar CSV
        </a>
      }
    >
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center">
        <Segmented options={OUTCOMES} value={outcome} onChange={setOutcome} size="sm" />
        <Segmented options={DECIDERS} value={decidedBy} onChange={setDecidedBy} size="sm" />
        <label htmlFor="registry-search" className="sr-only">Buscar en el registro</label>
        <input
          id="registry-search"
          className={`${inputClass} !h-9 lg:ml-auto lg:max-w-64`}
          placeholder="Buscar factura, proveedor o revisor"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>

      <ErrorBox message={log.error} />
      {log.loading && !log.data && <Loading rows={5} />}
      {log.data && rows.length === 0 && (
        <Empty icon="inbox" title="Sin decisiones">
          {outcome || decidedBy || q ? 'Prueba con otros filtros.' : 'Cuando el agente evalúe facturas aparecerán aquí.'}
        </Empty>
      )}

      {rows.length > 0 && (
        <>
          <p className="mb-2 text-xs text-muted">
            {rows.length} {rows.length === 1 ? 'decisión' : 'decisiones'}
            {rows.length >= 200 ? ' (se muestran las 200 más recientes; el CSV incluye todas)' : ''}
          </p>
          <ol className="divide-y divide-line rounded-card border border-line">
            {rows.map((r) => (
              <li key={r.id}>
                <button
                  onClick={() => openInvoice(r.invoice_id)}
                  className="grid w-full gap-2 px-4 py-3.5 text-left transition-colors hover:bg-surface sm:grid-cols-[150px_1fr_auto] sm:gap-4 sm:px-5"
                >
                  <div className="min-w-0">
                    <p className="text-xs text-subtle tabular">{dateTime(r.created_at)}</p>
                    <p className="mt-0.5 flex items-center gap-1 text-xs font-medium text-muted">
                      <Icon name={r.decided_by === 'agent' ? 'bot' : 'user'} size={13} />
                      {r.decided_by === 'agent' ? 'Agente' : r.reviewer ? r.reviewer : 'Humano'}
                    </p>
                  </div>
                  <div className="min-w-0">
                    <p className="flex flex-wrap items-baseline gap-x-2 text-sm">
                      <span className="font-semibold text-ink">{r.invoice_number}</span>
                      <span className="truncate text-muted">{r.vendor_name}</span>
                    </p>
                    <p className="mt-1 text-[13px] leading-relaxed text-ink">{r.explanation}</p>
                    {r.failed_rules.length > 0 && (
                      <p className="mt-1.5 flex flex-wrap gap-1">
                        {r.failed_rules.map((rule) => (
                          <span key={rule} className="rounded-full bg-surface px-2 py-0.5 text-[11px] font-medium text-muted">
                            {RULE_LABELS[rule] ?? rule}
                          </span>
                        ))}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center justify-between gap-3 sm:flex-col sm:items-end sm:justify-start">
                    <StatusBadge status={r.outcome} size="sm" />
                    <span className="text-sm font-semibold whitespace-nowrap text-ink tabular">{money(r.amount, r.currency)}</span>
                  </div>
                </button>
              </li>
            ))}
          </ol>
        </>
      )}
    </Card>
  )
}
