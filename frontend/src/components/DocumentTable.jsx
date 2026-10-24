import { DOC_TYPES, clp, documentStatus, rut, shortDate } from '../format'
import { href } from '../hooks'
import Icon from './icons'
import { StatusBadge, Tag } from './ui'

/**
 * Tabla de documentos (lote o bandeja). Cada fila lleva al detalle.
 * `documents`: elementos con doc_type, estado, RUT, número, fecha, total y alertas.
 */
export default function DocumentTable({ documents, showReceived = false }) {
  return (
    <div className="-mx-5 overflow-x-auto sm:-mx-6">
      <table className="w-full min-w-[780px] text-left text-sm">
        <thead>
          <tr className="border-b border-line text-xs text-subtle">
            <th className="px-5 py-2.5 font-medium sm:pl-6">Tipo</th>
            <th className="px-3 py-2.5 font-medium">Estado</th>
            <th className="px-3 py-2.5 font-medium">RUT prestador</th>
            <th className="px-3 py-2.5 font-medium">Número</th>
            <th className="px-3 py-2.5 font-medium">{showReceived ? 'Recibido' : 'Emisión'}</th>
            <th className="px-3 py-2.5 text-right font-medium">Total</th>
            <th className="px-3 py-2.5 text-center font-medium">Firma</th>
            <th className="px-5 py-2.5 text-right font-medium sm:pr-6">Alertas</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {documents.map((doc) => {
            const issues = doc.issue_count ?? doc.issues?.length ?? 0
            return (
              <tr
                key={doc.id}
                onClick={() => (window.location.hash = href('documentos', doc.id))}
                className="cursor-pointer whitespace-nowrap transition-colors hover:bg-brand-50/60"
              >
                <td className="px-5 py-3 sm:pl-6">
                  <a href={href('documentos', doc.id)} className="font-medium text-ink hover:text-brand-700">
                    {DOC_TYPES[doc.doc_type] ?? 'Clasificando…'}
                  </a>
                </td>
                <td className="px-3 py-3">
                  <StatusBadge status={documentStatus(doc)} size="sm" />
                </td>
                <td className="px-3 py-3 tabular">
                  {doc.rut_is_substitute ? (
                    <span className="inline-flex items-center gap-1.5">
                      1-9 <Tag tone="warning">sustituto</Tag>
                    </span>
                  ) : (
                    rut(doc.provider_rut)
                  )}
                </td>
                <td className="px-3 py-3 tabular">{doc.document_number ?? '—'}</td>
                <td className="px-3 py-3 whitespace-nowrap text-muted">
                  {showReceived ? shortDate(doc.received_at) : shortDate(doc.issue_date)}
                </td>
                <td className="px-3 py-3 text-right tabular">{clp(doc.total_amount)}</td>
                <td className="px-3 py-3 text-center">
                  {doc.has_signature == null ? (
                    <span className="text-xs text-subtle">—</span>
                  ) : doc.has_signature ? (
                    <Icon name="check" size={16} className="mx-auto text-success-600" />
                  ) : (
                    <span className="text-xs text-muted">No</span>
                  )}
                </td>
                <td className="px-5 py-3 text-right sm:pr-6">
                  {issues > 0 ? (
                    <span className="inline-flex items-center gap-1 text-xs font-medium text-warning-700">
                      <Icon name="alert" size={14} /> {issues}
                    </span>
                  ) : (
                    <span className="text-xs text-subtle">—</span>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
