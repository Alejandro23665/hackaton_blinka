import { useState } from 'react'
import { api } from '../api'
import Icon from '../components/icons'
import { inputClass } from '../components/styles'
import { Button, Card, Empty, ErrorBox, Field, Loading, Toggle } from '../components/ui'
import { shortDate } from '../format'
import { useLoad } from '../hooks'

const MIN_PASSWORD = 8
const EMPTY = { nombre: '', email: '', rol: 'REVISOR', contrasena: '' }

function roleLabel(rol) {
  return rol.charAt(0) + rol.slice(1).toLowerCase()
}

/** Alta de un perfil nuevo: entra activo con la contraseña que se le da. */
function NewProfile({ roles, onCreated }) {
  const [form, setForm] = useState(EMPTY)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })
  const valid = form.nombre.trim() && form.email.includes('@') && form.contrasena.length >= MIN_PASSWORD

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const created = await api.users.create(form)
      setForm(EMPTY)
      onCreated(created)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title="Nuevo perfil" subtitle="Podrá iniciar sesión con este email y contraseña">
      <form onSubmit={submit} className="space-y-4">
        <Field label="Nombre">
          <input className={inputClass} value={form.nombre} onChange={set('nombre')} autoComplete="off" />
        </Field>
        <Field label="Email">
          <input type="email" className={inputClass} value={form.email} onChange={set('email')} autoComplete="off" />
        </Field>
        <Field label="Rol">
          <select className={inputClass} value={form.rol} onChange={set('rol')}>
            {roles.map((rol) => (
              <option key={rol} value={rol}>
                {roleLabel(rol)}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Contraseña" hint={`Mínimo ${MIN_PASSWORD} caracteres. Compártela con la persona por un canal seguro.`}>
          <input
            type="password"
            className={inputClass}
            value={form.contrasena}
            onChange={set('contrasena')}
            autoComplete="new-password"
          />
        </Field>
        <ErrorBox message={error} />
        <Button type="submit" icon="plus" disabled={!valid || busy} className="w-full">
          {busy ? 'Creando…' : 'Crear perfil'}
        </Button>
      </form>
    </Card>
  )
}

/** Una fila: cambiar el rol y activar o desactivar. El propio perfil no se puede cambiar. */
function ProfileRow({ profile, roles, isSelf, onChanged }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function update(change) {
    setBusy(true)
    setError(null)
    try {
      onChanged(await api.users.update(profile.id, change))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <li className={`px-5 py-4 sm:px-6 ${profile.activo ? '' : 'bg-surface/60'}`}>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
        <span
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${
            profile.activo ? 'bg-brand-100 text-brand-700' : 'bg-surface text-subtle'
          }`}
        >
          <Icon name="user" size={17} />
        </span>
        <span className="min-w-0 flex-1">
          <span className={`block truncate text-sm font-medium ${profile.activo ? 'text-ink' : 'text-muted'}`}>
            {profile.nombre}
            {isSelf && <span className="ml-2 text-xs font-normal text-subtle">(tú)</span>}
          </span>
          <span className="block truncate text-xs text-muted">
            {profile.email} · desde {shortDate(profile.creado_en)}
          </span>
        </span>
        <select
          aria-label={`Rol de ${profile.nombre}`}
          className={inputClass.replace('w-full', 'w-40')}
          value={profile.rol}
          disabled={isSelf || busy}
          onChange={(e) => update({ rol: e.target.value })}
        >
          {roles.map((rol) => (
            <option key={rol} value={rol}>
              {roleLabel(rol)}
            </option>
          ))}
        </select>
        <span className="flex w-32 items-center gap-2 text-[13px]">
          <Toggle
            checked={profile.activo}
            disabled={isSelf || busy}
            label={`${profile.activo ? 'Desactivar' : 'Activar'} a ${profile.nombre}`}
            onChange={(activo) => update({ activo })}
          />
          <span className={profile.activo ? 'text-success-700' : 'text-muted'}>{profile.activo ? 'Activo' : 'Desactivado'}</span>
        </span>
      </div>
      {error && <p className="mt-2 text-xs text-danger-700">{error}</p>}
    </li>
  )
}

/** Perfiles (solo administradores): ver los perfiles, cambiar su rol, desactivarlos y crear nuevos. */
export default function Profiles({ user }) {
  const profiles = useLoad(() => api.users.list())
  const roles = useLoad(() => api.users.roles())
  const active = profiles.data?.filter((p) => p.activo).length ?? 0

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,4fr)_minmax(0,8fr)]">
      <div className="lg:sticky lg:top-24 lg:self-start">
        {roles.data && <NewProfile roles={roles.data} onCreated={profiles.reload} />}
      </div>

      <Card
        title="Perfiles"
        subtitle={
          profiles.data
            ? `${profiles.data.length} en total · ${active} activo${active === 1 ? '' : 's'}. Un perfil desactivado no puede iniciar sesión; sus documentos y correcciones se conservan.`
            : undefined
        }
      >
        <ErrorBox message={profiles.error || roles.error} />
        {!profiles.data && profiles.loading && <Loading />}
        {profiles.data?.length === 0 && <Empty icon="user" title="Aún no hay perfiles" />}
        {profiles.data?.length > 0 && roles.data && (
          <ul className="-mx-5 divide-y divide-line sm:-mx-6">
            {profiles.data.map((profile) => (
              <ProfileRow
                key={profile.id}
                profile={profile}
                roles={roles.data}
                isSelf={profile.id === user.id}
                onChanged={profiles.reload}
              />
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
