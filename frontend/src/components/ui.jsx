import { useEffect, useState } from 'react'
import { STATUS } from '../format'
import Icon from './icons'

/* ---------- Superficies ---------- */

export function Card({ title, subtitle, action, children, className = '', bodyClassName = '' }) {
  return (
    <section className={`flex flex-col rounded-card border border-line bg-canvas p-5 shadow-card sm:p-6 ${className}`}>
      {(title || action) && (
        <header className="mb-5 flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            {title && <h2 className="text-[15px] font-semibold tracking-[-0.01em] text-ink">{title}</h2>}
            {subtitle && <p className="mt-0.5 max-w-prose text-[13px] leading-relaxed text-muted">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      <div className={`min-w-0 flex-1 ${bodyClassName}`}>{children}</div>
    </section>
  )
}

/** Bloque interior sobre gris claro, para cifras y filas destacadas dentro de una tarjeta. */
export function Tile({ children, className = '' }) {
  return <div className={`rounded-control bg-surface/70 p-4 ring-1 ring-line/70 ring-inset ${className}`}>{children}</div>
}

/** Encabezado de una vista: enlace para volver, antetítulo, título, datos y acciones. */
export function PageHeader({ back, eyebrow, title, meta, actions, children }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
      <div className="min-w-0">
        {back && <BackLink href={back.href}>{back.label}</BackLink>}
        {eyebrow && <Eyebrow className={back ? 'mt-3' : ''}>{eyebrow}</Eyebrow>}
        <h1 className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-2 text-[22px] leading-tight font-semibold tracking-[-0.02em] text-ink sm:text-2xl">
          {title}
        </h1>
        {meta && <div className="mt-1.5 text-[13px] text-muted">{meta}</div>}
        {children}
      </div>
      {actions && <div className="flex flex-wrap items-end gap-2">{actions}</div>}
    </header>
  )
}

export function BackLink({ href, children }) {
  return (
    <a
      href={href}
      className="group -ml-1 inline-flex h-7 items-center gap-1.5 rounded-md px-1 text-[13px] font-medium text-muted transition-colors hover:text-brand-700"
    >
      <Icon name="arrowLeft" size={15} className="transition-transform duration-150 group-hover:-translate-x-0.5" />
      {children}
    </a>
  )
}

/* ---------- Texto y etiquetas ---------- */

export function Eyebrow({ children, className = '' }) {
  return <p className={`text-[11px] font-semibold tracking-[0.08em] text-subtle uppercase ${className}`}>{children}</p>
}

export function StatusBadge({ status, size = 'md' }) {
  const s = STATUS[status] ?? { label: status, className: 'bg-surface text-muted ring-line-strong', icon: null }
  const sizing = size === 'sm' ? 'h-[22px] gap-1 px-1.5 text-[11.5px]' : 'h-6 gap-1.5 px-2 text-xs'
  return (
    <span
      className={`inline-flex items-center rounded-md font-medium whitespace-nowrap ring-1 ring-inset ${sizing} ${s.className}`}
    >
      {s.icon && (
        <Icon
          name={s.icon}
          size={size === 'sm' ? 12 : 13}
          strokeWidth={2.1}
          className={`${s.icon === 'loader' ? 'animate-spin [animation-duration:1.4s]' : ''}`}
        />
      )}
      {s.label}
    </span>
  )
}

/** "Requiere revisión": una marca aparte del estado, en el violeta de la marca. */
export function ReviewFlag({ size = 'md', label = 'Requiere revisión' }) {
  const sizing = size === 'sm' ? 'h-[22px] gap-1 px-1.5 text-[11.5px]' : 'h-6 gap-1.5 px-2 text-xs'
  return (
    <span
      className={`inline-flex items-center rounded-md bg-brand-600 font-medium whitespace-nowrap text-white shadow-brand ${sizing}`}
    >
      <Icon name="flag" size={size === 'sm' ? 11 : 12} strokeWidth={2.2} />
      {label}
    </span>
  )
}

/** Etiqueta compacta de variación / proporción. */
export function Tag({ tone = 'brand', icon, children }) {
  const tones = {
    brand: 'bg-brand-50 text-brand-700 ring-brand-600/20',
    success: 'bg-success-50 text-success-700 ring-success-600/20',
    warning: 'bg-warning-50 text-warning-700 ring-warning-600/25',
    danger: 'bg-danger-50 text-danger-700 ring-danger-600/20',
    neutral: 'bg-surface text-muted ring-line-strong',
  }
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11.5px] font-medium whitespace-nowrap tabular ring-1 ring-inset ${tones[tone]}`}
    >
      {icon && <Icon name={icon} size={12} strokeWidth={2.25} />}
      {children}
    </span>
  )
}

/* ---------- Mensajes del sistema ---------- */

const NOTICE_TONES = {
  danger: { box: 'border-danger-600/20 bg-danger-50 text-danger-700', bar: 'bg-danger-600', icon: 'alert' },
  warning: { box: 'border-warning-600/25 bg-warning-50 text-warning-700', bar: 'bg-warning-600', icon: 'alert' },
  success: { box: 'border-success-600/20 bg-success-50 text-success-700', bar: 'bg-success-600', icon: 'checkCircle' },
  info: { box: 'border-info-600/20 bg-info-50 text-info-700', bar: 'bg-info-600', icon: 'loader' },
  brand: { box: 'border-brand-600/20 bg-brand-50 text-brand-800', bar: 'bg-brand-600', icon: 'flag' },
  slate: { box: 'border-slate-600/20 bg-slate-50 text-slate-700', bar: 'bg-slate-600', icon: 'help' },
}

/** Aviso con una barra de color a la izquierda: mismo formato para errores, avisos y confirmaciones. */
export function Notice({ tone = 'warning', icon, title, children, role, className = '' }) {
  const t = NOTICE_TONES[tone]
  return (
    <div
      role={role}
      className={`relative flex items-start gap-2.5 overflow-hidden rounded-control border py-2.5 pr-3 pl-4 text-[13px] leading-relaxed ${t.box} ${className}`}
    >
      <span aria-hidden="true" className={`absolute inset-y-0 left-0 w-[3px] ${t.bar}`} />
      <Icon name={icon ?? t.icon} size={16} className="mt-[2px]" />
      <div className="min-w-0">
        {title && <span className="font-semibold">{title} </span>}
        {children}
      </div>
    </div>
  )
}

/* ---------- Controles ---------- */

const BUTTON_VARIANTS = {
  primary: 'bg-brand-600 text-white shadow-brand hover:bg-brand-700 active:bg-brand-800',
  secondary:
    'border border-line-strong bg-canvas text-ink shadow-control hover:border-brand-300 hover:bg-brand-25 hover:text-brand-800 active:bg-brand-50',
  ghost: 'text-muted hover:bg-surface hover:text-ink active:bg-surface-strong',
  danger:
    'border border-line-strong bg-canvas text-danger-600 shadow-control hover:border-danger-600/30 hover:bg-danger-50 active:bg-danger-50',
}

export function Button({ variant = 'primary', size = 'md', icon, className = '', children, ...props }) {
  const sizing = size === 'sm' ? 'h-8 gap-1.5 px-3 text-[13px]' : 'h-10 gap-2 px-4 text-sm'
  return (
    <button
      className={`inline-flex items-center justify-center rounded-control font-medium whitespace-nowrap transition-[background-color,border-color,color,transform] duration-150 ease-out select-none active:scale-[0.98] disabled:pointer-events-none disabled:opacity-45 ${sizing} ${BUTTON_VARIANTS[variant]} ${className}`}
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
      className={`inline-flex h-9 w-9 items-center justify-center rounded-control border border-line text-muted transition-colors hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700 ${className}`}
      {...props}
    >
      <Icon name={icon} size={17} />
    </button>
  )
}

/** Control segmentado (pestañas, filtros). options: [{ value, label, count? }] */
export function Segmented({ options, value, onChange, className = '', size = 'md' }) {
  const sizing = size === 'sm' ? 'h-7 px-2.5 text-[12.5px]' : 'h-8 px-3 text-[13px]'
  return (
    <div
      className={`inline-flex max-w-full scrollbar-none items-center gap-0.5 overflow-x-auto rounded-[10px] bg-surface-strong/70 p-[3px] ${className}`}
    >
      {options.map((o) => {
        const active = o.value === value
        return (
          <button
            key={o.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(o.value)}
            className={`inline-flex shrink-0 items-center gap-1.5 rounded-[7px] font-medium whitespace-nowrap transition-colors duration-150 ${sizing} ${
              active ? 'bg-canvas text-ink shadow-control ring-1 ring-line' : 'text-muted hover:bg-canvas/60 hover:text-ink'
            }`}
          >
            {o.label}
            {o.count != null && (
              <span
                className={`min-w-[1.25rem] rounded px-1 text-center tabular text-[11px] ${
                  active ? 'bg-brand-50 text-brand-700' : 'text-subtle'
                }`}
              >
                {o.count}
              </span>
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
      {hint && <span className="mt-1.5 block text-xs leading-relaxed text-subtle">{hint}</span>}
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
        className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow-control transition-transform duration-200 ease-out ${checked ? 'translate-x-5' : ''}`}
      />
    </button>
  )
}

