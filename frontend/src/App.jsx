import { useEffect, useState } from 'react'
import { SESSION_EXPIRED, api, getToken, setToken } from './api'
import Icon from './components/icons'
import { Loading } from './components/ui'
import { href, useLoad, useRoute } from './hooks'
import Correct from './views/Correct'
import DocumentDetail from './views/DocumentDetail'
import Documents from './views/Documents'
import Home from './views/Home'
import Login from './views/Login'
import Review from './views/Review'
import Upload from './views/Upload'

const TABS = [
  { section: 'inicio', label: 'Inicio', icon: 'grid' },
  { section: 'subir', label: 'Subir', icon: 'upload' },
  { section: 'revision', label: 'Revisión', icon: 'alert' },
  { section: 'documentos', label: 'Documentos', icon: 'file' },
]

function Logo() {
  return (
    <a href={href('inicio')} className="flex items-center gap-2.5">
      <span className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-brand-600 text-white shadow-control">
        <Icon name="file" size={18} strokeWidth={2} />
      </span>
      <span className="hidden leading-tight md:block">
        <span className="block text-[15px] font-semibold tracking-tight text-ink">Captura de documentos</span>
        <span className="block text-[11px] text-subtle">Oxxo · guías, controles y facturas</span>
      </span>
    </a>
  )
}

function UserMenu({ user, onLogout }) {
  return (
    <span className="flex items-center gap-2">
      <span className="hidden text-right leading-tight lg:block">
        <span className="block text-[13px] font-medium text-ink">{user.nombre}</span>
        <span className="block text-[11px] text-subtle">{user.rol.toLowerCase()}</span>
      </span>
      <button
        type="button"
        onClick={onLogout}
        title="Cerrar sesión"
        className="inline-flex h-9 items-center gap-1.5 rounded-full border border-line px-3 text-[13px] font-medium text-muted transition-colors hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700"
      >
        <Icon name="user" size={15} />
        Salir
      </button>
    </span>
  )
}

function View({ section, id }) {
  if (section === 'documentos') return id ? <DocumentDetail id={id} /> : <Documents />
  if (section === 'revision') return id ? <Correct id={id} /> : <Review />
  if (section === 'subir') return <Upload />
  return <Home />
}

export default function App() {
  const { section, id } = useRoute()
  // undefined: aún no se sabe (se usa la sesión guardada); null: sin sesión
  const [loggedUser, setUser] = useState(undefined)
  const [expired, setExpired] = useState(false)
  // Si ya había una sesión guardada, se comprueba que siga siendo válida
  const me = useLoad(() => (getToken() ? api.auth.me() : Promise.resolve(null)))
  const user = loggedUser === undefined ? me.data : loggedUser

  useEffect(() => {
    const onExpired = () => {
      setUser(null)
      setExpired(true)
    }
    window.addEventListener(SESSION_EXPIRED, onExpired)
    return () => window.removeEventListener(SESSION_EXPIRED, onExpired)
  }, [])

  function logout() {
    setToken(null)
    setUser(null)
    setExpired(false)
  }

  if (!user) {
    if (me.loading && getToken()) {
      return (
        <div className="mx-auto max-w-md px-4 pt-24">
          <Loading rows={2} />
        </div>
      )
    }
    return (
      <Login
        expired={expired}
        onLogin={(usuario) => {
          setUser(usuario)
          setExpired(false)
        }}
      />
    )
  }

  return (
    <div className="min-h-screen bg-surface/40">
      <header className="sticky top-0 z-10 border-b border-line bg-canvas/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-3 sm:px-6 lg:px-8">
          <Logo />
          <nav aria-label="Secciones" className="flex gap-1 rounded-full border border-line bg-surface p-1">
            {TABS.map((tab) => {
              const active = section === tab.section || (tab.section === 'inicio' && !TABS.some((t) => t.section === section))
              return (
                <a
                  key={tab.section}
                  href={href(tab.section)}
                  aria-current={active ? 'page' : undefined}
                  title={tab.label}
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
          <UserMenu user={user} onLogout={logout} />
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 pt-6 pb-12 sm:px-6 lg:px-8 lg:pt-8">
        <View section={section} id={id} />
      </main>
    </div>
  )
}
