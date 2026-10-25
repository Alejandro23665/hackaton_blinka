import { useState } from 'react'
import { api } from '../api'
import Icon from '../components/icons'
import { Card, ErrorBox, Eyebrow, Loading, Segmented, StatusBadge, Tag, Tile } from '../components/ui'
import { DOC_TYPES, REVIEW_REASONS, clp, dateTime, rut, shortDate } from '../format'
import { href, useLoad } from '../hooks'

/** El archivo original: imagen (con zoom para revisarla) o PDF. */
function Viewer({ doc }) {
  const [zoom, setZoom] = useState(1)
  const url = api.imageUrl(doc.id)
  const isPdf = doc.imagen.toLowerCase().endsWith('.pdf')

  return (
    <Card
      title="Documento original"
      subtitle={isPdf ? 'PDF' : 'Imagen tal como se subió'}
      action={
        <div className="flex items-center gap-3">
          {!isPdf && (
            <Segmented
              size="sm"
              value={zoom}
              onChange={setZoom}
              options={[
                { value: 1, label: 'Ajustar' },
                { value: 2, label: '200 %' },
                { value: 3, label: '300 %' },
              ]}
            />
          )}
          <a
            href={url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-[13px] font-medium text-brand-700 hover:underline"
          >
            Abrir <Icon name="external" size={14} />
          </a>
        </div>
      }
    >
      {isPdf ? (
        <iframe src={url} title="Documento original" className="h-[75vh] w-full rounded-control border border-line" />
      ) : (
        <div className="max-h-[75vh] overflow-auto rounded-control border border-line bg-surface">
          <img src={url} alt="Documento original" className="block h-auto max-w-none" style={{ width: `${zoom * 100}%` }} />
        </div>
      )}
    </Card>
  )
}

/** neto + IVA + impuestos = calculado, frente al total guardado. */
function Sum({ doc }) {
  const parts = [
    ['Neto', doc.total_neto],
    ['IVA', doc.iva],
    ['Impuestos (otros + exento)', doc.impuestos],
  ]
  const noAmounts = [doc.total_neto, doc.iva, doc.impuestos, doc.total].every((v) => v == null)
  const computable = doc.total_neto != null && doc.iva != null && doc.total != null
  const calculated = computable ? doc.total_neto + doc.iva + (doc.impuestos ?? 0) : null
  const difference = computable ? doc.total - calculated : null

  return (
    <Card title="Montos" subtitle="neto + IVA + impuestos = total">
      {noAmounts ? (
        <p className="text-sm text-muted">Sin montos (guía de despacho sin valorizar).</p>
      ) : (
        <dl className="space-y-2 text-sm">
          {parts.map(([label, value]) => (
            <div key={label} className="flex justify-between">
              <dt className="text-muted">{label}</dt>
              <dd className="tabular">{value == null ? <span className="text-subtle">sin valor</span> : clp(value)}</dd>
            </div>
          ))}
          <div className="flex justify-between border-t border-line pt-2">
            <dt className="text-muted">Calculado</dt>
            <dd className="tabular font-medium">{clp(calculated)}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted">Total del documento</dt>
            <dd className="tabular font-medium">{clp(doc.total)}</dd>
          </div>
          {difference != null && difference !== 0 && (
            <div className="flex justify-between rounded-control bg-danger-50 px-3 py-2 text-danger-700">
              <dt className="font-medium">Diferencia</dt>
              <dd className="tabular font-semibold">{clp(difference)}</dd>
            </div>
          )}
        </dl>
      )}
    </Card>
  )
}

function Data({ label, children }) {
  return (
    <Tile>
      <Eyebrow>{label}</Eyebrow>
      <div className="mt-1 text-sm font-medium text-ink">{children}</div>
    </Tile>
  )
}

/** Detalle de un documento: archivo original, datos guardados y suma de montos. */
export default function DocumentDetail({ id }) {
  const doc = useLoad(() => api.documents.get(id), id)

  if (!doc.data) {
    return doc.loading ? <Loading rows={5} /> : <ErrorBox message={doc.error} />
  }
  const d = doc.data
  const illegibleRut = d.rut_proveedor === '1-9'

  return (
    <div className="space-y-6">
      <div>
        <a href={href('documentos')} className="inline-flex items-center gap-1.5 text-[13px] text-muted hover:text-brand-700">
          <Icon name="arrowLeft" size={14} /> Documentos
        </a>
        <h2 className="mt-1 flex flex-wrap items-center gap-3 text-xl font-semibold tracking-tight">
          {DOC_TYPES[d.tipo]}
          {d.folio && <span className="tabular text-muted">N° {d.folio}</span>}
          <StatusBadge status={d.observaciones} />
        </h2>
        <p className="mt-1 text-xs text-subtle">Guardado el {dateTime(d.creado_en)} · id {d.id}</p>
      </div>

      {d.requiere_revision && (
        <p role="alert" className="flex items-start gap-2 rounded-control bg-warning-50 px-4 py-3 text-sm text-warning-700">
          <Icon name="alert" size={18} className="mt-px" />
          <span>
            <span className="font-semibold">Requiere revisión humana.</span> {REVIEW_REASONS[d.observaciones]}
            {illegibleRut && ' El RUT no se pudo leer y se guardó como 1-9.'}
          </span>
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,6fr)_minmax(0,5fr)]">
        <div className="lg:sticky lg:top-24 lg:self-start">
          <Viewer doc={d} />
        </div>

        <div className="space-y-6">
          <Card title="Datos guardados">
            <div className="grid gap-3 sm:grid-cols-2">
              <Data label="Tipo">
                {DOC_TYPES[d.tipo]} <span className="text-muted">({d.tipo})</span>
              </Data>
              <Data label="Folio">
                <span className="tabular">{d.folio ?? <span className="text-subtle">no legible</span>}</span>
              </Data>
              <Data label="RUT proveedor">
                {illegibleRut ? (
                  <span className="inline-flex items-center gap-1.5">
                    1-9 <Tag tone="warning">ilegible</Tag>
                  </span>
                ) : (
                  <span className="tabular">{rut(d.rut_proveedor)}</span>
                )}
              </Data>
              <Data label="Fecha">{d.fecha ? shortDate(d.fecha) : <span className="text-subtle">no legible</span>}</Data>
              <Data label="Firma">{d.firma ? 'Firmado' : 'Sin firma'}</Data>
              <Data label="Observaciones">
                <StatusBadge status={d.observaciones} size="sm" />
              </Data>
            </div>
          </Card>

          <Sum doc={d} />
        </div>
      </div>
    </div>
  )
}
