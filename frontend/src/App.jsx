import { useEffect, useState } from 'react'
import { SESSION_EXPIRED, api, getToken, setToken } from './api'
import { Logo } from './components/Brand'
import Icon from './components/icons'
import { Loading } from './components/ui'
import { href, useLoad, useRoute } from './hooks'
import About from './views/About'
import Appointment from './views/Appointment'
import Appointments from './views/Appointments'
import Correct from './views/Correct'
import DocumentDetail from './views/DocumentDetail'
import Documents from './views/Documents'
import Home from './views/Home'
import Landing from './views/Landing'
import Login from './views/Login'
import Metrics from './views/Metrics'
import Profiles from './views/Profiles'
import Review from './views/Review'
import Upload from './views/Upload'

const TABS = [
  { section: 'inicio', label: 'Inicio', icon: 'home', group: 'Operación' },
  { section: 'subir', label: 'Subir', icon: 'upload', group: 'Operación' },
  { section: 'revision', label: 'Revisión', icon: 'scan', group: 'Operación' },
  { section: 'documentos', label: 'Documentos', icon: 'file', group: 'Operación' },
  { section: 'metricas', label: 'Métricas', icon: 'chart', group: 'Análisis' },
  { section: 'perfiles', label: 'Perfiles', icon: 'users', group: 'Administración', admin: true },
  { section: 'citas', label: 'Citas', icon: 'calendar', group: 'Administración', admin: true },
]

const ADMIN_ROLE = 'ADMINISTRADOR'

function initials(name) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0].toUpperCase())
    .join('')
}

function Avatar({ user }) {
  return (
    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-950 text-[12px] font-semibold text-white">
      {initials(user.nombre)}
    </span>
  )
}

