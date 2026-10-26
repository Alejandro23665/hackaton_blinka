import { useState } from 'react'
import { api } from '../api'
import { Card, ErrorBox, Loading, Segmented, Tile, Eyebrow } from '../components/ui'
import { FIELD_LABELS } from '../format'
import { useLoad } from '../hooks'

// Paleta categórica validada (contraste y daltonismo) sobre fondo claro
const BLUE = '#2a78d6'
const ORANGE = '#eb6834'
const VIOLET = '#6250d6'
const BRAND = '#6d28d9'

const STAGES = { CLASIFICACION: 'Clasificación de páginas', LECTURA_1: 'Primera lectura', LECTURA_2: 'Segunda lectura (verificación)' }

const compact = new Intl.NumberFormat('es-CL', { notation: 'compact', maximumFractionDigits: 1 })
const integer = new Intl.NumberFormat('es-CL')
const tokens = (n) => (n >= 10000 ? compact.format(n) : integer.format(n))
const usd = (n) => (n == null ? '—' : `US$ ${n.toLocaleString('es-CL', { minimumFractionDigits: 2, maximumFractionDigits: n < 1 ? 4 : 2 })}`)
const percent = (part, whole) => (whole ? `${Math.round((part / whole) * 100)} %` : '—')
const seconds = (s) => (s == null ? '—' : s < 90 ? `${Math.round(s)} s` : `${(s / 60).toLocaleString('es-CL', { maximumFractionDigits: 1 })} min`)
const dayLabel = (iso) =>
  new Date(iso).toLocaleDateString('es-CL', { day: 'numeric', month: 'short', timeZone: 'UTC' })

function Stat({ label, value, hint, tone = 'text-ink' }) {
  return (
    <Tile>
      <Eyebrow>{label}</Eyebrow>
      <p className={`mt-1 text-2xl font-semibold tabular ${tone}`}>{value}</p>
      {hint && <p className="mt-0.5 text-xs text-muted">{hint}</p>}
    </Tile>
  )
}

function Legend({ series }) {
  return (
    <div className="flex flex-wrap gap-4 text-xs text-muted">
      {series.map((s) => (
        <span key={s.key} className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm" style={{ background: s.color }} />
          {s.label}
        </span>
      ))}
    </div>
  )
}

