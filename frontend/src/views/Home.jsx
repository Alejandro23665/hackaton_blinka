import { api } from '../api'
import Icon from '../components/icons'
import { inputClass } from '../components/styles'
import { Button, Empty, ErrorBox, Loading, PageHeader } from '../components/ui'
import { longDate } from '../format'
import { href, useLoad, usePolling, useViewState } from '../hooks'

/** Qué pasó con los documentos registrados en el día. */
const OUTCOMES = [
  {
    key: 'procesados_ia',
    label: 'Procesados por la IA',
    hint: 'Resueltos sin intervención de una persona',
    icon: 'bot',
    chip: 'bg-success-50 text-success-700 ring-success-600/20',
    bar: 'bg-success-600',
  },
  {
    key: 'requieren_revision',
    label: 'Requieren revisión humana',
    hint: 'Descuadres, tipos dudosos y desconocidos, pendientes',
    icon: 'flag',
    chip: 'bg-brand-50 text-brand-700 ring-brand-600/20',
    bar: 'bg-brand-600',
  },
  {
    key: 'revisados',
    label: 'Revisados por una persona',
    hint: 'Corregidos o confirmados',
    icon: 'user',
    chip: 'bg-slate-50 text-slate-700 ring-slate-600/20',
    bar: 'bg-slate-600',
  },
]

const share = (part, whole) => (whole ? Math.round((part / whole) * 100) : 0)

