import { api } from '../api'
import UploadZone from '../components/UploadZone'
import { Card, Empty, ErrorBox, Loading, StatusBadge } from '../components/ui'
import { dateTime } from '../format'
import { href, useLoad, usePolling } from '../hooks'
import Icon from '../components/icons'

const RUNNING = new Set(['RECIBIDO', 'EN_PROCESO'])

/** Inicio: subir un lote y ver los lotes recientes. */
export default function Lots() {
  const lots = useLoad(() => api.submissions.list())
  usePolling(lots.reload, lots.data?.some((lot) => RUNNING.has(lot.status)))

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <UploadZone onUploaded={(lot) => (window.location.hash = href('lotes', lot.id))} />

      <Card title="Lotes recientes" subtitle="Cada lote es lo que se subió de una vez">
        <ErrorBox message={lots.error} />
        {!lots.data && lots.loading && <Loading />}
        {lots.data?.length === 0 && (
          <Empty icon="inbox" title="Aún no hay lotes">
            Sube imágenes o PDF para que los agentes los procesen.
          </Empty>
        )}
        {lots.data?.length > 0 && (
          <ul className="-mx-5 divide-y divide-line sm:-mx-6">
            {lots.data.map((lot) => (
              <li key={lot.id}>
                <a
                  href={href('lotes', lot.id)}
                  className="flex items-center gap-4 px-5 py-3 transition-colors hover:bg-brand-50/60 sm:px-6"
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface text-muted">
                    <Icon name="layers" size={17} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium text-ink">{dateTime(lot.received_at)}</span>
                    <span className="block text-xs text-muted">
                      {lot.file_count} archivo{lot.file_count === 1 ? '' : 's'} · {lot.page_count} página
                      {lot.page_count === 1 ? '' : 's'}
                    </span>
                  </span>
                  <StatusBadge status={lot.status} size="sm" />
                  <Icon name="chevronRight" size={16} className="text-subtle" />
                </a>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
