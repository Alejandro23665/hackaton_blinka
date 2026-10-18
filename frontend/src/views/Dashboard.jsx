import { useMemo } from 'react'
import { api } from '../api'
import { DistributionBar, SpendChart, StackedBars } from '../components/charts'
import Icon from '../components/icons'
import ReviewForm from '../components/ReviewForm'
import { Card, Empty, ErrorBox, Loading, StatusBadge, Tag, Tile } from '../components/ui'
import { dateTime, money, OUTCOME_SERIES, PERIOD_LABELS, shortDate } from '../format'
import { convert, ratesMap } from '../fx'
import { useLoad } from '../hooks'

const SPENT_STATUSES = ['approved', 'paid'] // igual que el backend
const DAY = 86_400_000

const utcKey = (d) => d.toISOString().slice(0, 10)
const localKey = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

/** Serie diaria del periodo actual a partir de las facturas reales (mismo criterio que la API). */
function buildSpendSeries(budget, invoices, rates) {
  const start = new Date(budget.period_start)
  const length =
    budget.period === 'weekly'
      ? 7
      : new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth() + 1, 0)).getUTCDate()
  const todayKey = utcKey(new Date())

  const dailyByKey = {}
  invoices
    .filter((inv) => SPENT_STATUSES.includes(inv.status))
    .forEach((inv) => {
      const amount = convert(inv.amount, inv.currency, budget.base_currency, rates)
      if (amount == null) return // sin tipo de cambio: el backend tampoco la suma (y lo avisa)
      const key = utcKey(new Date(inv.created_at))
      dailyByKey[key] = (dailyByKey[key] ?? 0) + amount
    })

  let running = 0
  return Array.from({ length }, (_, i) => {
    const date = new Date(start.getTime() + i * DAY)
    const key = utcKey(date)
    const daily = dailyByKey[key] ?? 0
    const past = key <= todayKey
    if (past) running += daily
    return {
      date: key,
      label:
        budget.period === 'weekly'
          ? date.toLocaleDateString('es', { weekday: 'short', timeZone: 'UTC' }).replace('.', '')
          : String(date.getUTCDate()),
      fullLabel: date.toLocaleDateString('es', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC' }),
      daily,
      cumulative: past ? running : null,
    }
  })
}

/** Decisiones de los últimos 7 días, por resultado. */
function buildActivity(decisions) {
  const today = new Date()
  const days = Array.from({ length: 7 }, (_, i) => {
    const date = new Date(today.getFullYear(), today.getMonth(), today.getDate() - (6 - i))
    return {
      key: localKey(date),
      label: date.toLocaleDateString('es', { weekday: 'short' }).replace('.', ''),
      fullLabel: date.toLocaleDateString('es', { weekday: 'long', day: 'numeric', month: 'short' }),
      isToday: i === 6,
      values: { approved: 0, escalated: 0, blocked: 0 },
    }
  })
  const byKey = Object.fromEntries(days.map((d) => [d.key, d]))
  decisions.forEach((d) => {
    const day = byKey[localKey(new Date(d.created_at))]
    if (day && d.outcome in day.values) day.values[d.outcome] += 1
  })
  return days
}

/* ---------------------------------------------------------------- */

