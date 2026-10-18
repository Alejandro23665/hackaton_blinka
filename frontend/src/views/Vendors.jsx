import { useState } from 'react'
import { api } from '../api'
import Modal from '../components/Modal'
import { inputClass } from '../components/styles'
import { Button, Card, ConfirmDelete, Empty, ErrorBox, Field, IconButton, Loading, Tag, Toggle } from '../components/ui'
import { money, shortDate } from '../format'
import { useLoad } from '../hooks'

function agreementSummary(v) {
  if (v.agreed_amount == null) return null
  const tol = Number(v.agreement_tolerance_pct).toLocaleString('es', { maximumFractionDigits: 2 })
  return `${money(v.agreed_amount, v.agreed_currency)} ±${tol} %`
}

function vendorToForm(v, defaultCurrency) {
  return {
    name: v?.name ?? '',
    tax_id: v?.tax_id ?? '',
    is_allowed: v?.is_allowed ?? true,
    amount: v?.agreed_amount ?? '',
    currency: v?.agreed_currency ?? defaultCurrency,
    tolerance: v?.agreement_tolerance_pct ?? 5,
    notes: v?.agreement_notes ?? '',
  }
}

/**
 * Crear o editar un proveedor en un modal. Solo el nombre es obligatorio:
 * el acuerdo (monto, moneda, tolerancia) se puede definir ahora o más adelante.
 */
function VendorFormModal({ vendor, currencies, onClose, onSaved }) {
  const editing = Boolean(vendor)
  const [form, setForm] = useState(() => vendorToForm(vendor, currencies[0] ?? 'USD'))
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (key) => (e) => {
    setForm({ ...form, [key]: e.target.value })
    setError(null)
  }

  const hasAgreement = String(form.amount).trim() !== ''
  const options = [...new Set([...currencies, form.currency])]

  async function submit(e) {
    e.preventDefault()
    if (!form.name.trim()) {
      setError('Escribe la razón social o el nombre del proveedor')
      return
    }
    if (hasAgreement && !(Number(form.amount) > 0)) {
      setError('El monto acordado debe ser mayor que 0')
      return
    }
    const tolerance = Number(form.tolerance)
    if (hasAgreement && !(tolerance >= 0 && tolerance <= 100)) {
      setError('La tolerancia debe estar entre 0 y 100 %')
      return
    }

    // Sin monto no hay acuerdo: se envían nulos para crearlo sin acuerdo o quitar el que tenía
    const payload = {
      name: form.name.trim(),
      tax_id: form.tax_id.trim() || null,
      agreed_amount: hasAgreement ? Number(form.amount) : null,
      agreed_currency: hasAgreement ? form.currency : null,
      agreement_notes: form.notes.trim() || null,
      ...(hasAgreement ? { agreement_tolerance_pct: tolerance } : {}),
      ...(editing ? {} : { is_allowed: form.is_allowed }),
    }

    setBusy(true)
    setError(null)
    try {
      if (editing) await api.vendors.update(vendor.id, payload)
      else await api.vendors.create(payload)
      onSaved()
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <Modal
      title={editing ? `Editar ${vendor.name}` : 'Nuevo proveedor'}
      subtitle={editing ? null : 'Solo la razón social o nombre es obligatorio; el resto puedes completarlo después.'}
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose} disabled={busy}>
            Cancelar
          </Button>
          <Button type="submit" form="vendor-form" icon={editing ? 'check' : 'plus'} disabled={busy}>
            {busy ? 'Guardando…' : editing ? 'Guardar cambios' : 'Añadir proveedor'}
          </Button>
        </div>
      }
    >
      <form id="vendor-form" onSubmit={submit} noValidate className="space-y-5">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-[1fr_200px]">
          <Field label="Razón social o nombre" hint="Empresa o persona contratista, tal como aparece en sus facturas">
            <input className={inputClass} placeholder="Ej. Acme Tech Solutions Inc. o Ana Pérez" value={form.name} onChange={set('name')} autoFocus />
          </Field>
          <Field label="ID fiscal (opcional)" hint="RUC, NIT, RFC… ayuda a reconocerlo en facturas">
            <input className={`${inputClass} uppercase`} maxLength={50} placeholder="20123456789" value={form.tax_id} onChange={set('tax_id')} />
          </Field>
        </div>

        {!editing && (
          <div className="flex items-center justify-between gap-4 rounded-control border border-line px-4 py-3">
            <div>
              <p className="text-sm font-medium text-ink">Autorizado para recibir pagos</p>
              <p className="text-xs text-muted">Si no, el agente bloqueará sus facturas.</p>
            </div>
            <Toggle
              checked={form.is_allowed}
              label="Autorizado para recibir pagos"
              onChange={(value) => setForm({ ...form, is_allowed: value })}
            />
          </div>
        )}

        <fieldset className="space-y-4 rounded-control border border-line p-4">
          <legend className="px-1 text-sm font-semibold text-ink">
            Acuerdo con el proveedor <span className="font-normal text-muted">(opcional)</span>
          </legend>
          <p className="-mt-1 text-[13px] text-muted">
            Si una factura se desvía de este monto más que la tolerancia, o llega en otra moneda, el agente la escala a
            revisión humana. Déjalo vacío si no hay un monto fijo.
          </p>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-[1fr_96px_110px]">
            <div className="col-span-2 sm:col-span-1">
              <Field label="Monto acordado">
                <input
                  className={`${inputClass} tabular`}
                  type="number"
                  inputMode="decimal"
                  min="0.01"
                  step="0.01"
                  placeholder="Sin acuerdo"
                  value={form.amount}
                  onChange={set('amount')}
                />
              </Field>
            </div>
            <Field label="Moneda">
              <select className={inputClass} value={form.currency} onChange={set('currency')} disabled={!hasAgreement}>
                {options.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </Field>
            <Field label="Tolerancia %">
              <input
                className={`${inputClass} tabular`}
                type="number"
                inputMode="decimal"
                min="0"
                max="100"
                step="0.5"
                value={form.tolerance}
                onChange={set('tolerance')}
                disabled={!hasAgreement}
              />
            </Field>
          </div>
          <Field label="Qué se acordó" hint="Aparece en la explicación de cada decisión">
            <input
              className={inputClass}
              maxLength={500}
              placeholder="Ej. Desarrollo web, tarifa mensual fija"
              value={form.notes}
              onChange={set('notes')}
            />
          </Field>
        </fieldset>

        <ErrorBox message={error} />
      </form>
    </Modal>
  )
}

