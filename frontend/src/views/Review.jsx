import { api } from '../api'
import Icon from '../components/icons'
import { Button, Card, Empty, ErrorBox, Loading, PageHeader, StatusBadge, Tag } from '../components/ui'
import { DOC_TYPES, FIELD_LABELS, STATUS, dateTime, rut } from '../format'
import { href, useLoad } from '../hooks'

/** Motivos de la cola, en el orden en que se muestran. Un legible en la cola es un tipo deducido. */
const REASONS = [
  { key: 'DESCUADRE', label: 'Descuadres' },
  { key: 'DESCONOCIDO', label: 'Desconocidos' },
  { key: 'LEGIBLE', label: 'Tipo deducido' },
  { key: 'NO_LEGIBLE', label: 'No legibles' },
]

function Fields({ doc }) {
  if (!doc.campos_faltantes.length && !doc.campos_dudosos.length) return <span className="text-xs text-subtle">—</span>
  return (
    <span className="flex flex-wrap gap-1">
      {doc.campos_faltantes.map((c) => (
        <Tag key={c} tone="danger">
          {FIELD_LABELS[c]}
        </Tag>
      ))}
      {doc.campos_dudosos.map((c) => (
        <Tag key={c} tone="warning">
          {FIELD_LABELS[c]}
        </Tag>
      ))}
    </span>
  )
}

function Reason({ doc }) {
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <StatusBadge status={doc.observaciones} size="sm" />
      {doc.observaciones === 'LEGIBLE' && <Tag tone="brand">tipo deducido</Tag>}
    </span>
  )
}

function Rut({ value }) {
  return value === '1-9' ? <Tag tone="warning">ilegible</Tag> : <span className="tabular">{rut(value)}</span>
}

/** Cola de revisión humana: descuadres, tipos deducidos y desconocidos pendientes, los más antiguos primero. */
export default function Review() {
  const docs = useLoad(() => api.documents.list({ requiere_revision: 'true', orden: 'antiguos', limite: 500 }))
  const list = docs.data?.documentos
  const counts = REASONS.map((r) => ({ ...r, count: list?.filter((d) => d.observaciones === r.key).length ?? 0 })).filter(
    (r) => r.count > 0,
  )

  return (
    <div className="space-y-6 lg:space-y-8">
      <PageHeader
        eyebrow="Cola de trabajo"
        title={
          <>
            Revisión humana
            {docs.data && (
              <span className="rounded-md bg-brand-600 px-2 py-0.5 text-[15px] font-semibold text-white tabular shadow-brand">
                {docs.data.total}
              </span>
            )}
          </>
        }
        meta="Lo que la IA no pudo cerrar con certeza. Se atiende del más antiguo al más reciente."
        actions={
          list?.length > 0 && (
            <Button icon="scan" onClick={() => (window.location.hash = href('revision', list[0].id))}>
              Revisar el más antiguo
            </Button>
          )
        }
      />

      {counts.length > 0 && (
        <ul className="flex flex-wrap gap-2" aria-label="Pendientes por motivo">
          {counts.map((r) => (
            <li
              key={r.key}
              className="inline-flex items-center gap-2 rounded-control border border-line bg-canvas py-1.5 pr-3 pl-2 text-[13px] shadow-control"
            >
              <span className={`flex h-6 w-6 items-center justify-center rounded-md ${STATUS[r.key].className} ring-1 ring-inset`}>
                <Icon name={STATUS[r.key].icon} size={13} strokeWidth={2.1} />
              </span>
              <span className="text-muted">{r.label}</span>
              <span className="font-semibold text-ink tabular">{r.count}</span>
            </li>
          ))}
        </ul>
      )}

      <Card
        title="Pendientes"
        subtitle={docs.data ? `${docs.data.total} pendiente${docs.data.total === 1 ? '' : 's'} · los más antiguos primero` : undefined}
      >
        <ErrorBox message={docs.error} />
        {!docs.data && docs.loading && <Loading />}
        {list?.length === 0 && (
          <Empty icon="checkCircle" tone="success" title="Todo revisado">
            No hay documentos pendientes de revisión. Los nuevos aparecerán aquí cuando la IA necesite a una persona.
          </Empty>
        )}
        {list?.length > 0 && (
          <>
            {/* Móvil: una tarjeta por documento */}
            <ul className="-mx-5 -mb-5 divide-y divide-line border-t border-line sm:-mx-6 sm:-mb-6 md:hidden">
              {list.map((doc) => (
                <li key={doc.id}>
                  <a href={href('revision', doc.id)} className="flex items-start gap-3 px-5 py-4 active:bg-brand-25 sm:px-6">
                    <span className="min-w-0 flex-1 space-y-2">
                      <span className="flex flex-wrap items-baseline gap-x-2">
                        <span className="text-sm font-semibold text-ink">{DOC_TYPES[doc.tipo]}</span>
                        <span className="text-[13px] text-muted tabular">N° {doc.folio ?? '—'}</span>
                      </span>
                      <span className="block text-xs text-subtle">
                        {dateTime(doc.creado_en)} · RUT <Rut value={doc.rut_proveedor} />
                      </span>
                      <Reason doc={doc} />
                      <Fields doc={doc} />
                    </span>
                    <Icon name="chevronRight" size={18} className="mt-0.5 text-subtle" />
                  </a>
                </li>
              ))}
            </ul>

            {/* Escritorio: tabla */}
            <div className="-mx-5 -mb-5 hidden overflow-x-auto border-t border-line sm:-mx-6 sm:-mb-6 md:block">
              <table className="w-full min-w-[820px] text-left text-sm">
                <thead className="bg-surface/60">
                  <tr className="border-b border-line text-[11.5px] font-semibold tracking-[0.04em] text-subtle uppercase">
                    <th className="py-2.5 pr-3 pl-6 font-semibold">Subido</th>
                    <th className="px-3 py-2.5 font-semibold">Documento</th>
                    <th className="px-3 py-2.5 font-semibold">RUT proveedor</th>
                    <th className="px-3 py-2.5 font-semibold">Motivo</th>
                    <th className="px-3 py-2.5 font-semibold">Campos a revisar</th>
                    <th className="py-2.5 pr-6 pl-3">
                      <span className="sr-only">Abrir</span>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {list.map((doc, i) => (
                    <tr
                      key={doc.id}
                      onClick={() => (window.location.hash = href('revision', doc.id))}
                      className="group cursor-pointer transition-colors hover:bg-brand-25"
                    >
                      <td className="relative py-3 pr-3 pl-6 whitespace-nowrap text-muted tabular">
                        {i === 0 && <span aria-hidden="true" className="absolute inset-y-0 left-0 w-[3px] bg-brand-600" />}
                        {dateTime(doc.creado_en)}
                      </td>
                      <td className="px-3 py-3 whitespace-nowrap">
                        <a href={href('revision', doc.id)} className="font-medium text-ink group-hover:text-brand-700">
                          {DOC_TYPES[doc.tipo]}
                        </a>
                        <span className="ml-2 text-muted tabular">N° {doc.folio ?? '—'}</span>
                      </td>
                      <td className="px-3 py-3 whitespace-nowrap">
                        <Rut value={doc.rut_proveedor} />
                      </td>
                      <td className="px-3 py-3">
                        <Reason doc={doc} />
                      </td>
                      <td className="px-3 py-3">
                        <Fields doc={doc} />
                      </td>
                      <td className="py-3 pr-6 pl-3 text-right">
                        <Icon
                          name="chevronRight"
                          size={16}
                          className="ml-auto text-subtle transition-transform group-hover:translate-x-0.5 group-hover:text-brand-600"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>
    </div>
  )
}
