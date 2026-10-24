import { useEffect, useState } from 'react'
import { api } from '../api'
import DocumentTable from '../components/DocumentTable'
import Icon from '../components/icons'
import { inputClass } from '../components/styles'
import { Card, Empty, ErrorBox, Loading, Segmented } from '../components/ui'
import { DOC_TYPES, STATUS } from '../format'
import { useLoad } from '../hooks'

const STATUSES = ['PROCESADO', 'NO_LEGIBLE', 'DESCUADRE', 'DESCONOCIDO', 'EN_PROCESO', 'FALLIDO']
const TILES = [
  { status: 'PROCESADO', hint: 'Datos completos y montos cuadrados', tone: 'text-success-700' },
  { status: 'NO_LEGIBLE', hint: 'Faltan datos obligatorios', tone: 'text-warning-700' },
  { status: 'DESCUADRE', hint: 'La suma no da el total', tone: 'text-danger-700' },
  { status: 'DESCONOCIDO', hint: 'No es un tipo admitido', tone: 'text-muted' },
]

/** Bandeja: todos los documentos con su resultado vigente, filtrables por estado, tipo y búsqueda. */
export default function Documents() {
  const [status, setStatus] = useState('')
  const [docType, setDocType] = useState('')
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')

  // La búsqueda se aplica tras una pausa al escribir, no en cada tecla
  useEffect(() => {
    const timer = setTimeout(() => setQuery(search.trim()), 300)
    return () => clearTimeout(timer)
  }, [search])

  const stats = useLoad(() => api.documents.stats())
  const docs = useLoad(() => api.documents.list({ status, doc_type: docType, q: query }), `${status}|${docType}|${query}`)
  const byStatus = stats.data?.by_status ?? {}

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {TILES.map((tile) => (
          <button
            key={tile.status}
            type="button"
            onClick={() => setStatus(status === tile.status ? '' : tile.status)}
            className={`rounded-card border bg-canvas p-4 text-left shadow-card transition-colors ${
              status === tile.status ? 'border-brand-600 ring-4 ring-brand-100' : 'border-line hover:border-brand-300'
            }`}
          >
            <p className="text-[13px] font-medium text-muted">{STATUS[tile.status].label}</p>
            <p className={`mt-1 text-2xl font-semibold tabular ${tile.tone}`}>{byStatus[tile.status] ?? 0}</p>
            <p className="mt-0.5 text-xs text-subtle">{tile.hint}</p>
          </button>
        ))}
      </div>

      <Card
        title="Documentos"
        subtitle={stats.data ? `${stats.data.total} en total` : undefined}
        action={
          <div className="relative w-full sm:w-64">
            <Icon name="search" size={16} className="pointer-events-none absolute top-3 left-3 text-subtle" />
            <input
              type="search"
              aria-label="Buscar por RUT o número"
              placeholder="Buscar RUT o número"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className={`${inputClass} pl-9`}
            />
          </div>
        }
      >
        <div className="mb-4 flex flex-wrap gap-2">
          <Segmented
            size="sm"
            value={status}
            onChange={setStatus}
            options={[
              { value: '', label: 'Todos los estados' },
              ...STATUSES.map((s) => ({ value: s, label: STATUS[s].label, count: byStatus[s] ?? 0 })).filter(
                (o) => o.count > 0 || o.value === status,
              ),
            ]}
          />
          <Segmented
            size="sm"
            value={docType}
            onChange={setDocType}
            options={[
              { value: '', label: 'Todos los tipos' },
              ...Object.entries(DOC_TYPES).map(([value, label]) => ({ value, label, count: stats.data?.by_type[value] ?? 0 })),
            ]}
          />
        </div>

        <ErrorBox message={docs.error} />
        {!docs.data && docs.loading && <Loading />}
        {docs.data?.length === 0 && (
          <Empty icon="search" title="Sin resultados">
            {status || docType || query ? 'Ningún documento cumple los filtros.' : 'Aún no se han procesado documentos.'}
          </Empty>
        )}
        {docs.data?.length > 0 && <DocumentTable documents={docs.data} showReceived />}
      </Card>
    </div>
  )
}
