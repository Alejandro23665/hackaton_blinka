import { api } from '../api'
import ReviewForm from '../components/ReviewForm'
import { Card, Empty, ErrorBox, Loading, StatusBadge } from '../components/ui'
import { dateTime, money, PERIOD_LABELS, shortDate } from '../format'
import { useLoad } from '../hooks'

function BudgetCard({ version }) {
  const policy = useLoad(() => api.policies.active().catch(() => null), version)
  const budget = useLoad(() => api.policies.budget().catch(() => null), version)

  if (policy.loading && !policy.data) return <Card title="Presupuesto"><Loading /></Card>
  if (!policy.data) {
    return (
      <Card title="Presupuesto">
        <p className="text-sm text-amber-700">No hay política activa: el agente escalará todas las facturas.</p>
      </Card>
    )
  }

  const b = budget.data
  const pct = b ? Math.min(100, (b.spent / b.period_budget) * 100) : 0
  const bar = pct >= 90 ? 'bg-rose-500' : pct >= 70 ? 'bg-amber-500' : 'bg-emerald-500'

  return (
    <Card title="Presupuesto del periodo">
      <p className="mb-1 text-sm text-slate-500">
        {policy.data.name} · {PERIOD_LABELS[policy.data.period]}
        {b && ` desde ${shortDate(b.period_start)}`}
      </p>
      {b && (
        <>
          <p className="text-2xl font-semibold text-slate-900">
            {money(b.spent)} <span className="text-base font-normal text-slate-500">/ {money(b.period_budget)}</span>
          </p>
          <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-slate-100">
            <div className={`h-full rounded-full ${bar} transition-all`} style={{ width: `${pct}%` }} />
          </div>
          <p className="mt-2 text-sm text-slate-600">Disponible: <strong>{money(b.remaining)}</strong></p>
        </>
      )}
      <dl className="mt-4 grid grid-cols-2 gap-2 border-t border-slate-100 pt-4 text-sm">
        <dt className="text-slate-500">Máx. por factura</dt>
        <dd className="text-right font-medium">{money(policy.data.max_amount_per_invoice)}</dd>
        <dt className="text-slate-500">Revisión humana desde</dt>
        <dd className="text-right font-medium">{money(policy.data.require_human_above)}</dd>
        <dt className="text-slate-500">Monedas</dt>
        <dd className="text-right font-medium">{policy.data.allowed_currencies.join(', ')}</dd>
      </dl>
    </Card>
  )
}

function Stats({ invoices }) {
  const count = (s) => invoices.filter((i) => i.status === s).length
  const items = [
    { status: 'approved', label: 'Aprobadas', color: 'text-emerald-600' },
    { status: 'escalated', label: 'Escaladas', color: 'text-amber-600' },
    { status: 'blocked', label: 'Bloqueadas', color: 'text-rose-600' },
  ]
  return (
    <div className="grid grid-cols-3 gap-4">
      {items.map((it) => (
        <div key={it.status} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-sm text-slate-500">{it.label}</p>
          <p className={`text-3xl font-semibold ${it.color}`}>{count(it.status)}</p>
        </div>
      ))}
    </div>
  )
}

export default function Dashboard({ version, onChange, openInvoice }) {
  const invoices = useLoad(() => api.invoices.list(), version)
  const vendors = useLoad(() => api.vendors.list(), version)
  const decisions = useLoad(() => api.decisions.list({ limit: 8 }), version)

  const vendorName = (id) => vendors.data?.find((v) => v.id === id)?.name ?? `#${id}`
  const invoiceById = (id) => invoices.data?.find((i) => i.id === id)
  const escalated = invoices.data?.filter((i) => i.status === 'escalated') ?? []

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        {invoices.data && <Stats invoices={invoices.data} />}
        <ErrorBox message={invoices.error} />

        <Card title={`Pendientes de revisión humana (${escalated.length})`}>
          {invoices.loading && !invoices.data && <Loading />}
          {invoices.data && escalated.length === 0 && <Empty>Nada pendiente. El agente lo tiene bajo control.</Empty>}
          <ul className="space-y-4">
            {escalated.map((inv) => (
              <li key={inv.id} className="rounded-xl border border-amber-200 bg-amber-50/50 p-4">
                <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
                  <button className="text-left" onClick={() => openInvoice(inv.id)}>
                    <span className="font-medium text-slate-900 hover:underline">{inv.invoice_number}</span>
                    <span className="ml-2 text-sm text-slate-500">{vendorName(inv.vendor_id)}</span>
                  </button>
                  <span className="font-semibold">{money(inv.amount, inv.currency)}</span>
                </div>
                <ReviewForm invoiceId={inv.id} onDone={onChange} />
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <div className="space-y-6">
        <BudgetCard version={version} />

        <Card title="Últimas decisiones">
          {decisions.loading && !decisions.data && <Loading />}
          {decisions.data?.length === 0 && <Empty>Aún no hay decisiones.</Empty>}
          <ul className="divide-y divide-slate-100">
            {decisions.data?.map((d) => {
              const inv = invoiceById(d.invoice_id)
              return (
                <li key={d.id}>
                  <button className="w-full py-3 text-left hover:bg-slate-50" onClick={() => openInvoice(d.invoice_id)}>
                    <div className="mb-1 flex items-center justify-between gap-2">
                      <span className="text-sm font-medium text-slate-900">{inv?.invoice_number ?? `Factura #${d.invoice_id}`}</span>
                      <StatusBadge status={d.outcome} />
                    </div>
                    <p className="line-clamp-2 text-xs text-slate-500">{d.explanation}</p>
                    <p className="mt-1 text-xs text-slate-400">
                      {d.decided_by === 'agent' ? 'Agente' : 'Humano'} · {dateTime(d.created_at)}
                    </p>
                  </button>
                </li>
              )
            })}
          </ul>
        </Card>
      </div>
    </div>
  )
}
