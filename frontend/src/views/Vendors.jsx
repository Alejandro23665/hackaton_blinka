import { useState } from 'react'
import { api } from '../api'
import { Button, Card, Empty, ErrorBox, inputClass, Loading } from '../components/ui'
import { shortDate } from '../format'
import { useLoad } from '../hooks'

function Toggle({ checked, onChange, disabled }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 shrink-0 rounded-full transition disabled:opacity-50 ${checked ? 'bg-emerald-500' : 'bg-slate-300'}`}
    >
      <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition ${checked ? 'left-5.5' : 'left-0.5'}`} />
    </button>
  )
}

export default function Vendors({ version, onChange }) {
  const vendors = useLoad(() => api.vendors.list(), version)
  const [name, setName] = useState('')
  const [error, setError] = useState(null)
  const [busyId, setBusyId] = useState(null)

  async function create(e) {
    e.preventDefault()
    if (!name.trim()) {
      setError('Escribe el nombre del proveedor')
      return
    }
    try {
      await api.vendors.create({ name: name.trim(), is_allowed: true })
      setName('')
      onChange()
    } catch (err) {
      setError(err.message)
    }
  }

  async function toggle(vendor, isAllowed) {
    setBusyId(vendor.id)
    try {
      await api.vendors.update(vendor.id, { is_allowed: isAllowed })
      onChange()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  return (
    <Card title="Proveedores" className="mx-auto max-w-3xl">
      <form className="mb-4 flex gap-2" onSubmit={create}>
        <input
          className={inputClass}
          placeholder="Nombre del nuevo proveedor"
          value={name}
          onChange={(e) => {
            setName(e.target.value)
            setError(null)
          }}
        />
        <Button type="submit" className="shrink-0">Añadir</Button>
      </form>
      <ErrorBox message={error ?? vendors.error} />

      {vendors.loading && !vendors.data && <Loading />}
      {vendors.data?.length === 0 && <Empty>Aún no hay proveedores.</Empty>}
      <ul className="divide-y divide-slate-100">
        {vendors.data?.map((v) => (
          <li key={v.id} className="flex items-center justify-between gap-4 py-3">
            <div>
              <p className="font-medium text-slate-900">{v.name}</p>
              <p className="text-xs text-slate-500">Desde {shortDate(v.created_at)}</p>
            </div>
            <div className="flex items-center gap-3">
              <span className={`text-sm ${v.is_allowed ? 'text-emerald-700' : 'text-rose-600'}`}>
                {v.is_allowed ? 'Autorizado' : 'Bloqueado'}
              </span>
              <Toggle checked={v.is_allowed} disabled={busyId === v.id} onChange={(val) => toggle(v, val)} />
            </div>
          </li>
        ))}
      </ul>
    </Card>
  )
}
