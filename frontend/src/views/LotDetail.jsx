import { useState } from 'react'
import { api } from '../api'
import DocumentTable from '../components/DocumentTable'
import Icon from '../components/icons'
import { Button, Card, Empty, ErrorBox, Loading, Segmented, StatusBadge } from '../components/ui'
import { STATUS, dateTime, documentStatus, fileSize } from '../format'
import { href, useLoad, usePolling } from '../hooks'

const RUNNING = new Set(['RECIBIDO', 'EN_PROCESO'])
const FILTERS = ['PROCESADO', 'NO_LEGIBLE', 'DESCUADRE', 'DESCONOCIDO', 'EN_PROCESO', 'FALLIDO']

/** Un lote: progreso, archivos y páginas, y los documentos que los agentes encontraron. */
export default function LotDetail({ id }) {
  const lot = useLoad(() => api.submissions.get(id), id)
  const [filter, setFilter] = useState('all')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const running = RUNNING.has(lot.data?.status)
  usePolling(lot.reload, running)

  if (!lot.data) {
    return lot.loading ? <Loading rows={4} /> : <ErrorBox message={lot.error} />
  }
  const { files, documents } = lot.data
  const pages = files.flatMap((f) => f.pages)
  const classified = pages.filter((p) => p.classification_status === 'OK').length
  const counts = Object.fromEntries(FILTERS.map((s) => [s, documents.filter((d) => documentStatus(d) === s).length]))
  const shown = filter === 'all' ? documents : documents.filter((d) => documentStatus(d) === filter)
  const pageErrors = pages.filter((p) => p.classification_status === 'ERROR')
  const finished = documents.filter((d) => d.technical_status !== 'EN_PROCESO').length
  // Avance: cada página se clasifica y cada documento se extrae y valida
  const progress = (classified + finished) / Math.max(1, pages.length + documents.length)

  async function reprocess() {
    setBusy(true)
    setError(null)
    try {
      await api.submissions.process(id)
      lot.reload()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <a href={href('lotes')} className="inline-flex items-center gap-1.5 text-[13px] text-muted hover:text-brand-700">
            <Icon name="arrowLeft" size={14} /> Lotes
          </a>
          <h2 className="mt-1 flex items-center gap-3 text-xl font-semibold tracking-tight">
            Lote del {dateTime(lot.data.received_at)} <StatusBadge status={lot.data.status} />
          </h2>
        </div>
        {!running && lot.data.status === 'COMPLETADO_CON_ERRORES' && (
          <Button variant="secondary" icon="refresh" disabled={busy} onClick={reprocess}>
            {busy ? 'Reintentando…' : 'Reintentar lo pendiente'}
          </Button>
        )}
      </div>

      <ErrorBox message={error} />

      {running && (
        <div className="rounded-card border border-brand-200 bg-brand-50 p-4">
          <p className="text-sm font-medium text-brand-800">
            Los agentes están trabajando: {classified} de {pages.length} página{pages.length === 1 ? '' : 's'} clasificada
            {pages.length === 1 ? '' : 's'} · {finished} de {documents.length} documento{documents.length === 1 ? '' : 's'}{' '}
            terminado{documents.length === 1 ? '' : 's'}.
          </p>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-brand-100">
            <div
              className="h-full rounded-full bg-brand-600 transition-all duration-500"
              style={{ width: `${Math.max(5, progress * 100)}%` }}
            />
          </div>
          <p className="mt-2 text-xs text-brand-700">Con el modelo gratuito, cada página y cada documento tardan entre 15 y 60 segundos.</p>
        </div>
      )}

      {pageErrors.length > 0 && !running && (
        <ErrorBox message={`No se pudieron clasificar ${pageErrors.length} página(s): ${pageErrors[0].classification_error}`} />
      )}

      <Card
        title="Documentos"
        subtitle={`${documents.length} documento${documents.length === 1 ? '' : 's'} en ${pages.length} página${pages.length === 1 ? '' : 's'}`}
        action={
          documents.length > 0 && (
            <Segmented
              size="sm"
              value={filter}
              onChange={setFilter}
              options={[
                { value: 'all', label: 'Todos', count: documents.length },
                ...FILTERS.filter((s) => counts[s]).map((s) => ({ value: s, label: STATUS[s].label, count: counts[s] })),
              ]}
            />
          )
        }
      >
        {documents.length === 0 ? (
          <Empty icon="file" title={running ? 'Buscando documentos…' : 'Sin documentos'}>
            {running ? 'Aparecerán aquí a medida que se clasifiquen las páginas.' : 'No se encontraron documentos en este lote.'}
          </Empty>
        ) : (
          <DocumentTable documents={shown} />
        )}
      </Card>

      <Card title="Archivos" subtitle="Originales tal como llegaron y sus páginas">
        <ul className="space-y-4">
          {files.map((file) => (
            <li key={file.id}>
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <Icon name={file.content_type === 'application/pdf' ? 'file' : 'image'} size={16} className="text-subtle" />
                <a href={api.fileUrl(file.id)} target="_blank" rel="noreferrer" className="font-medium hover:text-brand-700">
                  {file.original_name}
                </a>
                <span className="text-xs text-subtle">{fileSize(file.size_bytes)}</span>
                {file.preprocess_status !== 'LISTO' && <StatusBadge status={file.preprocess_status} size="sm" />}
              </div>
              {file.preprocess_error && <p className="mt-1 text-xs text-danger-700">{file.preprocess_error}</p>}
              {file.pages.length > 0 && (
                <div className="mt-2 flex gap-2 overflow-x-auto pb-1">
                  {file.pages.map((page) => (
                    <a
                      key={page.id}
                      href={api.pageImageUrl(page.id)}
                      target="_blank"
                      rel="noreferrer"
                      title={page.classification_error ?? `Página ${page.page_number}`}
                      className="group relative shrink-0"
                    >
                      <img
                        src={api.pageImageUrl(page.id)}
                        alt={`Página ${page.page_number}`}
                        loading="lazy"
                        className="h-28 w-auto rounded-md border border-line object-cover group-hover:border-brand-300"
                      />
                      <span className="absolute right-1 bottom-1 left-1 flex items-center justify-between rounded bg-canvas/90 px-1.5 py-0.5 text-[10px] font-medium">
                        {page.page_number}
                        <span
                          className={`h-1.5 w-1.5 rounded-full ${
                            page.classification_status === 'OK'
                              ? 'bg-success-600'
                              : page.classification_status === 'ERROR'
                                ? 'bg-danger-600'
                                : 'bg-line-strong'
                          }`}
                        />
                      </span>
                    </a>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}
