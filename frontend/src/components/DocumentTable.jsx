import { DOC_TYPES, clp, rut, shortDate } from '../format'
import { href } from '../hooks'
import Icon from './icons'
import { ReviewFlag, StatusBadge, Tag } from './ui'

/** Código del tipo (FC, CI, GD, DESC) en una pastilla de ancho fijo, para leer la columna de un vistazo. */
export function TypeCode({ tipo }) {
  return (
    <span
      title={DOC_TYPES[tipo]}
      className={`inline-flex h-6 min-w-[2.75rem] items-center justify-center rounded-md px-1.5 font-mono text-[11.5px] font-medium ring-1 ring-inset ${
        tipo === 'DESC' ? 'bg-slate-50 text-slate-700 ring-slate-600/25' : 'bg-surface text-ink ring-line-strong'
      }`}
    >
      {tipo}
    </span>
  )
}

function Rut({ value }) {
  return value === '1-9' ? (
    <span className="inline-flex items-center gap-1.5">
      1-9 <Tag tone="warning">ilegible</Tag>
    </span>
  ) : (
    rut(value)
  )
}

/** Tabla de documentos_procesados. Cada fila lleva al detalle. En móvil, una tarjeta por documento. */
export default function DocumentTable({ documents }) {
  return (
    <>
      <ul className="-mx-5 divide-y divide-line border-y border-line sm:-mx-6 md:hidden">
        {documents.map((doc) => (
          <li key={doc.id} className="relative">
            {doc.requiere_revision && <span aria-hidden="true" className="absolute inset-y-0 left-0 w-[3px] bg-brand-600" />}
            <a href={href('documentos', doc.id)} className="flex items-start gap-3 px-5 py-3.5 active:bg-brand-25 sm:px-6">
              <TypeCode tipo={doc.tipo} />
              <span className="min-w-0 flex-1">
                <span className="flex items-baseline justify-between gap-3">
                  <span className="truncate text-sm font-medium text-ink tabular">N° {doc.folio ?? '—'}</span>
                  <span className="text-sm font-semibold text-ink tabular">{clp(doc.total)}</span>
                </span>
                <span className="mt-0.5 block text-xs text-muted tabular">
                  <Rut value={doc.rut_proveedor} /> · {shortDate(doc.fecha)}
                </span>
                <span className="mt-2 flex flex-wrap gap-1.5">
                  <StatusBadge status={doc.observaciones} size="sm" />
                  {doc.requiere_revision && <ReviewFlag size="sm" label="Revisión" />}
                </span>
              </span>
            </a>
          </li>
        ))}
      </ul>

      <div className="-mx-5 hidden overflow-x-auto border-y border-line sm:-mx-6 md:block">
        <table className="w-full min-w-[960px] text-left text-sm">
          <thead className="bg-surface/60">
            <tr className="border-b border-line text-[11.5px] tracking-[0.04em] text-subtle uppercase">
              <th className="py-2.5 pr-3 pl-6 font-semibold">Tipo</th>
              <th className="px-3 py-2.5 font-semibold">Folio</th>
              <th className="px-3 py-2.5 font-semibold">RUT proveedor</th>
              <th className="px-3 py-2.5 font-semibold">Fecha</th>
              <th className="px-3 py-2.5 text-right font-semibold">Neto</th>
              <th className="px-3 py-2.5 text-right font-semibold">IVA</th>
              <th className="px-3 py-2.5 text-right font-semibold">Impuestos</th>
              <th className="px-3 py-2.5 text-right font-semibold">Total</th>
              <th className="px-3 py-2.5 text-center font-semibold">Firma</th>
              <th className="py-2.5 pr-6 pl-3 font-semibold">Observaciones</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {documents.map((doc) => (
              <tr
                key={doc.id}
                onClick={() => (window.location.hash = href('documentos', doc.id))}
                className={`group cursor-pointer whitespace-nowrap transition-colors hover:bg-brand-25 ${
                  doc.requiere_revision ? 'bg-brand-25/60' : ''
                }`}
              >
                <td className="relative py-2.5 pr-3 pl-6">
                  {doc.requiere_revision && <span aria-hidden="true" className="absolute inset-y-0 left-0 w-[3px] bg-brand-600" />}
                  <a href={href('documentos', doc.id)} className="rounded-md" aria-label={`${DOC_TYPES[doc.tipo]} ${doc.folio ?? ''}`}>
                    <TypeCode tipo={doc.tipo} />
                  </a>
                </td>
                <td className="px-3 py-2.5 font-medium text-ink tabular group-hover:text-brand-700">{doc.folio ?? '—'}</td>
                <td className="px-3 py-2.5 tabular">
                  <Rut value={doc.rut_proveedor} />
                </td>
                <td className="px-3 py-2.5 text-muted tabular">{shortDate(doc.fecha)}</td>
                <td className="px-3 py-2.5 text-right text-muted tabular">{clp(doc.total_neto)}</td>
                <td className="px-3 py-2.5 text-right text-muted tabular">{clp(doc.iva)}</td>
                <td className="px-3 py-2.5 text-right text-muted tabular">{clp(doc.impuestos)}</td>
                <td className="px-3 py-2.5 text-right font-semibold text-ink tabular">{clp(doc.total)}</td>
                <td className="px-3 py-2.5 text-center">
                  {doc.firma ? (
                    <Icon name="check" size={16} strokeWidth={2.2} className="mx-auto text-success-600" />
                  ) : (
                    <span className="text-xs text-subtle">No</span>
                  )}
                </td>
                <td className="py-2.5 pr-6 pl-3">
                  <span className="inline-flex items-center gap-1.5">
                    <StatusBadge status={doc.observaciones} size="sm" />
                    {doc.requiere_revision && <ReviewFlag size="sm" label="Revisión" />}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
