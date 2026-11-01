import { href } from '../hooks'
import { Logo } from './Brand'
import Icon from './icons'

/** Cabecera de las páginas públicas (sin sesión): marca, navegación propia de cada página y accesos. */
export function PublicHeader({ nav, cta = true }) {
  return (
    <header className="sticky top-0 z-30 border-b border-line/80 bg-canvas/85 pt-[env(safe-area-inset-top)] backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-[1200px] items-center justify-between gap-6 px-5 sm:px-8">
        <a href={href('')} aria-label="Veriq, página principal" className="flex h-10 items-center rounded-control">
          <Logo height={21} />
        </a>
        {nav && (
          <nav aria-label="Secciones" className="hidden items-center gap-1 lg:flex">
            {nav}
          </nav>
        )}
        <div className="flex items-center gap-1 sm:gap-2">
          {/* Quien ya tiene perfil sigue entrando desde aquí */}
          <a
            href={href('entrar')}
            aria-label="Iniciar sesión"
            title="Iniciar sesión"
            className="inline-flex h-10 items-center gap-2 rounded-control px-2.5 text-sm font-medium text-muted transition-colors hover:bg-surface hover:text-ink sm:px-3"
          >
            <Icon name="user" size={18} className="sm:hidden" />
            <span className="hidden sm:inline">Iniciar sesión</span>
          </a>
          {cta && (
            <a
              href={href('cita')}
              className="inline-flex h-10 items-center gap-2 rounded-control bg-brand-600 px-4 text-sm font-medium text-white shadow-brand transition-[background-color,transform] duration-150 ease-out hover:bg-brand-700 active:scale-[0.97]"
            >
              Agendar una cita
              <Icon name="calendar" size={16} className="hidden sm:block" />
            </a>
          )}
        </div>
      </div>
    </header>
  )
}

/** Enlace de la navegación pública con el mismo aspecto que los botones de sección. */
export const publicNavClass =
  'inline-flex h-9 items-center rounded-control px-3 text-sm font-medium text-muted transition-colors hover:bg-surface hover:text-ink aria-[current=page]:text-brand-700'

const FOOTER_LINKS = [
  ['', 'Inicio'],
  ['nosotros', 'Sobre nosotros'],
  ['cita', 'Agendar una cita'],
  ['entrar', 'Iniciar sesión'],
]

export function PublicFooter() {
  return (
    <footer className="border-t border-line bg-canvas pb-[env(safe-area-inset-bottom)]">
      <div className="mx-auto flex max-w-[1200px] flex-col gap-6 px-5 py-10 sm:px-8 md:flex-row md:items-center md:justify-between">
        <div>
          <Logo height={18} />
          <p className="mt-3 text-[13px] text-subtle">Lee, procesa y verifica documentos comerciales con IA.</p>
        </div>
        <nav aria-label="Enlaces" className="flex flex-wrap gap-x-6 gap-y-2 text-[13px] font-medium">
          {FOOTER_LINKS.map(([section, label]) => (
            <a key={label} href={href(section)} className="text-muted underline-offset-2 hover:text-brand-700 hover:underline">
              {label}
            </a>
          ))}
        </nav>
      </div>
    </footer>
  )
}