/** Los documentos del día y qué se hizo con ellos, con su proporción sobre el total registrado. */
function DayLedger({ data }) {
  return (
    <section className="rounded-card border border-line bg-canvas shadow-card">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line px-5 py-5 sm:px-6">
        <div>
          <p className="text-[13px] font-medium text-muted">Documentos registrados</p>
          <p className="mt-1 text-[44px] leading-none font-semibold tracking-[-0.03em] text-ink tabular">{data.registrados}</p>
        </div>
        <p className="max-w-[16rem] text-xs leading-relaxed text-subtle sm:text-right">
          Facturas, controles y guías guardados durante el día.
        </p>
      </div>

      {data.registrados === 0 ? (
        <Empty
          icon="inbox"
          title="Sin documentos este día"
          action={
            <Button variant="secondary" icon="upload" onClick={() => (window.location.hash = href('subir'))}>
              Subir documentos
            </Button>
          }
        >
          Cuando se suban y procesen documentos, aquí verás cuántos resolvió la IA y cuántos necesitan a una persona.
        </Empty>
      ) : (
        <ul className="divide-y divide-line">
          {OUTCOMES.map((o) => {
            const value = data[o.key]
            const pct = share(value, data.registrados)
            return (
              <li key={o.key} className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-4 gap-y-2 px-5 py-4 sm:px-6">
                <span className={`flex h-9 w-9 items-center justify-center rounded-[9px] ring-1 ring-inset ${o.chip}`}>
                  <Icon name={o.icon} size={18} />
                </span>
                <span className="min-w-0">
                  <span className="block text-sm font-medium text-ink">{o.label}</span>
                  <span className="block truncate text-xs text-subtle">{o.hint}</span>
                </span>
                <span className="text-right">
                  <span className="block text-xl font-semibold text-ink tabular">{value}</span>
                  <span className="block text-[11.5px] text-subtle tabular">{pct} %</span>
                </span>
                <span
                  className="col-span-3 h-1.5 overflow-hidden rounded-full bg-surface sm:col-span-2 sm:col-start-2"
                  role="img"
                  aria-label={`${pct} % de los registrados`}
                >
                  <span
                    className={`block h-full rounded-full transition-[width] duration-500 ease-out ${o.bar}`}
                    style={{ width: `${Math.min(pct, 100)}%` }}
                  />
                </span>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

/** La cola de revisión de todos los días: la siguiente acción de quien opera. */
function QueuePanel({ pending }) {
  const clear = pending === 0
  return (
    <section className="relative flex flex-col overflow-hidden rounded-card bg-brand-950 p-6 text-white shadow-pop">
      <div aria-hidden="true" className="v-hatch absolute inset-0" />
      <div aria-hidden="true" className="absolute -top-24 -right-20 h-64 w-64 rounded-full bg-brand-600/30 blur-3xl" />
      <div className="relative flex items-center gap-2 text-[13px] font-medium text-white/70">
        <Icon name="scan" size={16} />
        Cola de revisión
      </div>
      <p className="relative mt-6 text-[56px] leading-none font-semibold tracking-[-0.04em] tabular">{pending}</p>
      <p className="relative mt-2 text-sm text-white/75">
        {clear
          ? 'Todo al día: no hay documentos esperando a una persona.'
          : `documento${pending === 1 ? '' : 's'} esperando a una persona, de todos los días.`}
      </p>
      <div className="relative mt-auto pt-8">
        <a
          href={href('revision')}
          className={`inline-flex h-10 w-full items-center justify-center gap-2 rounded-control text-sm font-medium transition-[background-color,transform] duration-150 active:scale-[0.98] ${
            clear ? 'bg-white/10 text-white hover:bg-white/15' : 'bg-white text-brand-950 hover:bg-brand-50'
          }`}
        >
          {clear ? 'Ver la cola' : 'Empezar a revisar'}
          <Icon name="arrowUpRight" size={16} />
        </a>
      </div>
    </section>
  )
}

const SHORTCUTS = [
  { section: 'subir', icon: 'upload', label: 'Subir documentos', hint: 'Imágenes, PDF o carpetas completas' },
  { section: 'documentos', icon: 'file', label: 'Ver documentos', hint: 'Buscar por RUT o folio y filtrar' },
  { section: 'metricas', icon: 'chart', label: 'Métricas', hint: 'Uso de la IA y rendimiento' },
]

/** Pantalla principal: totales de un día (por defecto, hoy). */
export default function Home() {
  const [fecha, setFecha] = useViewState('inicio.fecha', '')
  const day = useLoad(() => api.documents.day(fecha || undefined), fecha)
  // Mientras se mira el día de hoy, las cifras se actualizan solas
  usePolling(day.reload, !fecha, 15000)
  const data = day.data

  return (
    <div className="space-y-6 lg:space-y-8">
      <PageHeader
        eyebrow={fecha ? 'Día seleccionado' : 'Hoy'}
        title={<span className="first-letter:uppercase">{data ? longDate(data.fecha) : '…'}</span>}
        meta={!fecha && 'Las cifras se actualizan solas mientras miras el día de hoy.'}
        actions={
          <>
            <label className="block">
              <span className="mb-1.5 block text-[13px] font-medium text-ink">Ver otro día</span>
              <input
                type="date"
                value={fecha || data?.fecha || ''}
                onChange={(e) => setFecha(e.target.value)}
                className={`${inputClass} w-44`}
              />
            </label>
            {fecha && (
              <Button variant="secondary" onClick={() => setFecha('')}>
                Volver a hoy
              </Button>
            )}
          </>
        }
      />

      <ErrorBox message={day.error} />
      {!data && day.loading && <Loading rows={4} />}

      {data && (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px] lg:gap-6">
          <DayLedger data={data} />
          <QueuePanel pending={data.pendientes_total} />
        </div>
      )}

      <nav aria-label="Accesos directos" className="grid gap-3 sm:grid-cols-3">
        {SHORTCUTS.map((s) => (
          <a
            key={s.section}
            href={href(s.section)}
            className="group flex items-center gap-3 rounded-card border border-line bg-canvas px-4 py-3.5 transition-colors hover:border-brand-300"
          >
            <Icon name={s.icon} size={18} className="text-brand-600" />
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-medium text-ink">{s.label}</span>
              <span className="block truncate text-xs text-subtle">{s.hint}</span>
            </span>
            <Icon
              name="chevronRight"
              size={16}
              className="text-subtle transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-brand-600"
            />
          </a>
        ))}
      </nav>
    </div>
  )
}