/**
 * Botón de eliminar con confirmación en dos pasos (sin diálogos del navegador).
 * onConfirm debe devolver una promesa; los errores los muestra quien lo usa.
 */
export function ConfirmDelete({ label, warning, onConfirm, className = '' }) {
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!confirming) return
    const onKey = (e) => {
      if (e.key !== 'Escape') return
      e.stopPropagation() // no cerrar también un panel que esté detrás
      setConfirming(false)
    }
    document.addEventListener('keydown', onKey, true)
    return () => document.removeEventListener('keydown', onKey, true)
  }, [confirming])

  async function confirm() {
    setBusy(true)
    try {
      await onConfirm()
    } finally {
      setBusy(false)
      setConfirming(false)
    }
  }

  if (!confirming) {
    return (
      <button
        type="button"
        aria-label={label}
        title={label}
        onClick={() => setConfirming(true)}
        className={`inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-control text-subtle transition-colors hover:bg-danger-50 hover:text-danger-600 ${className}`}
      >
        <Icon name="trash" size={16} />
      </button>
    )
  }

  return (
    <div
      role="group"
      aria-label={label}
      // Cubre toda la fila/tarjeta contenedora (que debe ser `relative`) mientras se confirma
      className={`absolute inset-0 z-10 flex flex-wrap items-center justify-between gap-x-3 gap-y-2 rounded-[inherit] bg-danger-50 px-4 py-2 sm:px-5 ${className}`}
    >
      <span className="min-w-0 text-[13px] font-medium text-danger-700">{warning ?? '¿Eliminar?'}</span>
      <div className="flex gap-1.5">
        <Button variant="ghost" size="sm" disabled={busy} onClick={() => setConfirming(false)} className="!h-7">
          Cancelar
        </Button>
        <button
          type="button"
          autoFocus
          disabled={busy}
          onClick={confirm}
          className="inline-flex h-7 items-center rounded-control bg-danger-600 px-3 text-[13px] font-medium text-white transition-colors hover:bg-danger-700 disabled:opacity-50"
        >
          {busy ? 'Eliminando…' : 'Eliminar'}
        </button>
      </div>
    </div>
  )
}

