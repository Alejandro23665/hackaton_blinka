import { useState } from 'react'
import { api } from '../api'
import DocumentViewer from '../components/DocumentViewer'
import Icon from '../components/icons'
import { inputClass } from '../components/styles'
import { TypeCode } from '../components/DocumentTable'
import { Button, Card, ErrorBox, Loading, Notice, PageHeader, ReviewFlag, StatusBadge, Toggle } from '../components/ui'
import { DOC_TYPES, FIELD_LABELS, FREQUENT_RUTS, clp, dateTime, reviewReason, rut } from '../format'
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
    <span className="inline-flex items-center gap-1 text-xs font-medium text-danger-700">
      <Icon name="alert" size={12} strokeWidth={2.2} />
      Falta: no se pudo leer
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-warning-700">
      <Icon name="eyeOff" size={12} strokeWidth={2.2} />
      Con dudas: revísalo
    </span>
  )
}

function FormField({ name, problem, children }) {
  const ring =
    problem === 'falta'
      ? 'rounded-control ring-[3px] ring-danger-600/25 [&_input]:border-danger-600/60'
      : problem === 'duda'
        ? 'rounded-control ring-[3px] ring-warning-600/25 [&_input]:border-warning-600/60'
        : ''
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

/** Botones con los RUT más habituales del tipo: un clic los escribe en el campo. */
function FrequentRuts({ tipo, value, onPick }) {
  const options = FREQUENT_RUTS[tipo] ?? []
  if (!options.length) return null
  const current = value.replace(/[.\s]/g, '').toUpperCase()
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5">
      <span className="text-[11px] text-subtle">Habituales:</span>
      {options.map((option) => (
        <button
          key={option}
          type="button"
          onClick={() => onPick(rut(option))}
          aria-pressed={current === option}
          className={`h-7 rounded-md border px-2 text-xs tabular transition-colors ${
            current === option
              ? 'border-brand-600 bg-brand-50 font-medium text-brand-700'
              : 'border-line bg-canvas text-muted hover:border-brand-300 hover:bg-brand-25 hover:text-brand-700'
          }`}
        >
          {rut(option)}
        </button>
      ))}
    </div>
  )
}

