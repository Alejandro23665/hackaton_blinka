import { DOC_TYPES, clp, rut, shortDate } from '../format'
import { href } from '../hooks'
import Icon from './icons'
import { StatusBadge, Tag } from './ui'

/** Tabla de documentos_procesados. Cada fila lleva al detalle. */
export default function DocumentTable({ documents }) {
  return (
    <div className="-mx-5 overflow-x-auto sm:-mx-6">
      <table className="w-full min-w-[960px] text-left text-sm">
        <thead>
          <tr className="border-b border-line text-xs text-subtle">
            <th className="px-5 py-2.5 font-medium sm:pl-6">Tipo</th>
            <th className="px-3 py-2.5 font-medium">Folio</th>
            <th className="px-3 py-2.5 font-medium">RUT proveedor</th>
            <th className="px-3 py-2.5 font-medium">Fecha</th>
            <th className="px-3 py-2.5 text-right font-medium">Neto</th>
            <th className="px-3 py-2.5 text-right font-medium">IVA</th>
            <th className="px-3 py-2.5 text-right font-medium">Impuestos</th>
            <th className="px-3 py-2.5 text-right font-medium">Total</th>
            <th className="px-3 py-2.5 text-center font-medium">Firma</th>
            <th className="px-5 py-2.5 font-medium sm:pr-6">Observaciones</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {documents.map((doc) => (
            <tr
              key={doc.id}
              onClick={() => (window.location.hash = href('documentos', doc.id))}
              className={`cursor-pointer whitespace-nowrap transition-colors hover:bg-brand-50/60 ${
                doc.requiere_revision ? 'bg-warning-50/40' : ''
              }`}
            >
              <td className="px-5 py-3 sm:pl-6">
                <a href={href('documentos', doc.id)} className="font-medium text-ink hover:text-brand-700" title={DOC_TYPES[doc.tipo]}>
                  {doc.tipo}
                </a>
              </td>
              <td className="px-3 py-3 tabular">{doc.folio ?? '—'}</td>
              <td className="px-3 py-3 tabular">
                {doc.rut_proveedor === '1-9' ? (
                  <span className="inline-flex items-center gap-1.5">
                    1-9 <Tag tone="warning">ilegible</Tag>
                  </span>
                ) : (
                  rut(doc.rut_proveedor)
                )}
              </td>
              <td className="px-3 py-3 text-muted">{shortDate(doc.fecha)}</td>
              <td className="px-3 py-3 text-right tabular">{clp(doc.total_neto)}</td>
              <td className="px-3 py-3 text-right tabular">{clp(doc.iva)}</td>
              <td className="px-3 py-3 text-right tabular">{clp(doc.impuestos)}</td>
              <td className="px-3 py-3 text-right font-medium tabular">{clp(doc.total)}</td>
              <td className="px-3 py-3 text-center">
                {doc.firma ? (
                  <Icon name="check" size={16} className="mx-auto text-success-600" />
                ) : (
                  <span className="text-xs text-muted">No</span>
                )}
              </td>
              <td className="px-5 py-3 sm:pr-6">
                <span className="inline-flex items-center gap-2">
                  <StatusBadge status={doc.observaciones} size="sm" />
                  {doc.requiere_revision && <Icon name="alert" size={14} className="text-warning-700" />}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