/* ---------- Estados ---------- */

export function ErrorBox({ message }) {
  if (!message) return null
  return (
    <Notice tone="danger" role="alert">
      {message}
    </Notice>
  )
}

export function Empty({ icon = 'inbox', title, children, action, tone = 'brand' }) {
  const tones = {
    brand: 'bg-brand-50 text-brand-600 ring-brand-600/15',
    success: 'bg-success-50 text-success-600 ring-success-600/15',
    neutral: 'bg-surface text-subtle ring-line',
  }
  return (
    <div className="flex flex-col items-center justify-center px-4 py-12 text-center">
      <span className={`v-cut mb-4 flex h-11 w-11 items-center justify-center rounded-[10px] ring-1 ring-inset ${tones[tone]}`}>
        <Icon name={icon} size={20} />
      </span>
      {title && <p className="text-[15px] font-semibold text-ink">{title}</p>}
      {children && <p className="mt-1 max-w-sm text-[13px] leading-relaxed text-muted">{children}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

export function Loading({ rows = 3 }) {
  return (
    <div className="space-y-2.5 py-2" aria-busy="true" aria-label="Cargando">
      {Array.from({ length: rows }, (_, i) => (
        <div
          key={i}
          className="h-10 animate-pulse rounded-control bg-surface-strong/60"
          style={{ animationDelay: `${i * 90}ms`, opacity: Math.max(0.35, 1 - i * 0.12) }}
        />
      ))}
    </div>
  )
}