function Form({ doc, onSaved }) {
  const [initial] = useState(() => initialValues(doc))
  const [values, setValues] = useState(initial)
  // Sin cambios se acepta tal como está; con cambios se guardan
  const changed = JSON.stringify(values) !== JSON.stringify(initial)
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

  async function accept() {
    setBusy(true)
    setError(null)
    try {
      await api.documents.accept(doc.id)
      onSaved()
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  async function save(e) {
    e.preventDefault()
    if (!changed) return
    // Ningún dato es obligatorio: lo que no se puede leer va vacío y se guarda como No legible.
    // Lo que sí se escribe debe ser válido.
    if (values.tipo === 'DESC') {
      setError('Elige el tipo del documento.')
      return
    }
    if (invalid.length) {
      setError(`Montos no válidos: ${invalid.map((n) => FIELD_LABELS[n]).join(', ')}. Usa solo números.`)
      return
    }
    if (mismatch && !confirm) {
      setError('Los montos no cuadran. Corrígelos o confirma que el documento trae ese descuadre.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await api.documents.correct(doc.id, {
        ...values,
        ...amounts,
        rut_proveedor: values.rut_proveedor.trim() || null,
        folio: values.folio.trim() || null,
        fecha: values.fecha || null,
        confirmar_descuadre: mismatch && confirm,
      })
      onSaved()
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <form onSubmit={save} noValidate className="space-y-6">
      <Card
        title="Datos del documento"
        subtitle="Corrige lo que puedas leer. Lo que no se vea en el documento, déjalo vacío: se guarda como No legible."
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1.5 block text-[13px] font-medium text-ink">Tipo</span>
            <select value={values.tipo} onChange={set('tipo')} className={inputClass}>
              {doc.tipo === 'DESC' && (
                <option value="DESC" disabled>
                  {DOC_TYPES.DESC} (DESC)
                </option>
              )}
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
          <div>
            <FormField name="rut_proveedor" problem={problem('rut_proveedor')}>
              <input value={values.rut_proveedor} onChange={set('rut_proveedor')} placeholder="76.084.682-1" className={inputClass} />
            </FormField>
            <FrequentRuts
              tipo={values.tipo}
              value={values.rut_proveedor}
              onPick={(value) => {
                setValues((v) => ({ ...v, rut_proveedor: value }))
                setError(null)
              }}
            />
          </div>
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
        <dl className="mt-5 space-y-2 border-t border-dashed border-line-strong pt-4 text-sm">
          <div className="flex items-center justify-between gap-3">
            <dt className="text-muted">Calculado</dt>
            <dd className="flex items-center gap-2 font-medium tabular">
              {computable && !mismatch && (
                <span className="inline-flex items-center gap-1 text-xs font-medium text-success-700">
                  <Icon name="check" size={13} strokeWidth={2.2} />
                  cuadra con el total
                </span>
              )}
              {unvalued ? 'sin montos' : clp(calculated)}
            </dd>
          </div>
          {mismatch && (
            <>
              <div className="flex justify-between rounded-control bg-danger-50 px-3 py-2 text-danger-700 ring-1 ring-danger-600/20 ring-inset">
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

      {/* Acciones siempre a mano: la barra queda fija abajo mientras se recorre el formulario */}
      <div className="sticky bottom-[calc(66px+env(safe-area-inset-bottom))] z-10 space-y-3 rounded-card border border-line bg-canvas/95 p-4 shadow-pop backdrop-blur-md lg:bottom-4">
        <ErrorBox message={error} />
        <div className="flex flex-wrap items-center justify-end gap-3">
          <p className="mr-auto flex min-w-[12rem] flex-1 items-start gap-2 text-xs leading-relaxed text-muted">
            <span
              aria-hidden="true"
              className={`mt-[5px] h-1.5 w-1.5 shrink-0 rounded-full ${changed ? 'bg-brand-600' : 'bg-line-strong'}`}
            />
            {changed
              ? 'Hay cambios sin guardar. Guárdalos para corregir el documento.'
              : 'Si no se puede leer mejor, acéptalo tal como está: queda revisado a tu nombre.'}
          </p>
          <Button type="button" variant="secondary" icon="check" disabled={changed || busy} onClick={accept}>
            Aceptar
          </Button>
          <Button type="submit" icon="pencil" disabled={!changed || busy}>
            {busy ? 'Guardando…' : 'Guardar cambios'}
          </Button>
        </div>
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
      <PageHeader
        back={{ href: href('revision'), label: 'Revisión' }}
        title={
          <>
            <TypeCode tipo={d.tipo} />
            {DOC_TYPES[d.tipo]}
            {d.folio && <span className="font-normal text-muted tabular">N° {d.folio}</span>}
          </>
        }
        meta={
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1.5">
            <StatusBadge status={d.observaciones} />
            {d.requiere_revision && <ReviewFlag />}
            <span className="text-xs text-subtle">
              Subido el {dateTime(d.creado_en)} · id {d.id}
            </span>
          </span>
        }
      />

      {d.requiere_revision ? (
        <Notice tone="brand" title="Por qué está en revisión:">
          {reviewReason(d)}
        </Notice>
      ) : (
        <Notice tone="success">
          {d.revisado_en ? `Revisado por ${d.usuario} el ${dateTime(d.revisado_en)}.` : 'No requiere revisión.'} Puedes
          volver a corregirlo si hace falta.
        </Notice>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,6fr)_minmax(0,5fr)]">
        <div className="lg:sticky lg:top-6 lg:self-start">
          <DocumentViewer id={d.id} />
        </div>
        <Form key={d.id} doc={d} onSaved={next} />
      </div>
    </div>
  )
}
