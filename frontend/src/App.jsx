import { api } from './api'
import Icon from './components/icons'
import { href, useLoad, useRoute } from './hooks'
import DocumentDetail from './views/DocumentDetail'
import Documents from './views/Documents'
import Upload from './views/Upload'

const TABS = [
  { section: 'subir', label: 'Subir', icon: 'upload' },
  { section: 'documentos', label: 'Documentos', icon: 'file' },
]

function Logo() {
  return (
    <a href={href('subir')} className="flex items-center gap-2.5">
      <span className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-brand-600 text-white shadow-control">
        <Icon name="file" size={18} strokeWidth={2} />
      </span>
      <span className="leading-tight">
        <span className="block text-[15px] font-semibold tracking-tight text-ink">Captura de documentos</span>
        <span className="hidden text-[11px] text-subtle sm:block">Oxxo · guías, controles y facturas</span>
      </span>
    </a>
  )
}

function ApiStatus() {
  const health = useLoad(() => api.health())
  const online = health.data?.status === 'ok'
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full border border-line bg-canvas px-3 py-1.5 text-xs font-medium whitespace-nowrap text-muted"
      title={health.error ?? 'Backend disponible'}
    >
      <span className={`h-2 w-2 rounded-full ${health.loading ? 'bg-line-strong' : online ? 'bg-success-600' : 'bg-danger-600'}`} />
      <span className="hidden sm:inline">{health.loading ? 'Conectando…' : online ? 'API en línea' : 'API sin conexión'}</span>
    </span>
  )
}

function View({ section, id }) {
  if (section === 'documentos') return id ? <DocumentDetail id={id} /> : <Documents />
  return <Upload />
}

export default function App() {
  const { section, id } = useRoute()

  return (
    <div className="min-h-screen bg-surface/40">
      <header className="sticky top-0 z-10 border-b border-line bg-canvas/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
          <Logo />
          <nav aria-label="Secciones" className="flex gap-1 rounded-full border border-line bg-surface p-1">
            {TABS.map((tab) => {
              const active = section === tab.section
              return (
                <a
                  key={tab.section}
                  href={href(tab.section)}
                  aria-current={active ? 'page' : undefined}
                  className={`inline-flex h-9 items-center gap-2 rounded-full px-3 text-sm font-medium transition-colors sm:px-4 ${
                    active ? 'bg-canvas text-brand-700 shadow-control' : 'text-muted hover:text-ink'
                  }`}
                >
                  <Icon name={tab.icon} size={16} className={active ? 'text-brand-600' : ''} />
                  <span className="hidden sm:inline">{tab.label}</span>
                </a>
              )
            })}
          </nav>
          <ApiStatus />
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 pt-6 pb-12 sm:px-6 lg:px-8 lg:pt-8">
        <View section={section} id={id} />
      </main>
    </div>
  )
}
