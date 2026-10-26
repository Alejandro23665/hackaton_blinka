import { api } from '../api'
import Icon from '../components/icons'
import { Card, Empty, ErrorBox, Loading, StatusBadge, Tag } from '../components/ui'
import { DOC_TYPES, FIELD_LABELS, dateTime, rut } from '../format'
import { href, useLoad } from '../hooks'

/** Cola de revisión humana: no legibles y descuadres pendientes, los más antiguos primero. */
export default function Review() {
  const docs = useLoad(() => api.documents.list({ requiere_revision: 'true', orden: 'antiguos', limite: 500 }))
  const list = docs.data?.documentos

  return (
    <Card
      title="Revisión humana"
      subtitle={
        docs.data
          ? `${docs.data.total} pendiente${docs.data.total === 1 ? '' : 's'} · los más antiguos primero`
          : 'Documentos no legibles o con descuadre'
      }
    >
      <ErrorBox message={docs.error} />
      {!docs.data && docs.loading && <Loading />}
      {list?.length === 0 && (
        <Empty icon="check" title="Todo revisado">
          No hay documentos pendientes de revisión.
        </Empty>
      )}
      {list?.length > 0 && (
        <div className="-mx-5 overflow-x-auto sm:-mx-6">
          <table className="w-full min-w-[820px] text-left text-sm">
            <thead>
              <tr className="border-b border-line text-xs text-subtle">
                <th className="px-5 py-2.5 font-medium sm:pl-6">Subido</th>
                <th className="px-3 py-2.5 font-medium">Tipo</th>
                <th className="px-3 py-2.5 font-medium">Folio</th>
                <th className="px-3 py-2.5 font-medium">RUT proveedor</th>
                <th className="px-3 py-2.5 font-medium">Observaciones</th>
                <th className="px-3 py-2.5 font-medium">Campos a revisar</th>
                <th className="px-5 py-2.5 sm:pr-6" />
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {list.map((doc) => (
                <tr
                  key={doc.id}
                  onClick={() => (window.location.hash = href('revision', doc.id))}
                  className="cursor-pointer transition-colors hover:bg-brand-50/60"
                >
                  <td className="px-5 py-3 whitespace-nowrap text-muted sm:pl-6">{dateTime(doc.creado_en)}</td>
                  <td className="px-3 py-3 whitespace-nowrap">
                    <a href={href('revision', doc.id)} className="font-medium text-ink hover:text-brand-700">
                      {DOC_TYPES[doc.tipo]}
                    </a>
                  </td>
                  <td className="px-3 py-3 tabular">{doc.folio ?? '—'}</td>
                  <td className="px-3 py-3 whitespace-nowrap tabular">
                    {doc.rut_proveedor === '1-9' ? <Tag tone="warning">ilegible</Tag> : rut(doc.rut_proveedor)}
                  </td>
                  <td className="px-3 py-3">
                    <StatusBadge status={doc.observaciones} size="sm" />
                  </td>
                  <td className="px-3 py-3">
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
                      {!doc.campos_faltantes.length && !doc.campos_dudosos.length && (
                        <span className="text-xs text-subtle">—</span>
                      )}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-right sm:pr-6">
                    <Icon name="chevronRight" size={16} className="ml-auto text-subtle" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