/** Barras por día (apiladas si hay más de una serie), con el detalle del día al pasar el cursor. */
function DailyBars({ days, series, format, height = 160 }) {
  const [hover, setHover] = useState(null)
  const totals = days.map((d) => series.reduce((sum, s) => sum + (d[s.key] || 0), 0))
  const max = Math.max(...totals, 0)
  const ticks = [0, Math.floor(days.length / 2), days.length - 1]

  return (
    <div>
      <div className="relative flex gap-2">
        <div className="flex w-12 shrink-0 flex-col justify-between text-right text-[11px] text-subtle tabular" style={{ height }}>
          <span>{format(max)}</span>
          <span>{format(max / 2)}</span>
          <span>0</span>
        </div>
        <div className="relative flex-1">
          <div className="absolute inset-0 flex flex-col justify-between" aria-hidden="true">
            {[0, 1, 2].map((i) => (
              <div key={i} className="border-t border-line" />
            ))}
          </div>
          <div className="relative flex items-end gap-[2px]" style={{ height }}>
            {days.map((d, i) => (
              <div
                key={d.fecha}
                className="relative flex h-full flex-1 cursor-default flex-col-reverse"
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover(null)}
              >
                {series.map((s, j) => {
                  const value = d[s.key] || 0
                  if (!value || !max) return null
                  const top = series.slice(j + 1).every((next) => !d[next.key])
                  return (
                    <div
                      key={s.key}
                      className={top ? 'rounded-t-[4px]' : ''}
                      style={{
                        height: `${(value / max) * 100}%`,
                        background: s.color,
                        marginTop: top ? 0 : 2,
                        opacity: hover == null || hover === i ? 1 : 0.55,
                      }}
                    />
                  )
                })}
                {hover === i && (
                  <div
                    role="tooltip"
                    className={`pointer-events-none absolute bottom-full z-10 mb-2 w-max rounded-control border border-line bg-canvas px-3 py-2 text-xs shadow-card ${
                      i > days.length / 2 ? 'right-0' : 'left-0'
                    }`}
                  >
                    <p className="mb-1 font-medium text-ink">{dayLabel(d.fecha)}</p>
                    {series.map((s) => (
                      <p key={s.key} className="flex items-center gap-1.5 text-muted">
                        <span className="h-2 w-2 rounded-sm" style={{ background: s.color }} />
                        {s.label}: <span className="tabular font-medium text-ink">{format(d[s.key] || 0)}</span>
                      </p>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="mt-1.5 flex justify-between pl-14 text-[11px] text-subtle">
        {ticks.map((i) => (
          <span key={i}>{days[i] && dayLabel(days[i].fecha)}</span>
        ))}
      </div>
    </div>
  )
}

/** Campos que más faltan o generan dudas: barras horizontales apiladas. */
function FieldBars({ fields }) {
  const max = Math.max(...fields.map((f) => f.faltante + f.dudoso), 0)
  return (
    <ul className="space-y-2.5">
      {fields.map((f) => (
        <li key={f.campo} className="grid grid-cols-[minmax(0,10rem)_1fr_auto] items-center gap-3 text-sm">
          <span className="truncate text-ink">{FIELD_LABELS[f.campo] ?? f.campo}</span>
          <span className="flex h-3 gap-[2px]" title={`Faltan: ${f.faltante} · Con dudas: ${f.dudoso}`}>
            {f.faltante > 0 && (
              <span className={`h-full ${f.dudoso ? 'rounded-l-[4px]' : 'rounded-[4px]'}`} style={{ width: `${(f.faltante / max) * 100}%`, background: ORANGE }} />
            )}
            {f.dudoso > 0 && (
              <span className={`h-full ${f.faltante ? 'rounded-r-[4px]' : 'rounded-[4px]'}`} style={{ width: `${(f.dudoso / max) * 100}%`, background: VIOLET }} />
            )}
          </span>
          <span className="text-xs text-muted tabular">
            {f.faltante} · {f.dudoso}
          </span>
        </li>
      ))}
    </ul>
  )
}

const TOKEN_SERIES = [
  { key: 'tokens_entrada', label: 'Tokens de entrada', color: BLUE },
  { key: 'tokens_salida', label: 'Tokens de salida (incluye razonamiento)', color: ORANGE },
]

/** Métricas de uso de la IA (tokens y costo) y de rendimiento de la IA y del sistema. */
export default function Metrics() {
  const [days, setDays] = useState(30)
  const data = useLoad(() => api.metrics(days), days)
  const m = data.data

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">Métricas</h1>
          <p className="mt-0.5 text-[13px] text-muted">
            {m ? `Del ${dayLabel(m.periodo.desde)} al ${dayLabel(m.periodo.hasta)}` : 'Uso de la IA y rendimiento'}
          </p>
        </div>
        <Segmented
          value={days}
          onChange={setDays}
          options={[
            { value: 7, label: '7 días' },
            { value: 30, label: '30 días' },
            { value: 90, label: '90 días' },
          ]}
        />
      </div>

      <ErrorBox message={data.error} />
      {!m && data.loading && <Loading rows={6} />}

      {m && (
        <>
          <Card
            title="Uso de IA"
            subtitle={`Modelo ${m.uso.modelo}. Costo estimado con sus precios (en tandas, a mitad de precio); las respuestas de la caché no se cobran.`}
          >
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Tokens de entrada" value={tokens(m.uso.tokens_entrada)} hint="Instrucciones e imágenes" />
              <Stat label="Tokens de salida" value={tokens(m.uso.tokens_salida)} hint="Respuestas y razonamiento" />
              <Stat
                label="Costo estimado"
                value={usd(m.uso.costo_usd)}
                hint={m.uso.costo_por_documento_usd != null ? `${usd(m.uso.costo_por_documento_usd)} por documento leído (${m.uso.documentos_leidos})` : 'Sin documentos leídos'}
              />
              <Stat label="Llamadas a la IA" value={integer.format(m.uso.llamadas)} hint="Solicitudes pagadas" />
            </div>

            <div className="mt-6 flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-[13px] font-medium text-ink">Tokens por día</h3>
              <Legend series={TOKEN_SERIES} />
            </div>
            <div className="mt-3">
              <DailyBars days={m.uso.por_dia} series={TOKEN_SERIES} format={tokens} />
            </div>

            <div className="-mx-5 mt-6 overflow-x-auto sm:-mx-6">
              <table className="w-full min-w-[560px] text-left text-sm">
                <thead>
                  <tr className="border-b border-line text-xs text-subtle">
                    <th className="px-5 py-2 font-medium sm:pl-6">Etapa</th>
                    <th className="px-3 py-2 text-right font-medium">Llamadas</th>
                    <th className="px-3 py-2 text-right font-medium">Entrada</th>
                    <th className="px-3 py-2 text-right font-medium">Salida</th>
                    <th className="px-5 py-2 text-right font-medium sm:pr-6">Costo</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {m.uso.por_etapa.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-5 py-4 text-center text-[13px] text-muted sm:px-6">
                        Sin llamadas a la IA en este periodo.
                      </td>
                    </tr>
                  )}
                  {m.uso.por_etapa.map((s) => (
                    <tr key={s.etapa}>
                      <td className="px-5 py-2.5 sm:pl-6">{STAGES[s.etapa] ?? s.etapa}</td>
                      <td className="px-3 py-2.5 text-right tabular">{integer.format(s.llamadas)}</td>
                      <td className="px-3 py-2.5 text-right tabular">{integer.format(s.tokens_entrada)}</td>
                      <td className="px-3 py-2.5 text-right tabular">{integer.format(s.tokens_salida)}</td>
                      <td className="px-5 py-2.5 text-right tabular sm:pr-6">{usd(s.costo_usd)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card title="Rendimiento de la IA" subtitle="Documentos registrados en el periodo">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Documentos" value={integer.format(m.ia.documentos)} hint="FC, CI y GD guardados" />
              <Stat
                label="Legibles sin intervención"
                value={percent(m.ia.sin_intervencion, m.ia.documentos)}
                hint={`${m.ia.sin_intervencion} documentos`}
                tone="text-success-700"
              />
              <Stat
                label="Pendientes de revisión"
                value={percent(m.ia.pendientes, m.ia.documentos)}
                hint={`${m.ia.pendientes_no_legibles} no legibles · ${m.ia.pendientes_descuadre} descuadres`}
                tone="text-warning-700"
              />
              <Stat
                label="Revisados por una persona"
                value={percent(m.ia.revisados, m.ia.documentos)}
                hint={`${m.ia.revisados} documentos`}
                tone="text-brand-700"
              />
            </div>

            <div className="mt-6 flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-[13px] font-medium text-ink">Campos que más fallan</h3>
              <Legend
                series={[
                  { key: 'f', label: 'Faltan (no se leyeron)', color: ORANGE },
                  { key: 'd', label: 'Con dudas (lectura no fiable)', color: VIOLET },
                ]}
              />
            </div>
            <div className="mt-3">
              {m.ia.campos.length ? (
                <FieldBars fields={m.ia.campos} />
              ) : (
                <p className="text-[13px] text-muted">Ningún campo con problemas en este periodo.</p>
              )}
            </div>
          </Card>

          <Card title="Rendimiento del sistema">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Tandas enviadas" value={integer.format(m.sistema.tandas)} hint="Message Batches" />
              <Stat label="Espera promedio" value={seconds(m.sistema.espera_promedio_s)} hint="Hasta que Claude responde una tanda" />
              <Stat label="Espera máxima" value={seconds(m.sistema.espera_maxima_s)} />
              <Stat
                label="Llamadas con error"
                value={m.sistema.tasa_error == null ? '—' : `${(m.sistema.tasa_error * 100).toLocaleString('es-CL', { maximumFractionDigits: 1 })} %`}
                hint={`${m.sistema.resultados.ERROR} errores · ${m.sistema.resultados.RECHAZO} rechazos · ${m.sistema.resultados.FORMATO} incompletas`}
                tone={m.sistema.tasa_error ? 'text-danger-700' : 'text-ink'}
              />
            </div>
            <h3 className="mt-6 mb-3 text-[13px] font-medium text-ink">Documentos procesados por día</h3>
            <DailyBars
              days={m.sistema.por_dia}
              series={[{ key: 'documentos', label: 'Documentos', color: BRAND }]}
              format={(n) => integer.format(Math.round(n))}
              height={120}
            />
          </Card>
        </>
      )}
    </div>
  )
}
