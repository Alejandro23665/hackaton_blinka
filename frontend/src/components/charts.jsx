import { useEffect, useRef, useState } from 'react'
import { compact, money } from '../format'

function useWidth() {
  const ref = useRef(null)
  const [width, setWidth] = useState(0)
  useEffect(() => {
    if (!ref.current) return
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
    observer.observe(ref.current)
    return () => observer.disconnect()
  }, [])
  return [ref, width]
}

/** Curva suave que pasa por todos los puntos (Catmull-Rom → Bézier), sin sobrepasar demasiado. */
function smoothPath(pts) {
  if (pts.length < 2) return pts.length ? `M${pts[0].x},${pts[0].y}` : ''
  let d = `M${pts[0].x},${pts[0].y}`
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i]
    const p1 = pts[i]
    const p2 = pts[i + 1]
    const p3 = pts[i + 2] ?? p2
    const t = 0.16
    const c1 = { x: p1.x + (p2.x - p0.x) * t, y: p1.y + (p2.y - p0.y) * t }
    const c2 = { x: p2.x - (p3.x - p1.x) * t, y: p2.y - (p3.y - p1.y) * t }
    // Mantiene los puntos de control dentro del tramo: la curva no sobrepasa los datos (sin valores negativos falsos)
    const lo = Math.min(p1.y, p2.y)
    const hi = Math.max(p1.y, p2.y)
    c1.y = Math.min(Math.max(c1.y, lo), hi)
    c2.y = Math.min(Math.max(c2.y, lo), hi)
    d += ` C${c1.x},${c1.y} ${c2.x},${c2.y} ${p2.x},${p2.y}`
  }
  return d
}

function niceMax(value) {
  if (value <= 0) return 1
  const exp = 10 ** Math.floor(Math.log10(value))
  const n = value / exp
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * exp
}

/**
 * Gasto acumulado del periodo.
 * points: [{ label, date, daily, cumulative }] — cumulative = null en días futuros.
 */
export function SpendChart({ points, height = 220, currency }) {
  const [ref, width] = useWidth()
  const [hover, setHover] = useState(null)

  const pad = { top: 16, right: 12, bottom: 28, left: 44 }
  const innerW = Math.max(0, width - pad.left - pad.right)
  const innerH = height - pad.top - pad.bottom
  const known = points.filter((p) => p.cumulative != null)
  // Sin gasto todavía: escala redonda (0–1.000) en lugar de fracciones sin sentido
  const yMax = niceMax(Math.max(...known.map((p) => p.cumulative), 0) * 1.1 || 1000)
  const step = points.length > 1 ? innerW / (points.length - 1) : 0
  const x = (i) => pad.left + i * step
  const y = (v) => pad.top + innerH - (v / yMax) * innerH

  const coords = known.map((p) => ({ x: x(points.indexOf(p)), y: y(p.cumulative) }))
  const line = smoothPath(coords)
  const area = coords.length
    ? `${line} L${coords.at(-1).x},${pad.top + innerH} L${coords[0].x},${pad.top + innerH} Z`
    : ''
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * yMax)
  const labelEvery = Math.max(1, Math.ceil(points.length / Math.max(2, Math.floor(innerW / 44))))

  function onMove(e) {
    const rect = e.currentTarget.getBoundingClientRect()
    const i = Math.round((e.clientX - rect.left - pad.left) / (step || 1))
    const idx = Math.max(0, Math.min(points.length - 1, i))
    setHover(points[idx].cumulative != null ? idx : null)
  }

  const hp = hover != null ? points[hover] : null

  return (
    <div ref={ref} className="relative w-full select-none" style={{ height }}>
      {width > 0 && (
        <svg
          width={width}
          height={height}
          role="img"
          aria-label="Gasto acumulado del periodo por día"
          onMouseMove={onMove}
          onMouseLeave={() => setHover(null)}
          className="overflow-visible"
        >
          <defs>
            <linearGradient id="spend-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--color-brand-600)" stopOpacity="0.16" />
              <stop offset="100%" stopColor="var(--color-brand-600)" stopOpacity="0" />
            </linearGradient>
          </defs>

          {ticks.map((t) => (
            <g key={t}>
              <line x1={pad.left} x2={width - pad.right} y1={y(t)} y2={y(t)} stroke="var(--color-line)" strokeDasharray={t === 0 ? '' : '3 4'} />
              <text x={pad.left - 10} y={y(t)} dy="0.32em" textAnchor="end" className="fill-subtle text-[11px] tabular">
                {compact(t)}
              </text>
            </g>
          ))}

          {points.map((p, i) =>
            (i % labelEvery === 0 && points.length - 1 - i >= labelEvery / 2) || i === points.length - 1 ? (
              <text key={p.date} x={x(i)} y={height - 8} textAnchor="middle" className={`text-[11px] tabular ${hover === i ? 'fill-brand-700 font-semibold' : 'fill-subtle'}`}>
                {p.label}
              </text>
            ) : null,
          )}

          {/* Barras finas con el gasto de cada día */}
          {known.map((p) =>
            p.daily > 0 ? (
              <rect
                key={`d-${p.date}`}
                x={x(points.indexOf(p)) - 2}
                width={4}
                y={y(p.daily)}
                height={pad.top + innerH - y(p.daily)}
                rx={2}
                fill="var(--color-brand-200)"
              />
            ) : null,
          )}

          <path d={area} fill="url(#spend-fill)" />
          <path d={line} fill="none" stroke="var(--color-brand-600)" strokeWidth={2.25} strokeLinecap="round" />

          {coords.length > 0 && hover == null && (
            <circle cx={coords.at(-1).x} cy={coords.at(-1).y} r={4} fill="var(--color-canvas)" stroke="var(--color-brand-600)" strokeWidth={2} />
          )}

          {hp && (
            <g>
              <line x1={x(hover)} x2={x(hover)} y1={pad.top} y2={pad.top + innerH} stroke="var(--color-brand-300)" strokeDasharray="3 3" />
              <circle cx={x(hover)} cy={y(hp.cumulative)} r={5} fill="var(--color-brand-600)" stroke="var(--color-canvas)" strokeWidth={2} />
            </g>
          )}
        </svg>
      )}

      {hp && (
        <div
          className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full rounded-control border border-line bg-canvas px-3 py-2 shadow-pop"
          style={{ left: Math.min(Math.max(x(hover), 70), width - 70), top: y(hp.cumulative) - 12 }}
        >
          <p className="text-[11px] text-subtle">{hp.fullLabel}</p>
          <p className="text-sm font-semibold text-ink tabular">{money(hp.cumulative, currency)}</p>
          <p className="text-[11px] text-muted tabular">+{money(hp.daily, currency)} ese día</p>
        </div>
      )}
    </div>
  )
}

