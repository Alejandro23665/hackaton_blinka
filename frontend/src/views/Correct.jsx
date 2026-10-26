import { useState } from 'react'
import { api } from '../api'
import DocumentViewer from '../components/DocumentViewer'
import Icon from '../components/icons'
import { inputClass } from '../components/styles'
import { Button, Card, ErrorBox, Loading, StatusBadge, Toggle } from '../components/ui'
import { DOC_TYPES, FIELD_LABELS, REVIEW_REASONS, clp, dateTime, rut } from '../format'
import { href, useLoad } from '../hooks'

const AMOUNTS = ['total_neto', 'iva', 'impuestos', 'total']

/** "$ 1.234" → 1234; vacío → null; cualquier otra cosa → NaN (se marca como error). */
function parseAmount(text) {
  const clean = String(text).replace(/[$\s.]/g, '')
  if (clean === '') return null
  return /^\d+$/.test(clean) ? Number(clean) : NaN
}

/** Valores iniciales del formulario. Los montos en 0 de un NO_LEGIBLE no se leyeron: van vacíos. */
function initialValues(doc) {
  const zeroed = doc.observaciones === 'NO_LEGIBLE' && AMOUNTS.every((name) => doc[name] === 0)
  const amount = (name) => (zeroed || doc[name] == null ? '' : String(doc[name]))
  return {
    tipo: doc.tipo,
    rut_proveedor: doc.rut_proveedor && doc.rut_proveedor !== '1-9' ? rut(doc.rut_proveedor) : '',
    folio: doc.folio ?? '',
    fecha: doc.fecha ?? '',
    firma: doc.firma,
    ...Object.fromEntries(AMOUNTS.map((name) => [name, amount(name)])),
  }
}

/** Marca de un campo: falta (rojo) o con dudas (ámbar). */
function Problem({ kind }) {
  if (!kind) return null
  return kind === 'falta' ? (
    <span className="text-xs font-medium text-danger-700">Falta: no se pudo leer</span>
  ) : (
    <span className="text-xs font-medium text-warning-700">Con dudas: revísalo</span>
  )
}

function FormField({ name, problem, children }) {
  const ring = problem === 'falta' ? 'rounded-control ring-2 ring-danger-600/40' : problem === 'duda' ? 'rounded-control ring-2 ring-warning-600/40' : ''
  return (
    <label className="block">
      <span className="mb-1.5 flex items-center justify-between gap-2">
        <span className="text-[13px] font-medium text-ink">{FIELD_LABELS[name]}</span>
        <Problem kind={problem} />
      </span>
      <div className={ring}>{children}</div>
    </label>
  )
}

