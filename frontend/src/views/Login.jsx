import { useState } from 'react'
import { api, setToken } from '../api'
import Icon from '../components/icons'
import { inputClass } from '../components/styles'
import { Button, ErrorBox, Field } from '../components/ui'

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
    <div className="flex min-h-screen items-center justify-center bg-surface/40 px-4">
      <form
        onSubmit={submit}
        noValidate
        className="w-full max-w-sm rounded-card border border-line bg-canvas p-6 shadow-card sm:p-8"
      >
        <span className="mb-4 flex h-11 w-11 items-center justify-center rounded-[12px] bg-brand-600 text-white shadow-control">
          <Icon name="file" size={20} strokeWidth={2} />
        </span>
        <h1 className="text-lg font-semibold tracking-tight text-ink">Captura de documentos</h1>
        <p className="mt-1 mb-6 text-[13px] text-muted">Oxxo · inicia sesión para continuar</p>

        {expired && !error && (
          <p className="mb-4 rounded-control bg-warning-50 px-3 py-2.5 text-[13px] text-warning-700">
            Tu sesión terminó. Vuelve a iniciar sesión.
          </p>
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
              className={inputClass}
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
              className={inputClass}
            />
          </Field>
          <ErrorBox message={error} />
          <Button type="submit" className="w-full" disabled={busy}>
            {busy ? 'Entrando…' : 'Iniciar sesión'}
          </Button>
        </div>
      </form>
    </div>
  )
}