/** Barra lateral (escritorio): secciones agrupadas y la sesión abajo. */
function Sidebar({ tabs, isActive, user, onLogout }) {
  const groups = [...new Set(tabs.map((tab) => tab.group))]
  return (
    <aside className="fixed inset-y-0 left-0 z-20 hidden w-[248px] flex-col border-r border-line bg-canvas lg:flex">
      <a href={href('inicio')} className="mx-3 mt-4 mb-6 flex h-11 items-center rounded-control px-3" aria-label="Veriq, inicio">
        <Logo height={22} />
      </a>

      <nav aria-label="Secciones" className="flex-1 space-y-6 overflow-y-auto px-3">
        {groups.map((group) => (
          <div key={group}>
            <p className="mb-1.5 px-3 text-[11px] font-semibold tracking-[0.08em] text-subtle uppercase">{group}</p>
            <ul className="space-y-0.5">
              {tabs
                .filter((tab) => tab.group === group)
                .map((tab) => {
                  const active = isActive(tab)
                  return (
                    <li key={tab.section}>
                      <a
                        href={href(tab.section)}
                        aria-current={active ? 'page' : undefined}
                        className={`relative flex h-9 items-center gap-3 rounded-control px-3 text-sm font-medium transition-colors duration-150 ${
                          active ? 'bg-brand-50 text-brand-800' : 'text-muted hover:bg-surface hover:text-ink'
                        }`}
                      >
                        {active && (
                          <span aria-hidden="true" className="absolute top-2 bottom-2 -left-3 w-[3px] rounded-r-full bg-brand-600" />
                        )}
                        <Icon name={tab.icon} size={18} className={active ? 'text-brand-600' : 'text-subtle'} />
                        {tab.label}
                      </a>
                    </li>
                  )
                })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="m-3 flex items-center gap-3 rounded-card border border-line bg-surface/60 p-2.5 pl-3">
        <Avatar user={user} />
        <span className="min-w-0 flex-1 leading-tight">
          <span className="block truncate text-[13px] font-medium text-ink">{user.nombre}</span>
          <span className="block truncate text-[11.5px] text-subtle first-letter:uppercase">{user.rol.toLowerCase()}</span>
        </span>
        <button
          type="button"
          onClick={onLogout}
          title="Cerrar sesión"
          aria-label="Cerrar sesión"
          className="inline-flex h-8 w-8 items-center justify-center rounded-control text-muted transition-colors hover:bg-canvas hover:text-danger-600"
        >
          <Icon name="logout" size={17} />
        </button>
      </div>
    </aside>
  )
}

/** Móvil y tableta: barra superior con la marca y la sesión. */
function TopBar({ user, onLogout }) {
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-canvas/90 pt-[env(safe-area-inset-top)] backdrop-blur-md lg:hidden">
      <div className="flex h-14 items-center justify-between gap-3 px-4 sm:px-6">
        <a href={href('inicio')} aria-label="Veriq, inicio" className="flex h-10 items-center rounded-control">
          <Logo height={20} />
        </a>
        <span className="flex items-center gap-2">
          <span className="hidden text-right leading-tight sm:block">
            <span className="block text-[13px] font-medium text-ink">{user.nombre}</span>
            <span className="block text-[11px] text-subtle first-letter:uppercase">{user.rol.toLowerCase()}</span>
          </span>
          <Avatar user={user} />
          <button
            type="button"
            onClick={onLogout}
            title="Cerrar sesión"
            aria-label="Cerrar sesión"
            className="inline-flex h-10 w-10 items-center justify-center rounded-control text-muted transition-colors hover:bg-surface hover:text-danger-600"
          >
            <Icon name="logout" size={18} />
          </button>
        </span>
      </div>
    </header>
  )
}

/** Móvil y tableta: pestañas abajo, al alcance del pulgar. */
function TabBar({ tabs, isActive }) {
  return (
    <nav
      aria-label="Secciones"
      className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-canvas/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-md lg:hidden"
    >
      <ul className="mx-auto grid max-w-xl" style={{ gridTemplateColumns: `repeat(${tabs.length}, minmax(0, 1fr))` }}>
        {tabs.map((tab) => {
          const active = isActive(tab)
          return (
            <li key={tab.section}>
              <a
                href={href(tab.section)}
                aria-current={active ? 'page' : undefined}
                className={`relative flex h-[58px] flex-col items-center justify-center gap-1 text-[10.5px] font-medium transition-colors select-none ${
                  active ? 'text-brand-700' : 'text-subtle active:text-ink'
                }`}
              >
                {active && <span aria-hidden="true" className="absolute top-0 h-[2px] w-8 rounded-b-full bg-brand-600" />}
                <Icon name={tab.icon} size={21} strokeWidth={active ? 2 : 1.75} />
                <span className="max-w-full truncate px-0.5">{tab.label}</span>
              </a>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}

function View({ section, id, user }) {
  if (section === 'perfiles' && user.rol === ADMIN_ROLE) return <Profiles user={user} />
  if (section === 'citas' && user.rol === ADMIN_ROLE) return <Appointments />
  if (section === 'documentos') return id ? <DocumentDetail id={id} /> : <Documents />
  if (section === 'revision') return id ? <Correct id={id} /> : <Review />
  if (section === 'subir') return <Upload />
  if (section === 'metricas') return <Metrics />
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
        <div className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center gap-6 px-4">
          <Logo height={24} className="self-center" />
          <Loading rows={2} />
        </div>
      )
    }
    // La raíz muestra la página pública; un enlace directo (#/revision/12…) o una sesión vencida van
    // directo al inicio de sesión
    const atRoot = ['', '#', '#/'].includes(window.location.hash)
    if (atRoot && !expired) return <Landing />
    // El formulario para agendar una cita es público
    if (section === 'cita') return <Appointment />
    if (section === 'nosotros') return <About />
    return (
      <Login
        expired={expired}
        onLogin={(usuario) => {
          setUser(usuario)
          setExpired(false)
          // Desde la página pública se entra al inicio de la aplicación
          if (section === 'entrar') window.location.hash = href('inicio')
        }}
      />
    )
  }

  // Perfiles solo la ve un administrador
  const tabs = TABS.filter((tab) => !tab.admin || user.rol === ADMIN_ROLE)
  const isActive = (tab) => section === tab.section || (tab.section === 'inicio' && !tabs.some((t) => t.section === section))

  return (
    <div className="min-h-dvh lg:pl-[248px]">
      <a
        href="#contenido"
        onClick={(e) => {
          // Sin cambiar el hash (las rutas viven en él): solo se lleva el foco al contenido
          e.preventDefault()
          document.getElementById('contenido')?.focus()
        }}
        className="sr-only z-50 rounded-control bg-canvas px-3 py-2 text-sm font-medium text-brand-700 shadow-pop focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Ir al contenido
      </a>
      <Sidebar tabs={tabs} isActive={isActive} user={user} onLogout={logout} />
      <TopBar user={user} onLogout={logout} />

      <main
        id="contenido"
        tabIndex={-1}
        className="mx-auto max-w-[1320px] px-4 pt-5 pb-[calc(88px+env(safe-area-inset-bottom))] outline-none sm:px-6 lg:px-10 lg:pt-9 lg:pb-14"
      >
        {/* Cambiar de vista la hace entrar con un leve desplazamiento (no entre documentos de una misma vista) */}
        <div key={`${section}/${id ? 'detalle' : 'lista'}`} className="animate-enter">
          <View section={section} id={id} user={user} />
        </div>
      </main>

      <TabBar tabs={tabs} isActive={isActive} />
    </div>
  )
}
