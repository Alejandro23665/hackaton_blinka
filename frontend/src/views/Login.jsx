import { useState } from 'react'
import { api, setToken } from '../api'
import { Logo, VeriqSymbol } from '../components/Brand'
import { inputClass } from '../components/styles'
import { Button, ErrorBox, Field, Notice } from '../components/ui'
import { href } from '../hooks'

const STEPS = [
  ['Clasifica', 'Separa las páginas y reconoce cada tipo de documento.'],
  ['Lee dos veces', 'Dos lecturas independientes: si no coinciden, el dato se marca.'],
  ['Verifica', 'Comprueba los datos obligatorios y los importes antes de guardar.'],
]

/** Panel de marca (escritorio): qué hace el producto, sobre el morado oscuro. */
function BrandPanel() {
  return (
    <aside className="relative hidden overflow-hidden bg-brand-950 text-white lg:flex lg:flex-col lg:justify-between lg:p-12 xl:p-14">
      <div aria-hidden="true" className="v-hatch absolute inset-0" />
      <div
        aria-hidden="true"
        className="absolute -right-24 -bottom-40 h-[520px] w-[520px] rounded-full bg-brand-600/25 blur-3xl"
      />

      <a
        href={href('')}
        aria-label="Veriq, página principal"
        className="relative inline-flex h-14 w-14 items-center justify-center rounded-[14px] bg-white shadow-pop"
      >
        <VeriqSymbol height={20} />
      </a>

      <div className="relative max-w-md">
        <h2 className="text-[34px] leading-[1.1] font-semibold tracking-[-0.03em] text-balance">
          Cada documento, leído y verificado.
        </h2>
        <p className="mt-4 text-[15px] leading-relaxed text-white/70">
          Veriq procesa facturas y documentos comerciales con IA, y solo te pide revisar lo que de verdad lo necesita.
        </p>
        <ol className="mt-10 space-y-5">
          {STEPS.map(([title, text], i) => (
            <li key={title} className="flex gap-4">
              <span className="mt-0.5 font-mono text-xs text-brand-300 tabular">0{i + 1}</span>
              <span>
                <span className="block text-sm font-semibold">{title}</span>
                <span className="block text-sm text-white/60">{text}</span>
              </span>
            </li>
          ))}
        </ol>
      </div>

      <p className="relative text-xs text-white/45">Veriq · verificación documental con IA</p>
    </aside>
  )
}

/** Inicio de sesión con email y contraseña (tabla usuarios). */
export default function Login({ onLogin, expired }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function submit(e) {
    e.preventDefault()
    if (!email.trim() || !password) {
      setError('Escribe tu email y tu contraseña.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const { token, usuario } = await api.auth.login(email, password)
      setToken(token)
      onLogin(usuario)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid min-h-dvh bg-canvas lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <BrandPanel />

      <main className="flex flex-col px-5 pt-[max(2rem,env(safe-area-inset-top))] pb-8 sm:px-10">
        <a href={href('')} aria-label="Veriq, página principal" className="self-start rounded-control lg:hidden">
          <Logo height={24} />
        </a>
        <div className="flex flex-1 items-center justify-center py-10">
          <form onSubmit={submit} noValidate className="w-full max-w-[380px] animate-enter">
            <h1 className="text-[26px] leading-tight font-semibold tracking-[-0.02em] text-ink">Inicia sesión</h1>
            <p className="mt-1.5 mb-8 text-sm text-muted">Entra con el email y la contraseña de tu perfil.</p>

            {expired && !error && (
              <Notice tone="warning" icon="clock" className="mb-5">
                Tu sesión terminó. Vuelve a iniciar sesión.
              </Notice>
            )}

            <div className="space-y-4">
              <Field label="Email">
                <input
                  type="email"
                  autoComplete="username"
                  autoFocus
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value)
                    setError(null)
                  }}
                  className={`${inputClass} h-11 text-base sm:text-sm`}
                />
              </Field>
              <Field label="Contraseña">
                <input
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value)
                    setError(null)
                  }}
                  className={`${inputClass} h-11 text-base sm:text-sm`}
                />
              </Field>
              <ErrorBox message={error} />
              <Button type="submit" className="!h-11 w-full" disabled={busy}>
                {busy ? 'Entrando…' : 'Iniciar sesión'}
              </Button>
            </div>
            <p className="mt-6 text-xs leading-relaxed text-subtle">
              ¿Sin acceso? Pide a un administrador que cree o reactive tu perfil.
            </p>
          </form>
        </div>
      </main>
    </div>
  )
}