function Form({ doc, onSaved }) {
  const [values, setValues] = useState(() => initialValues(doc))
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const problem = (name) =>
    doc.campos_faltantes.includes(name) ? 'falta' : doc.campos_dudosos.includes(name) ? 'duda' : null
  const set = (name) => (e) => {
    setValues((v) => ({ ...v, [name]: e.target.value }))
    setError(null)
  }

  const amounts = Object.fromEntries(AMOUNTS.map((name) => [name, parseAmount(values[name])]))
  const invalid = AMOUNTS.filter((name) => Number.isNaN(amounts[name]))
  const unvalued = values.tipo === 'GD' && AMOUNTS.every((name) => amounts[name] == null)
  const computable = !invalid.length && amounts.total_neto != null && amounts.iva != null && amounts.total != null
  const calculated = computable ? amounts.total_neto + amounts.iva + (amounts.impuestos ?? 0) : null
  const difference = computable ? amounts.total - calculated : null
  const mismatch = difference != null && difference !== 0

  async function save(e) {
    e.preventDefault()
    if (!values.rut_proveedor.trim() || !values.folio.trim() || !values.fecha) {
      setError('Completa el RUT, el folio y la fecha.')
      return
    }
    if (invalid.length) {
      setError(`Montos no válidos: ${invalid.map((n) => FIELD_LABELS[n]).join(', ')}. Usa solo números.`)
      return
    }
    if (!unvalued && !computable) {
      setError('Completa el neto, el IVA y el total (una guía sin valorizar puede ir sin montos).')
      return
    }
    if (mismatch && !confirm) {
      setError('Los montos no cuadran. Corrígelos o confirma que el documento trae ese descuadre.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await api.documents.correct(doc.id, { ...values, ...amounts, confirmar_descuadre: mismatch && confirm })
      onSaved()
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <form onSubmit={save} noValidate className="space-y-6">
      <Card title="Datos del documento" subtitle="Corrige lo marcado y confirma el resto">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1.5 block text-[13px] font-medium text-ink">Tipo</span>
            <select value={values.tipo} onChange={set('tipo')} className={inputClass}>
              {['FC', 'CI', 'GD'].map((code) => (
                <option key={code} value={code}>
                  {DOC_TYPES[code]} ({code})
                </option>
              ))}
            </select>
          </label>
          <FormField name="folio" problem={problem('folio')}>
            <input value={values.folio} onChange={set('folio')} className={inputClass} />
          </FormField>
          <FormField name="rut_proveedor" problem={problem('rut_proveedor')}>
            <input value={values.rut_proveedor} onChange={set('rut_proveedor')} placeholder="76.084.682-1" className={inputClass} />
          </FormField>
          <FormField name="fecha" problem={problem('fecha')}>
            <input type="date" value={values.fecha} onChange={set('fecha')} className={inputClass} />
          </FormField>
          <div className="sm:col-span-2">
            <span className="mb-1.5 flex items-center justify-between gap-2">
              <span className="text-[13px] font-medium text-ink">{FIELD_LABELS.firma}</span>
              <Problem kind={problem('firma')} />
            </span>
            <span className="flex items-center gap-3 text-sm text-ink">
              <Toggle checked={values.firma} onChange={(firma) => setValues((v) => ({ ...v, firma }))} label="Firmado" />
              {values.firma ? 'Firmado' : 'Sin firma'}
            </span>
          </div>
        </div>
      </Card>

      <Card title="Montos" subtitle="neto + IVA + impuestos = total, en pesos">
        <div className="grid gap-4 sm:grid-cols-2">
          {AMOUNTS.map((name) => (
            <FormField key={name} name={name} problem={problem(name)}>
              <input
                inputMode="numeric"
                value={values[name]}
                onChange={set(name)}
                placeholder={name === 'impuestos' ? 'vacío si no tiene' : ''}
                className={`${inputClass} text-right tabular`}
              />
            </FormField>
          ))}
        </div>
        <dl className="mt-5 space-y-2 border-t border-line pt-4 text-sm">
          <div className="flex justify-between">
            <dt className="text-muted">Calculado</dt>
            <dd className="tabular font-medium">{unvalued ? 'sin montos' : clp(calculated)}</dd>
          </div>
          {mismatch && (
            <>
              <div className="flex justify-between rounded-control bg-danger-50 px-3 py-2 text-danger-700">
                <dt className="font-medium">Diferencia con el total</dt>
                <dd className="tabular font-semibold">{clp(difference)}</dd>
              </div>
              <label className="flex items-start gap-2 text-[13px] text-ink">
                <input
                  type="checkbox"
                  checked={confirm}
                  onChange={(e) => {
                    setConfirm(e.target.checked)
                    setError(null)
                  }}
                  className="mt-0.5 h-4 w-4 accent-[var(--color-brand-600)]"
                />
                Confirmo que el documento trae este descuadre (se guarda como Descuadre revisado).
              </label>
            </>
          )}
        </dl>
      </Card>

      <ErrorBox message={error} />
      <div className="flex justify-end">
        <Button type="submit" icon="check" disabled={busy}>
          {busy ? 'Guardando…' : 'Guardar revisión'}
        </Button>
      </div>
    </form>
  )
}

/** Corrección de un documento: la imagen a la izquierda y el formulario a la derecha. */
export default function Correct({ id }) {
  const doc = useLoad(() => api.documents.get(id), id)

  async function next() {
    // Al guardar, se pasa al siguiente pendiente (el más antiguo); si no hay, a la lista
    const pending = await api.documents.list({ requiere_revision: 'true', orden: 'antiguos', limite: 1 }).catch(() => null)
    const following = pending?.documentos[0]
    window.location.hash = following ? href('revision', following.id) : href('revision')
  }

  if (!doc.data) return doc.loading ? <Loading rows={5} /> : <ErrorBox message={doc.error} />
  const d = doc.data

  return (
    <div className="space-y-6">
      <div>
        <a href={href('revision')} className="inline-flex items-center gap-1.5 text-[13px] text-muted hover:text-brand-700">
          <Icon name="arrowLeft" size={14} /> Revisión
        </a>
        <h2 className="mt-1 flex flex-wrap items-center gap-3 text-xl font-semibold tracking-tight">
          {DOC_TYPES[d.tipo]}
          {d.folio && <span className="tabular text-muted">N° {d.folio}</span>}
          <StatusBadge status={d.observaciones} />
        </h2>
        <p className="mt-1 text-xs text-subtle">
          Subido el {dateTime(d.creado_en)} · id {d.id}
        </p>
      </div>

      {d.requiere_revision ? (
        <p className="flex items-start gap-2 rounded-control bg-warning-50 px-4 py-3 text-sm text-warning-700">
          <Icon name="alert" size={18} className="mt-px" />
          {REVIEW_REASONS[d.observaciones]}
        </p>
      ) : (
        <p className="flex items-start gap-2 rounded-control bg-success-50 px-4 py-3 text-sm text-success-700">
          <Icon name="check" size={18} className="mt-px" />
          {d.revisado_en ? `Revisado por ${d.usuario} el ${dateTime(d.revisado_en)}.` : 'No requiere revisión.'} Puedes
          volver a corregirlo si hace falta.
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,6fr)_minmax(0,5fr)]">
        <div className="lg:sticky lg:top-24 lg:self-start">
          <DocumentViewer id={d.id} />
        </div>
        <Form key={d.id} doc={d} onSaved={next} />
      </div>
    </div>
  )
}
