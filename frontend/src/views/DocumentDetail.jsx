import { api } from '../api'
import { TypeCode } from '../components/DocumentTable'
import DocumentViewer from '../components/DocumentViewer'
import Icon from '../components/icons'
import { Button, Card, ErrorBox, Loading, Notice, PageHeader, ReviewFlag, StatusBadge, Tag } from '../components/ui'
import { DOC_TYPES, clp, dateTime, reviewReason, rut, shortDate } from '../format'
import { href, useLoad } from '../hooks'

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
    <Card
      title="Montos"
      subtitle="neto + IVA + impuestos = total"
      action={
        difference === 0 ? (
          <Tag tone="success" icon="check">
            Cuadra
          </Tag>
        ) : difference != null ? (
          <Tag tone="danger" icon="notEqual">
            No cuadra
          </Tag>
        ) : null
      }
    >
      {noAmounts ? (
        <p className="text-sm text-muted">Sin montos (guía de despacho sin valorizar).</p>
      ) : (
        <dl className="text-sm">
          {parts.map(([label, value], i) => (
            <div key={label} className="flex items-baseline justify-between gap-4 py-1.5">
              <dt className="flex items-baseline gap-2 text-muted">
                <span aria-hidden="true" className="w-3 font-mono text-xs text-subtle">
                  {i ? '+' : ''}
                </span>
                {label}
              </dt>
              <dd className="tabular">{value == null ? <span className="text-subtle">sin valor</span> : clp(value)}</dd>
            </div>
          ))}
          <div className="mt-2 flex items-baseline justify-between gap-4 border-t border-dashed border-line-strong pt-3 pb-1.5">
            <dt className="flex items-baseline gap-2 text-muted">
              <span aria-hidden="true" className="w-3 font-mono text-xs text-subtle">
                =
              </span>
              Calculado
            </dt>
            <dd className="font-medium tabular">{clp(calculated)}</dd>
          </div>
          <div className="flex items-baseline justify-between gap-4 py-1.5">
            <dt className="pl-5 font-medium text-ink">Total del documento</dt>
            <dd className="text-base font-semibold text-ink tabular">{clp(doc.total)}</dd>
          </div>
          {difference != null && difference !== 0 && (
            <div className="mt-2 flex justify-between rounded-control bg-danger-50 px-3 py-2 text-danger-700 ring-1 ring-danger-600/20 ring-inset">
              <dt className="font-medium">Diferencia</dt>
              <dd className="font-semibold tabular">{clp(difference)}</dd>
            </div>
          )}
        </dl>
      )}
    </Card>
  )
}

function Data({ label, children }) {
  return (
    <div className="grid grid-cols-[8.5rem_minmax(0,1fr)] items-baseline gap-3 py-2.5 sm:grid-cols-[10rem_minmax(0,1fr)]">
      <dt className="text-[13px] text-muted">{label}</dt>
      <dd className="text-sm font-medium text-ink">{children}</dd>
    </div>
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
      <PageHeader
        back={{ href: href('documentos'), label: 'Documentos' }}
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
              Guardado el {dateTime(d.creado_en)} · id {d.id} · {d.carpeta && `carpeta ${d.carpeta} · `}
              {d.revisado_en ? `revisado por ${d.usuario} el ${dateTime(d.revisado_en)}` : `procesado por ${d.usuario}`}
            </span>
          </span>
        }
        actions={
          <Button
            variant={d.requiere_revision ? 'primary' : 'secondary'}
            icon="pencil"
            onClick={() => (window.location.hash = href('revision', d.id))}
          >
            {d.requiere_revision ? 'Revisar y corregir' : 'Corregir'}
          </Button>
        }
      />

      {d.requiere_revision && (
        <Notice tone="brand" role="alert" title="Requiere revisión humana.">
          {reviewReason(d)}
          {illegibleRut && ' El RUT no se pudo leer y se guardó como 1-9.'}
        </Notice>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,6fr)_minmax(0,5fr)]">
        <div className="lg:sticky lg:top-6 lg:self-start">
          <DocumentViewer id={d.id} />
        </div>

        <div className="space-y-6">
          <Card title="Datos guardados">
            <dl className="-my-2.5 divide-y divide-line">
              <Data label="Tipo">
                {DOC_TYPES[d.tipo]} <span className="text-muted">({d.tipo})</span>
              </Data>
              <Data label="Folio">
                <span className="tabular">{d.folio ?? <span className="font-normal text-subtle">no legible</span>}</span>
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
              <Data label="Fecha">
                {d.fecha ? shortDate(d.fecha) : <span className="font-normal text-subtle">no legible</span>}
              </Data>
              <Data label="Firma">
                <span className="inline-flex items-center gap-1.5">
                  {d.firma && <Icon name="check" size={15} strokeWidth={2.2} className="text-success-600" />}
                  {d.firma ? 'Firmado' : 'Sin firma'}
                </span>
              </Data>
              <Data label="Observaciones">
                <StatusBadge status={d.observaciones} size="sm" />
              </Data>
            </dl>
          </Card>

          <Sum doc={d} />
        </div>
      </div>
    </div>
  )
}
