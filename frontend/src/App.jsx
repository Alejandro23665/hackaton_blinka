import { useCallback, useState } from 'react'
import { api } from './api'
import Icon from './components/icons'
import InvoiceDetail from './components/InvoiceDetail'
import { useLoad } from './hooks'
import Dashboard from './views/Dashboard'
import Invoices from './views/Invoices'
import Policies from './views/Policies'
import Registry from './views/Registry'
import Vendors from './views/Vendors'

const TABS = [
  { id: 'dashboard', label: 'Panel', icon: 'grid', View: Dashboard },
  { id: 'invoices', label: 'Facturas', icon: 'file', View: Invoices },
  { id: 'vendors', label: 'Proveedores', icon: 'store', View: Vendors },
  { id: 'policies', label: 'Políticas', icon: 'shield', View: Policies },
  { id: 'registry', label: 'Registro', icon: 'list', View: Registry },
]

function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-600 text-white shadow-control">
        <Icon name="bot" size={19} strokeWidth={2} />
      </span>
      <div className="leading-tight">
        <p className="text-[17px] font-semibold tracking-tight text-ink">blinka</p>
        <p className="hidden text-[11px] whitespace-nowrap text-subtle sm:block">Agente de pagos</p>
      </div>
    </div>
  )
}

/** Estado real del backend y política activa (lo que gobierna al agente). */
function SystemStatus({ version }) {
  const health = useLoad(() => api.health(), version)
  const policy = useLoad(() => api.policies.active().catch(() => null), version)
  const online = health.data?.status === 'ok'

  return (
    <div className="flex items-center gap-2">
      {policy.data && (
        <span className="hidden items-center gap-1.5 rounded-full border border-line bg-canvas px-3 py-1.5 text-xs font-medium text-muted md:inline-flex">
          <Icon name="shield" size={14} className="text-brand-600" />
          <span className="max-w-40 truncate">{policy.data.name}</span>
        </span>
      )}
      <span
        className="inline-flex items-center gap-1.5 rounded-full border border-line bg-canvas px-3 py-1.5 text-xs font-medium whitespace-nowrap text-muted"
        title={health.error ?? 'Backend disponible'}
      >
        <span className={`h-2 w-2 rounded-full ${health.loading ? 'bg-line-strong' : online ? 'bg-success-600' : 'bg-danger-600'}`} />
        <span className="hidden sm:inline">{health.loading ? 'Conectando…' : online ? 'API en línea' : 'API sin conexión'}</span>
      </span>
    </div>
  )
}

function Nav({ tab, setTab, className = '', compact = false }) {
  return (
    <nav
      aria-label="Secciones"
      className={`gap-1 border border-line bg-surface p-1 ${compact ? 'grid grid-cols-5 rounded-[16px] sm:flex sm:rounded-full' : 'flex rounded-full'} ${className}`}
    >
      {TABS.map((t) => {
        const active = tab === t.id
        return (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            aria-current={active ? 'page' : undefined}
            className={`inline-flex shrink-0 items-center justify-center font-medium transition-colors duration-150 ${
              compact ? 'h-12 flex-col gap-0.5 rounded-[12px] px-1 text-[11px] sm:h-9 sm:flex-1 sm:flex-row sm:gap-2 sm:rounded-full sm:text-sm' : 'h-9 gap-2 rounded-full px-4 text-sm'
            } ${
              active ? 'bg-canvas text-brand-700 shadow-control' : 'text-muted hover:text-ink'
            }`}
          >
            <Icon name={t.icon} size={16} className={active ? 'text-brand-600' : ''} />
            {t.label}
          </button>
        )
      })}
    </nav>
  )
}

export default function App() {
  const [tab, setTab] = useState('dashboard')
  const [openInvoiceId, setOpenInvoiceId] = useState(null)
  // Se incrementa cuando algo cambia, para que las vistas recarguen sus datos
  const [version, setVersion] = useState(0)
  const bump = () => setVersion((v) => v + 1)
  const closeInvoice = useCallback(() => setOpenInvoiceId(null), [])

  const { View, label } = TABS.find((t) => t.id === tab)

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-line bg-canvas/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
          <Logo />
          <Nav tab={tab} setTab={setTab} className="hidden xl:flex" />
          <SystemStatus version={version} />
        </div>
        <div className="px-4 pb-3 sm:px-6 xl:hidden">
          <Nav tab={tab} setTab={setTab} compact className="w-full" />
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 pt-6 pb-12 sm:px-6 lg:px-8 lg:pt-8">
        <h1 className="sr-only">{label}</h1>
        <View version={version} onChange={bump} openInvoice={setOpenInvoiceId} />
      </main>

      {openInvoiceId && (
        <InvoiceDetail invoiceId={openInvoiceId} onClose={closeInvoice} onChange={bump} />
      )}
    </div>
  )
}
