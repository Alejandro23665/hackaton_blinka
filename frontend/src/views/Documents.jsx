import { useEffect, useRef } from 'react'
import { api } from '../api'
import DocumentTable from '../components/DocumentTable'
import Icon from '../components/icons'
import { inputClass } from '../components/styles'
import { Button, Card, Empty, ErrorBox, Loading, PageHeader, Segmented } from '../components/ui'
import { DOC_TYPES, STATUS, dateTime } from '../format'
import { href, useLoad, useViewState } from '../hooks'

const PAGE_SIZE = 50
const OBSERVATIONS = ['LEGIBLE', 'NO_LEGIBLE', 'DESCUADRE', 'DESCONOCIDO']

/** Cada recuadro aplica un filtro: por observaciones o "requieren revisión". */
const TILES = [
  { key: 'todos', label: 'Total', hint: 'Documentos guardados', icon: 'layers', accent: 'text-ink', bar: 'bg-ink', filter: {} },
  { key: 'LEGIBLE', label: 'Legibles', hint: 'Datos completos y montos cuadrados', filter: { observaciones: 'LEGIBLE' } },
  { key: 'NO_LEGIBLE', label: 'No legibles', hint: 'Falta un dato o no fue fiable', filter: { observaciones: 'NO_LEGIBLE' } },
  { key: 'DESCUADRE', label: 'Descuadres', hint: 'La suma no da el total', filter: { observaciones: 'DESCUADRE' } },
  { key: 'DESCONOCIDO', label: 'Desconocidos', hint: 'Tipo no reconocido', filter: { observaciones: 'DESCONOCIDO' } },
  { key: 'revision', label: 'Requieren revisión', hint: 'Pendientes de una persona', icon: 'flag', accent: 'text-brand-700', bar: 'bg-brand-600', filter: { revision: true } },
]

function tileCount(key, summary) {
  if (!summary) return 0
  if (key === 'todos') return summary.total
  if (key === 'revision') return summary.requieren_revision
  return summary.por_observaciones[key] ?? 0
}

/** Icono, color del número y de la marca activa de cada recuadro (los estados usan los de su etiqueta). */
function tileStyle(tile) {
  const s = STATUS[tile.key]
  if (!s) return { icon: tile.icon, accent: tile.accent, bar: tile.bar }
  return { icon: s.icon, accent: s.className.split(' ').find((c) => c.startsWith('text-')), bar: s.dot }
}

/** Bandeja: documentos_procesados con filtros por tipo, observaciones, revisión, carpeta y búsqueda. */
export default function Documents() {
  // Se recuerdan al ir a un documento y volver
  const [tipo, setTipo] = useViewState('documentos.tipo', '')
  const [observaciones, setObservaciones] = useViewState('documentos.observaciones', '')
  const [revision, setRevision] = useViewState('documentos.revision', false)
  const [carpeta, setCarpeta] = useViewState('documentos.carpeta', '')
  const [search, setSearch] = useViewState('documentos.busqueda', '')
  const [query, setQuery] = useViewState('documentos.consulta', '')
  const [page, setPage] = useViewState('documentos.pagina', 0)

  // La búsqueda se aplica tras una pausa al escribir, no en cada tecla
  useEffect(() => {
    const timer = setTimeout(() => setQuery(search.trim()), 300)
    return () => clearTimeout(timer)
  }, [search, setQuery])
  // Cualquier filtro nuevo vuelve a la primera página (al volver a la vista, los filtros no cambian:
  // se conserva la página en que se dejó)
  const filters = JSON.stringify([tipo, observaciones, revision, carpeta, query])
  const previousFilters = useRef(filters)
  useEffect(() => {
    if (previousFilters.current !== filters) setPage(0)
    previousFilters.current = filters
  }, [filters, setPage])

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
    <div className="space-y-6 lg:space-y-8">
      <PageHeader
        eyebrow="Archivo"
        title="Documentos"
        meta="Todo lo que se procesó y guardó. Toca un estado para filtrar."
      />

      {/* Riel de estados: cada uno filtra la tabla */}
      <div className="-mx-4 overflow-x-auto px-4 scrollbar-none sm:mx-0 sm:px-0">
        <div className="flex min-w-max gap-px overflow-hidden rounded-card border border-line bg-line shadow-card sm:grid sm:min-w-0 sm:grid-cols-3 xl:grid-cols-6">
          {TILES.map((tile) => {
            const style = tileStyle(tile)
            const active = activeTile === tile.key
            return (
              <button
                key={tile.key}
                type="button"
                onClick={() => applyTile(tile)}
                aria-pressed={active}
                className={`relative w-40 px-4 py-3.5 text-left transition-colors sm:w-auto ${
                  active ? 'bg-brand-25' : 'bg-canvas hover:bg-surface'
                }`}
              >
                <span
                  aria-hidden="true"
                  className={`absolute inset-x-0 bottom-0 h-[2px] transition-opacity duration-150 ${style.bar} ${active ? 'opacity-100' : 'opacity-0'}`}
                />
                <span className="flex items-center gap-1.5 text-[13px] font-medium text-muted">
                  <Icon name={style.icon} size={14} strokeWidth={2} className={style.accent} />
                  {tile.label}
                </span>
                <span className={`mt-1 block text-2xl font-semibold tracking-[-0.02em] tabular ${style.accent}`}>
                  {tileCount(tile.key, summary.data)}
                </span>
                <span className="mt-0.5 block truncate text-xs text-subtle">{tile.hint}</span>
              </button>
            )
          })}
        </div>
      </div>

      <Card
        title={filtered ? 'Resultados' : 'Todos los documentos'}
        subtitle={docs.data ? `${total} ${filtered ? 'con estos filtros' : 'en total'}` : undefined}
        action={
          <div className="relative w-full sm:w-72">
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
        <div className="mb-5 flex flex-wrap items-center gap-2">
          <Segmented
            size="sm"
            value={tipo}
            onChange={setTipo}
            options={[
              { value: '', label: 'Todos los tipos' },
              ...['FC', 'CI', 'GD', 'DESC'].map((value) => ({
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
        {!docs.data && docs.loading && <Loading rows={6} />}
        {docs.data?.documentos.length === 0 && (
          <Empty
            icon={filtered ? 'search' : 'inbox'}
            title={filtered ? 'Sin resultados' : 'Aún no hay documentos'}
            action={
              !filtered && (
                <Button variant="secondary" icon="upload" onClick={() => (window.location.hash = href('subir'))}>
                  Subir documentos
                </Button>
              )
            }
          >
            {filtered
              ? 'Ningún documento cumple los filtros. Prueba con otro estado, tipo o carpeta, o borra la búsqueda.'
              : 'Aún no se han guardado documentos. Cuando subas archivos, aparecerán aquí.'}
          </Empty>
        )}
        {docs.data?.documentos.length > 0 && (
          <div className={`transition-opacity duration-150 ${docs.loading ? 'opacity-60' : ''}`}>
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
          </div>
        )}
      </Card>
    </div>
  )
}