/**
 * Barras apiladas por día.
 * days: [{ key, label, isToday, values: { approved, escalated, blocked } }]
 * series: [{ key, label, color }]
 */
export function StackedBars({ days, series, height = 180 }) {
  const totals = days.map((d) => series.reduce((s, se) => s + (d.values[se.key] ?? 0), 0))
  const max = Math.max(...totals, 1)

  return (
    <div className="flex items-end justify-between gap-2 sm:gap-3" style={{ height }}>
      {days.map((d, i) => {
        const total = totals[i]
        return (
          <div key={d.key} className="group relative flex h-full min-w-0 flex-1 flex-col items-center gap-2">
            <div className="relative flex w-full max-w-12 flex-1 flex-col justify-end overflow-hidden rounded-[10px] bg-surface">
              {total > 0 && (
                <div className="flex w-full flex-col-reverse gap-px" style={{ height: `${(total / max) * 100}%` }}>
                  {series.map((se) =>
                    d.values[se.key] ? (
                      <div key={se.key} style={{ flexGrow: d.values[se.key], background: se.color }} className="min-h-1 transition-opacity group-hover:opacity-90" />
                    ) : null,
                  )}
                </div>
              )}
            </div>
            <span className={`text-[11px] font-medium ${d.isToday ? 'text-brand-700' : 'text-subtle'}`}>{d.label}</span>

            {total > 0 && (
              <div
                className={`pointer-events-none absolute bottom-full z-10 mb-1 hidden w-max rounded-control ${
                  i >= days.length - 2 ? 'right-0' : i < 2 ? 'left-0' : 'left-1/2 -translate-x-1/2'
                } border border-line bg-canvas px-3 py-2 text-xs shadow-pop group-hover:block`}
              >
                <p className="mb-1 font-semibold text-ink">{d.fullLabel}</p>
                {series.map((se) => (
                  <p key={se.key} className="flex items-center gap-2 text-muted">
                    <span className="h-2 w-2 rounded-full" style={{ background: se.color }} />
                    {se.label}
                    <span className="ml-auto pl-3 font-medium text-ink tabular">{d.values[se.key] ?? 0}</span>
                  </p>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

/** Barra horizontal de proporciones con leyenda. items: [{ key, label, color, value }] */
export function DistributionBar({ items }) {
  const total = items.reduce((s, it) => s + it.value, 0)
  return (
    <div>
      <div className="flex h-2.5 w-full gap-1 overflow-hidden rounded-full bg-surface">
        {total > 0 &&
          items.map((it) =>
            it.value ? <div key={it.key} className="h-full rounded-full" style={{ flexGrow: it.value, background: it.color }} /> : null,
          )}
      </div>
      <ul className="mt-3 grid grid-cols-[repeat(auto-fit,minmax(84px,1fr))] gap-2">
        {items.map((it) => (
          <li key={it.key} className="min-w-0">
            <p className="flex items-center gap-1.5 text-xs text-muted">
              <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: it.color }} />
              <span className="min-w-0 truncate" title={it.label}>{it.label}</span>
            </p>
            <p className="mt-0.5 text-lg font-semibold text-ink tabular">
              {it.value}
              <span className="ml-1 text-xs font-medium text-subtle">{total ? Math.round((it.value / total) * 100) : 0}%</span>
            </p>
          </li>
        ))}
      </ul>
    </div>
  )
}