export default function Vendors({ version, onChange }) {
  const vendors = useLoad(() => api.vendors.list(), version)
  const rates = useLoad(() => api.exchangeRates.list(), version)
  // null = cerrado; 'new' = crear; objeto = editar ese proveedor
  const [modal, setModal] = useState(null)
  const [error, setError] = useState(null)
  const [busyId, setBusyId] = useState(null)

  const list = vendors.data ?? []
  const allowed = list.filter((v) => v.is_allowed).length
  const pending = list.filter((v) => v.needs_review).length
  const currencies = ['USD', ...(rates.data ?? []).map((r) => r.currency)]

  async function remove(vendor) {
    setError(null)
    try {
      await api.vendors.remove(vendor.id)
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
          <div className="flex flex-wrap items-center gap-2">
            {pending > 0 && <Tag tone="warning">{pending} por aprobar</Tag>}
            {vendors.data && <Tag tone="brand">{allowed} de {list.length} autorizados</Tag>}
            <Button size="sm" icon="plus" onClick={() => setModal('new')}>
              Añadir proveedor
            </Button>
          </div>
        }
      >
        <div className="mb-4">
          <ErrorBox message={error ?? vendors.error} />
        </div>

        {vendors.loading && !vendors.data && <Loading rows={4} />}
        {vendors.data?.length === 0 && (
          <Empty icon="store" title="Aún no hay proveedores">
            Usa «Añadir proveedor» para registrar el primero.
          </Empty>
        )}

        {list.length > 0 && (
          <ul className="divide-y divide-line rounded-card border border-line">
            {list.map((v) => (
              <li key={v.id} className="relative flex items-center justify-between gap-4 px-4 py-3.5 sm:px-5">
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
                    <p className="mt-0.5 truncate text-xs" title={v.agreement_notes ?? undefined}>
                      {agreementSummary(v) ? (
                        <span className="text-brand-700">
                          Acordado: {agreementSummary(v)}
                          {v.agreement_notes ? ` · ${v.agreement_notes}` : ''}
                        </span>
                      ) : (
                        <span className="text-subtle">Sin acuerdo de monto</span>
                      )}
                    </p>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  {v.needs_review ? (
                    // Pendiente: el interruptor ya estaría apagado, así que se decide con botones explícitos
                    <div className="flex items-center gap-1.5" role="group" aria-label={`Decidir sobre ${v.name}`}>
                      <Button size="sm" variant="secondary" icon="x" disabled={busyId === v.id} onClick={() => toggle(v, false)}>
                        Bloquear
                      </Button>
                      <Button size="sm" icon="check" disabled={busyId === v.id} onClick={() => toggle(v, true)}>
                        Autorizar
                      </Button>
                    </div>
                  ) : (
                    <>
                      <span className={`hidden text-[13px] font-medium sm:inline ${v.is_allowed ? 'text-brand-700' : 'text-subtle'}`}>
                        {v.is_allowed ? 'Autorizado' : 'Bloqueado'}
                      </span>
                      <Toggle
                        checked={v.is_allowed}
                        disabled={busyId === v.id}
                        label={`${v.is_allowed ? 'Bloquear' : 'Autorizar'} a ${v.name}`}
                        onChange={(val) => toggle(v, val)}
                      />
                    </>
                  )}
                  <IconButton
                    icon="pencil"
                    label={`Editar ${v.name}`}
                    className="!h-8 !w-8 border-transparent"
                    onClick={() => setModal(v)}
                  />
                  <ConfirmDelete label={`Eliminar a ${v.name}`} warning={`¿Eliminar a ${v.name}?`} onConfirm={() => remove(v)} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {modal && (
        <VendorFormModal
          vendor={modal === 'new' ? null : modal}
          currencies={currencies}
          onClose={() => setModal(null)}
          onSaved={() => {
            setModal(null)
            onChange()
          }}
        />
      )}
    </div>
  )
}
