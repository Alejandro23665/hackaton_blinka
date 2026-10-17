import { STATUS } from '../format'
import Icon from './icons'

/* ---------- Superficies ---------- */

export function Card({ title, subtitle, action, children, className = '', bodyClassName = '' }) {
  return (
    <section className={`flex flex-col rounded-card border border-line bg-canvas p-5 shadow-card sm:p-6 ${className}`}>
      {(title || action) && (
        <header className="mb-5 flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            {title && <h2 className="text-[15px] font-semibold tracking-tight text-ink">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-[13px] text-muted">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      <div className={`min-w-0 flex-1 ${bodyClassName}`}>{children}</div>
    </section>
  )
}

/** Bloque interior sobre gris lavanda, para KPIs y filas destacadas dentro de una tarjeta. */
export function Tile({ children, className = '' }) {
  return <div className={`rounded-control bg-surface p-4 ${className}`}>{children}</div>
}

/* ---------- Texto y etiquetas ---------- */

export function Eyebrow({ children, className = '' }) {
  return <p className={`text-xs font-medium uppercase tracking-[0.08em] text-subtle ${className}`}>{children}</p>
}

export function StatusBadge({ status, size = 'md' }) {
  const s = STATUS[status] ?? { label: status, className: 'bg-surface text-muted', dot: 'bg-subtle' }
  const sizing = size === 'sm' ? 'px-2 py-0.5 text-[11px]' : 'px-2.5 py-1 text-xs'
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full font-medium ${sizing} ${s.className}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
      {s.label}
    </span>
  )
}

/** Etiqueta compacta de variación / proporción. */
export function Tag({ tone = 'brand', icon, children }) {
  const tones = {
    brand: 'bg-brand-100 text-brand-800',
    success: 'bg-success-50 text-success-700',
    warning: 'bg-warning-50 text-warning-700',
    danger: 'bg-danger-50 text-danger-700',
    neutral: 'bg-surface text-muted',
  }
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold tabular ${tones[tone]}`}>
      {icon && <Icon name={icon} size={12} strokeWidth={2.25} />}
      {children}
    </span>
  )
}

/* ---------- Controles ---------- */

const BUTTON_VARIANTS = {
  primary: 'bg-brand-600 text-white shadow-control hover:bg-brand-700 active:bg-brand-800',
  secondary: 'border border-line-strong bg-canvas text-ink shadow-control hover:border-brand-300 hover:bg-brand-50 active:bg-brand-100',
  ghost: 'text-muted hover:bg-surface hover:text-ink active:bg-surface-strong',
  danger: 'border border-line-strong bg-canvas text-danger-600 shadow-control hover:border-danger-600/30 hover:bg-danger-50 active:bg-danger-50',
}

export function Button({ variant = 'primary', size = 'md', icon, className = '', children, ...props }) {
  const sizing = size === 'sm' ? 'h-8 gap-1.5 px-3 text-[13px]' : 'h-10 gap-2 px-4 text-sm'
  return (
    <button
      className={`inline-flex items-center justify-center rounded-control font-medium whitespace-nowrap transition-colors duration-150 disabled:pointer-events-none disabled:opacity-45 ${sizing} ${BUTTON_VARIANTS[variant]} ${className}`}
      {...props}
    >
      {icon && <Icon name={icon} size={size === 'sm' ? 15 : 16} />}
      {children}
    </button>
  )
}

export function IconButton({ icon, label, className = '', ...props }) {
  return (
    <button
      aria-label={label}
      title={label}
      className={`inline-flex h-9 w-9 items-center justify-center rounded-full border border-line text-muted transition-colors hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700 ${className}`}
      {...props}
    >
      <Icon name={icon} size={17} />
    </button>
  )
}

/** Control segmentado (pestañas, filtros). options: [{ value, label, count? }] */
export function Segmented({ options, value, onChange, className = '', size = 'md' }) {
  const sizing = size === 'sm' ? 'h-7 px-2.5 text-xs' : 'h-8 px-3 text-[13px]'
  return (
    <div className={`inline-flex max-w-full scrollbar-none items-center gap-0.5 overflow-x-auto rounded-full border border-line bg-surface p-1 ${className}`}>
      {options.map((o) => {
        const active = o.value === value
        return (
          <button
            key={o.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(o.value)}
            className={`inline-flex shrink-0 items-center gap-1.5 rounded-full font-medium whitespace-nowrap transition-colors duration-150 ${sizing} ${
              active ? 'bg-canvas text-brand-700 shadow-control' : 'text-muted hover:text-ink'
            }`}
          >
            {o.label}
            {o.count != null && (
              <span className={`tabular text-[11px] ${active ? 'text-brand-600' : 'text-subtle'}`}>{o.count}</span>
            )}
          </button>
        )
      })}
    </div>
  )
}

export function Field({ label, children, hint }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[13px] font-medium text-ink">{label}</span>
      {children}
      {hint && <span className="mt-1.5 block text-xs text-subtle">{hint}</span>}
    </label>
  )
}

export function Toggle({ checked, onChange, disabled, label }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 shrink-0 rounded-full transition-colors duration-150 disabled:opacity-50 ${checked ? 'bg-brand-600' : 'bg-line-strong'}`}
    >
      <span
        className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow-control transition-transform duration-150 ${checked ? 'translate-x-5' : ''}`}
      />
    </button>
  )
}

/* ---------- Estados ---------- */

export function ErrorBox({ message }) {
  if (!message) return null
  return (
    <p role="alert" className="flex items-start gap-2 rounded-control bg-danger-50 px-3 py-2.5 text-[13px] text-danger-700">
      <Icon name="alert" size={16} className="mt-px" />
      {message}
    </p>
  )
}

export function Empty({ icon = 'inbox', title, children }) {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-10 text-center">
      <span className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-brand-50 text-brand-600">
        <Icon name={icon} size={18} />
      </span>
      {title && <p className="text-sm font-medium text-ink">{title}</p>}
      {children && <p className="mt-1 max-w-xs text-[13px] text-muted">{children}</p>}
    </div>
  )
}

export function Loading({ rows = 3 }) {
  return (
    <div className="space-y-3 py-2" aria-busy="true" aria-label="Cargando">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="h-10 animate-pulse rounded-control bg-surface" />
      ))}
    </div>
  )
}