function SpendCard({ policy, budget, invoices, rates, loading }) {
  const series = useMemo(
    () => (budget && invoices ? buildSpendSeries(budget, invoices, ratesMap(rates)) : []),
    [budget, invoices, rates],
  )

  if (loading) {
    return (
      <Card title="Gasto del periodo" className="lg:col-span-8">
        <Loading rows={4} />
      </Card>
    )
  }

  if (!policy) {
    return (
      <Card title="Gasto del periodo" className="lg:col-span-8">
        <Empty icon="shield" title="No hay política activa">
          Sin política, el agente escala todas las facturas a revisión humana. Crea una en Políticas.
        </Empty>
      </Card>
    )
  }

  const pct = budget ? (budget.spent / budget.period_budget) * 100 : 0
  const tone = pct >= 90 ? 'danger' : pct >= 70 ? 'warning' : 'brand'
  const approvedCount = invoices?.filter((i) => SPENT_STATUSES.includes(i.status)).length ?? 0
  const base = policy.base_currency

  return (
    <Card
      title="Gasto del periodo"
      subtitle={`${policy.name} · ${PERIOD_LABELS[policy.period]}${budget ? ` desde ${shortDate(budget.period_start)}` : ''}`}
      className="lg:col-span-8"
    >
      <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-5">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-4xl font-semibold tracking-tight text-ink tabular sm:text-[44px] sm:leading-none">{money(budget?.spent ?? 0)}
              <span className="ml-2 text-lg font-medium text-subtle">{base}</span>
            </p>
            <Tag tone={tone}>{pct.toLocaleString('es', { maximumFractionDigits: 1 })}% del presupuesto</Tag>
          </div>
          <p className="mt-2 text-[13px] text-muted">
            Aprobado en {approvedCount} {approvedCount === 1 ? 'factura' : 'facturas'} de {money(budget?.period_budget ?? policy.period_budget, base)}
          </p>
          {budget?.missing_rates?.length > 0 && (
            <p className="mt-2 flex items-start gap-1.5 text-xs text-warning-700">
              <Icon name="alert" size={14} className="mt-px" />
              Sin tipo de cambio para {budget.missing_rates.join(', ')}: esas facturas no se suman y el agente escalará las nuevas.
            </p>
          )}
        </div>

        <dl className="grid w-full grid-cols-3 gap-2 sm:w-auto sm:gap-3">
          {[
            ['Disponible', budget?.remaining ?? 0, 'text-brand-700'],
            ['Máx. por factura', policy.max_amount_per_invoice, 'text-ink'],
            ['Humano desde', policy.require_human_above, 'text-ink'],
          ].map(([label, value, color]) => (
            <Tile key={label} className="!px-3 !py-2.5 sm:min-w-32">
              <dt className="text-[11px] leading-tight text-muted">{label}</dt>
              <dd className={`mt-0.5 text-[15px] font-semibold tabular ${color}`}>{money(value, base)}</dd>
            </Tile>
          ))}
        </dl>
      </div>

      <div className="mt-5 h-2 overflow-hidden rounded-full bg-surface" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100} aria-label="Presupuesto consumido">
        <div
          className={`h-full rounded-full transition-[width] duration-500 ${tone === 'danger' ? 'bg-danger-600' : tone === 'warning' ? 'bg-warning-600' : 'bg-brand-600'}`}
          style={{ width: `${Math.min(100, pct)}%` }}
        />
      </div>

      <div className="mt-6 -mx-1">
        <SpendChart points={series} currency={base} />
      </div>
      <p className="mt-1 flex items-center gap-4 text-xs text-muted">
        <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 rounded-full bg-brand-600" />Acumulado</span>
        <span className="flex items-center gap-1.5"><span className="h-3 w-1 rounded-full bg-brand-200" />Aprobado por día</span>
        <span className="ml-auto hidden sm:inline">Montos en {base} · Monedas aceptadas: {policy.allowed_currencies.join(', ')}</span>
      </p>
    </Card>
  )
}

function ActivityCard({ invoices, decisions }) {
  const activity = useMemo(() => (decisions ? buildActivity(decisions) : []), [decisions])
  const count = (s) => invoices?.filter((i) => i.status === s).length ?? 0
  const weekTotal = activity.reduce((s, d) => s + d.values.approved + d.values.escalated + d.values.blocked, 0)

  return (
    <Card title="Actividad del agente" subtitle="Estado actual de las facturas" className="lg:col-span-4">
      {!invoices ? (
        <Loading rows={3} />
      ) : (
        <div className="md:grid md:grid-cols-2 md:items-center md:gap-8 lg:block">
          <DistributionBar items={OUTCOME_SERIES.map((s) => ({ ...s, value: count(s.key) }))} />
          <div className="mt-6 border-t border-line pt-5 md:mt-0 md:border-0 md:pt-0 lg:mt-6 lg:border-t lg:pt-5">
            <div className="mb-4 flex items-baseline justify-between">
              <p className="text-[13px] font-medium text-ink">Decisiones · últimos 7 días</p>
              <p className="text-2xl font-semibold text-ink tabular">{weekTotal}</p>
            </div>
            <StackedBars days={activity} series={OUTCOME_SERIES} height={150} />
          </div>
        </div>
      )}
    </Card>
  )
}

function Initials({ name }) {
  const initials = name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0])
    .join('')
    .toUpperCase()
  return (
    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-100 text-[13px] font-semibold text-brand-800">
      {initials}
    </span>
  )
}

