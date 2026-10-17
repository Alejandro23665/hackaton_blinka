import { useState } from 'react'
import InvoiceDetail from './components/InvoiceDetail'
import Dashboard from './views/Dashboard'
import Invoices from './views/Invoices'
import Policies from './views/Policies'
import Vendors from './views/Vendors'

const TABS = [
  { id: 'dashboard', label: 'Panel', View: Dashboard },
  { id: 'invoices', label: 'Facturas', View: Invoices },
  { id: 'vendors', label: 'Proveedores', View: Vendors },
  { id: 'policies', label: 'Políticas', View: Policies },
]

export default function App() {
  const [tab, setTab] = useState('dashboard')
  const [openInvoiceId, setOpenInvoiceId] = useState(null)
  // Se incrementa cuando algo cambia, para que las vistas recarguen sus datos
  const [version, setVersion] = useState(0)
  const bump = () => setVersion((v) => v + 1)

  const { View } = TABS.find((t) => t.id === tab)

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-8 gap-y-2 px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">B</span>
            <div>
              <p className="font-semibold leading-tight text-slate-900">Blinka</p>
              <p className="text-xs leading-tight text-slate-500">Agente de pago de facturas</p>
            </div>
          </div>
          <nav className="flex gap-1">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`rounded-lg px-3 py-2 text-sm font-medium transition ${
                  tab === t.id ? 'bg-indigo-50 text-indigo-700' : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                {t.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6">
        <View version={version} onChange={bump} openInvoice={setOpenInvoiceId} />
      </main>

      {openInvoiceId && (
        <InvoiceDetail invoiceId={openInvoiceId} onClose={() => setOpenInvoiceId(null)} onChange={bump} />
      )}
    </div>
  )
}
