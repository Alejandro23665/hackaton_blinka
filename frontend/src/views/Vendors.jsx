import { useState } from 'react'
import { api } from '../api'
import { Button, Card, Empty, ErrorBox, Loading, Tag, Toggle } from '../components/ui'
import { shortDate } from '../format'
import { inputClass } from '../components/styles'
import { useLoad } from '../hooks'

export default function Vendors({ version, onChange }) {
  const vendors = useLoad(() => api.vendors.list(), version)
  const [name, setName] = useState('')
  const [error, setError] = useState(null)
  const [busyId, setBusyId] = useState(null)

  const list = vendors.data ?? []
  const allowed = list.filter((v) => v.is_allowed).length
  const pending = list.filter((v) => v.needs_review).length

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
    setError(null)
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
    <div className="mx-auto max-w-3xl">
      <Card
        title="Proveedores"
        subtitle="Los no autorizados se bloquean; los nuevos que el agente detecta en facturas esperan tu aprobación"
        action={
          vendors.data && (
            <div className="flex flex-wrap gap-2">
              {pending > 0 && <Tag tone="warning">{pending} por aprobar</Tag>}
              <Tag tone="brand">{allowed} de {list.length} autorizados</Tag>
            </div>
          )
        }
      >
        <form className="mb-5 flex flex-col gap-2 sm:flex-row" onSubmit={create} noValidate>
          <label htmlFor="vendor-name" className="sr-only">Nombre del proveedor</label>
          <input
            id="vendor-name"
            className={inputClass}
            placeholder="Nombre del nuevo proveedor"
            value={name}
            onChange={(e) => {
              setName(e.target.value)
              setError(null)
            }}
          />
          <Button type="submit" icon="plus" className="shrink-0">Añadir proveedor</Button>
        </form>
        <div className="mb-4">
          <ErrorBox message={error ?? vendors.error} />
        </div>

        {vendors.loading && !vendors.data && <Loading rows={4} />}
        {vendors.data?.length === 0 && <Empty icon="store" title="Aún no hay proveedores">Añade el primero con el formulario.</Empty>}

        <ul className="divide-y divide-line rounded-card border border-line">
          {list.map((v) => (
            <li key={v.id} className="flex items-center justify-between gap-4 px-4 py-3.5 sm:px-5">
              <div className="flex min-w-0 items-center gap-3">
                <span
                  className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${
                    v.is_allowed ? 'bg-brand-100 text-brand-800' : 'bg-surface-strong text-subtle'
                  }`}
                >
                  {v.name.slice(0, 1).toUpperCase()}
                </span>
                <div className="min-w-0">
                  <p className={`flex items-center gap-2 text-sm font-medium ${v.is_allowed ? 'text-ink' : 'text-muted'}`}>
                    <span className="truncate">{v.name}</span>
                    {v.needs_review && <Tag tone="warning">Nuevo</Tag>}
                  </p>
                  <p className="truncate text-xs text-subtle">
                    {v.tax_id ? `ID fiscal ${v.tax_id} · ` : ''}Desde {shortDate(v.created_at)}
                  </p>
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-3">
                <span
                  className={`hidden text-[13px] font-medium sm:inline ${
                    v.is_allowed ? 'text-brand-700' : v.needs_review ? 'text-warning-700' : 'text-subtle'
                  }`}
                >
                  {v.is_allowed ? 'Autorizado' : v.needs_review ? 'Por aprobar' : 'Bloqueado'}
                </span>
                <Toggle
                  checked={v.is_allowed}
                  disabled={busyId === v.id}
                  label={`${v.is_allowed ? 'Bloquear' : 'Autorizar'} a ${v.name}`}
                  onChange={(val) => toggle(v, val)}
                />
              </div>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}
