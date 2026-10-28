import { useEffect, useState } from 'react'
import { api } from '../api'
import DocumentTable from '../components/DocumentTable'
import Icon from '../components/icons'
import { inputClass } from '../components/styles'
import { Button, Card, Empty, ErrorBox, Loading, Segmented } from '../components/ui'
import { DOC_TYPES, STATUS, dateTime } from '../format'
import { useLoad } from '../hooks'

const PAGE_SIZE = 50
const OBSERVATIONS = ['LEGIBLE', 'NO_LEGIBLE', 'DESCUADRE']

/** Cada recuadro aplica un filtro: por observaciones o "requieren revisión". */
const TILES = [
  { key: 'todos', label: 'Total', hint: 'Documentos guardados', tone: 'text-ink', filter: {} },
  { key: 'LEGIBLE', label: 'Legibles', hint: 'Datos completos y montos cuadrados', tone: 'text-success-700', filter: { observaciones: 'LEGIBLE' } },
  { key: 'NO_LEGIBLE', label: 'No legibles', hint: 'Falta un dato o no fue fiable', tone: 'text-warning-700', filter: { observaciones: 'NO_LEGIBLE' } },
  { key: 'DESCUADRE', label: 'Descuadres', hint: 'La suma no da el total', tone: 'text-danger-700', filter: { observaciones: 'DESCUADRE' } },
  { key: 'revision', label: 'Requieren revisión', hint: 'No legibles + descuadres', tone: 'text-warning-700', filter: { revision: true } },
]

function tileCount(key, summary) {
  if (!summary) return 0
  if (key === 'todos') return summary.total
  if (key === 'revision') return summary.requieren_revision
  return summary.por_observaciones[key] ?? 0
}

/** Bandeja: documentos_procesados con filtros por tipo, observaciones, revisión, carpeta y búsqueda. */
export default function Documents() {
  const [tipo, setTipo] = useState('')
  const [observaciones, setObservaciones] = useState('')
  const [revision, setRevision] = useState(false)
  const [carpeta, setCarpeta] = useState('')
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(0)

  // La búsqueda se aplica tras una pausa al escribir, no en cada tecla
  useEffect(() => {
    const timer = setTimeout(() => setQuery(search.trim()), 300)
    return () => clearTimeout(timer)
  }, [search])
  // Cualquier filtro nuevo vuelve a la primera página
  useEffect(() => setPage(0), [tipo, observaciones, revision, carpeta, query])

  const summary = useLoad(() => api.documents.summary())
  const folders = useLoad(() => api.folders())
  const params = {
    carpeta,
    tipo,
    observaciones,
    requiere_revision: revision ? 'true' : '',
    q: query,
    limite: PAGE_SIZE,
    desde: page * PAGE_SIZE,
  }
  const docs = useLoad(() => api.documents.list(params), JSON.stringify(params))
  const total = docs.data?.total ?? 0
  const filtered = tipo || observaciones || revision || carpeta || query

  function applyTile(tile) {
    setObservaciones(tile.filter.observaciones ?? '')
    setRevision(Boolean(tile.filter.revision))
  }
  const activeTile = revision ? 'revision' : observaciones || 'todos'

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {TILES.map((tile) => (
          <button
            key={tile.key}
            type="button"
            onClick={() => applyTile(tile)}
            aria-pressed={activeTile === tile.key}
            className={`rounded-card border bg-canvas p-4 text-left shadow-card transition-colors ${
              activeTile === tile.key ? 'border-brand-600 ring-4 ring-brand-100' : 'border-line hover:border-brand-300'
            }`}
          >
            <p className="text-[13px] font-medium text-muted">{tile.label}</p>
            <p className={`mt-1 text-2xl font-semibold tabular ${tile.tone}`}>{tileCount(tile.key, summary.data)}</p>
            <p className="mt-0.5 text-xs text-subtle">{tile.hint}</p>
          </button>
        ))}
      </div>

      <Card
        title="Documentos"
        subtitle={docs.data ? `${total} ${filtered ? 'con estos filtros' : 'en total'}` : undefined}
        action={
          <div className="relative w-full sm:w-64">
            <Icon name="search" size={16} className="pointer-events-none absolute top-3 left-3 text-subtle" />
            <input
              type="search"
              aria-label="Buscar por RUT o folio"
              placeholder="Buscar RUT o folio"
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
            value={tipo}
            onChange={setTipo}
            options={[
              { value: '', label: 'Todos los tipos' },
              ...['FC', 'CI', 'GD'].map((value) => ({
                value,
                label: DOC_TYPES[value],
                count: summary.data?.por_tipo[value] ?? 0,
              })),
            ]}
          />
          <Segmented
            size="sm"
            value={observaciones}
            onChange={(value) => {
              setObservaciones(value)
              setRevision(false)
            }}
            options={[{ value: '', label: 'Todas las observaciones' }, ...OBSERVATIONS.map((value) => ({ value, label: STATUS[value].label }))]}
          />
          <Segmented
            size="sm"
            value={revision}
            onChange={(value) => {
              setRevision(value)
              if (value) setObservaciones('')
            }}
            options={[
              { value: false, label: 'Todos' },
              { value: true, label: 'Solo requieren revisión' },
            ]}
          />
          {folders.data?.length > 0 && (
            <div className="relative w-full sm:w-72">
              <Icon name="folder" size={16} className="pointer-events-none absolute top-3 left-3 text-subtle" />
              <select
                aria-label="Filtrar por carpeta"
                value={carpeta}
                onChange={(e) => setCarpeta(e.target.value)}
                className={`${inputClass} pl-9`}
              >
                <option value="">Todas las carpetas</option>
                {folders.data.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.nombre} · {dateTime(f.subida_en)} · {f.documentos} doc.
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        <ErrorBox message={docs.error} />
        {!docs.data && docs.loading && <Loading />}
        {docs.data?.documentos.length === 0 && (
          <Empty icon="search" title="Sin resultados">
            {filtered ? 'Ningún documento cumple los filtros.' : 'Aún no se han guardado documentos.'}
          </Empty>
        )}
        {docs.data?.documentos.length > 0 && (
          <>
            <DocumentTable documents={docs.data.documentos} />
            {total > PAGE_SIZE && (
              <div className="mt-4 flex items-center justify-between gap-3 text-[13px] text-muted">
                <span className="tabular">
                  {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} de {total}
                </span>
                <div className="flex gap-2">
                  <Button variant="secondary" size="sm" disabled={page === 0} onClick={() => setPage(page - 1)}>
                    Anterior
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={(page + 1) * PAGE_SIZE >= total}
                    onClick={() => setPage(page + 1)}
                  >
                    Siguiente
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  )
}