function ReviewQueue({ invoices, vendorName, reasonFor, onChange, openInvoice }) {
  const escalated = invoices?.filter((i) => i.status === 'escalated') ?? []

  return (
    <Card
      title="Pendientes de revisión humana"
      subtitle="Facturas que el agente escaló por superar el umbral o por falta de política"
      action={escalated.length > 0 && <Tag tone="warning">{escalated.length} en cola</Tag>}
      className="lg:col-span-7"
    >
      {!invoices && <Loading rows={2} />}
      {invoices && escalated.length === 0 && (
        <Empty icon="check" title="Todo al día">No hay facturas esperando una decisión.</Empty>
      )}
      <ul className="space-y-3">
        {escalated.map((inv) => (
          <li key={inv.id} className="rounded-card border border-line p-4 transition-colors hover:border-brand-200">
            <div className="flex items-start gap-3">
              <Initials name={vendorName(inv.vendor_id)} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                  <button
                    onClick={() => openInvoice(inv.id)}
                    className="group inline-flex items-center gap-1 text-left text-sm font-semibold text-ink hover:text-brand-700"
                  >
                    {inv.invoice_number}
                    <Icon name="chevronRight" size={14} className="text-subtle transition-transform group-hover:translate-x-0.5 group-hover:text-brand-600" />
                  </button>
                  <p className="text-lg font-semibold text-ink tabular">{money(inv.amount, inv.currency)}</p>
                </div>
                <p className="text-[13px] text-muted">
                  {vendorName(inv.vendor_id)} · vence {shortDate(inv.due_date)}
                </p>
                {reasonFor(inv.id) && (
                  <p className="mt-2 rounded-control bg-warning-50 px-3 py-2 text-xs text-warning-700">{reasonFor(inv.id)}</p>
                )}
              </div>
            </div>
            <div className="mt-4 sm:pl-[52px]">
              <ReviewForm invoiceId={inv.id} onDone={onChange} />
            </div>
          </li>
        ))}
      </ul>
    </Card>
  )
}

const OUTCOME_ICON = {
  approved: { icon: 'check', className: 'bg-brand-100 text-brand-700' },
  escalated: { icon: 'user', className: 'bg-warning-50 text-warning-700' },
  blocked: { icon: 'x', className: 'bg-surface-strong text-muted' },
}

function RecentDecisions({ decisions, invoiceNumber, openInvoice }) {
  const recent = decisions?.slice(0, 7)
  return (
    <Card title="Últimas decisiones" subtitle="Del agente y del equipo" className="lg:col-span-5">
      {!decisions && <Loading rows={4} />}
      {decisions?.length === 0 && <Empty title="Sin decisiones aún">Ingresa una factura para ver al agente en acción.</Empty>}
      <ul className="-mx-2">
        {recent?.map((d) => {
          const o = OUTCOME_ICON[d.outcome]
          return (
            <li key={d.id}>
              <button
                onClick={() => openInvoice(d.invoice_id)}
                className="flex w-full items-start gap-3 rounded-control px-2 py-3 text-left transition-colors hover:bg-surface"
              >
                <span className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${o.className}`}>
                  <Icon name={o.icon} size={15} strokeWidth={2.25} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium text-ink">{invoiceNumber(d.invoice_id)}</span>
                    <StatusBadge status={d.outcome} size="sm" />
                  </span>
                  <span className="mt-0.5 line-clamp-2 block text-xs text-muted">{d.explanation}</span>
                  <span className="mt-1 flex items-center gap-1 text-[11px] text-subtle">
                    <Icon name={d.decided_by === 'agent' ? 'bot' : 'user'} size={12} />
                    {d.decided_by === 'agent' ? 'Agente' : 'Humano'} · {dateTime(d.created_at)}
                  </span>
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}

export default function Dashboard({ version, onChange, openInvoice }) {
  const invoices = useLoad(() => api.invoices.list(), version)
  const vendors = useLoad(() => api.vendors.list(), version)
  const decisions = useLoad(() => api.decisions.list({ limit: 500 }), version)
  const policy = useLoad(() => api.policies.active().catch(() => null), version)
  const budget = useLoad(() => api.policies.budget().catch(() => null), version)
  const rates = useLoad(() => api.exchangeRates.list(), version)

  const vendorName = (id) => vendors.data?.find((v) => v.id === id)?.name ?? `Proveedor #${id}`
  const invoiceNumber = (id) => invoices.data?.find((i) => i.id === id)?.invoice_number ?? `Factura #${id}`
  // decisions viene ordenado de más reciente a más antigua
  const reasonFor = (invoiceId) => decisions.data?.find((d) => d.invoice_id === invoiceId && d.decided_by === 'agent')?.explanation

  return (
    <div className="space-y-6">
      <ErrorBox message={invoices.error ?? decisions.error} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <SpendCard
          rates={rates.data}
          policy={policy.data}
          budget={budget.data}
          invoices={invoices.data}
          loading={(policy.loading && !policy.data) || (invoices.loading && !invoices.data)}
        />
        <ActivityCard invoices={invoices.data} decisions={decisions.data} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <ReviewQueue
          invoices={invoices.data}
          vendorName={vendorName}
          reasonFor={reasonFor}
          onChange={onChange}
          openInvoice={openInvoice}
        />
        <RecentDecisions decisions={decisions.data} invoiceNumber={invoiceNumber} openInvoice={openInvoice} />
      </div>
    </div>
  )
}
