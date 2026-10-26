import { api } from '../api'
import Icon from '../components/icons'
import UploadZone from '../components/UploadZone'
import { Card, Empty, ErrorBox, Loading, StatusBadge } from '../components/ui'
import { DOC_TYPES, dateTime } from '../format'
import { href, useLoad, usePolling } from '../hooks'

const RUNNING = new Set(['EN_COLA', 'EN_PROCESO'])

/** "menos de 1 min", "3 min"… desde un instante. */
function minutesSince(value) {
  const minutes = Math.floor((Date.now() - new Date(value).getTime()) / 60000)
  return minutes < 1 ? 'menos de 1 min' : `${minutes} min`
}

/** Qué pasó con un documento encontrado en un archivo. Los guardados llevan a su detalle. */
function DocumentResult({ doc }) {
  const content = (
    <>
      <StatusBadge status={doc.resultado} size="sm" />
      <span className="font-medium text-ink">{DOC_TYPES[doc.tipo] ?? doc.tipo}</span>
      {doc.folio && <span className="tabular text-muted">N° {doc.folio}</span>}
      {doc.observaciones && <StatusBadge status={doc.observaciones} size="sm" />}
      {doc.mensaje && <span className="w-full text-xs text-muted">{doc.mensaje}</span>}
    </>
  )
  if (doc.id == null) return <li className="flex flex-wrap items-center gap-x-2 gap-y-1 py-1.5 text-sm">{content}</li>
  return (
    <li>
      <a
        href={href('documentos', doc.id)}
        className="-mx-2 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-control px-2 py-1.5 text-sm transition-colors hover:bg-brand-50/60"
      >
        {content}
        <Icon name="chevronRight" size={14} className="ml-auto text-subtle" />
      </a>
    </li>
  )
}

function Job({ job }) {
  const saved = job.archivos.flatMap((f) => f.documentos).filter((d) => d.resultado === 'GUARDADO').length
  return (
    <li className="px-5 py-4 sm:px-6">
      <div className="flex flex-wrap items-center gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface text-muted">
          <Icon name="upload" size={17} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium text-ink">{dateTime(job.creado_en)}</span>
          <span className="block text-xs text-muted">
            {job.archivos.length} archivo{job.archivos.length === 1 ? '' : 's'} · {saved} documento
            {saved === 1 ? '' : 's'} guardado{saved === 1 ? '' : 's'}
          </span>
        </span>
        <StatusBadge status={job.estado} size="sm" />
      </div>
      {job.etapa && (
        <p className="mt-2 flex items-start gap-2 rounded-control bg-brand-50 px-3 py-2 text-[13px] text-brand-800">
          <Icon name="refresh" size={15} className="mt-px animate-spin [animation-duration:2s]" />
          <span>
            {job.etapa}
            <span className="text-brand-700/70"> · hace {minutesSince(job.etapa_desde)}</span>
          </span>
        </p>
      )}
      {job.mensaje && <p className="mt-2 text-[13px] text-warning-700">{job.mensaje}</p>}

      <ul className="mt-3 space-y-3 border-l-2 border-line pl-4">
        {job.archivos.map((file) => (
          <li key={file.imagen}>
            <div className="flex flex-wrap items-center gap-2 text-[13px]">
              <Icon name={file.tipo_contenido === 'application/pdf' ? 'file' : 'image'} size={15} className="text-subtle" />
              <span className="min-w-0 truncate font-medium text-ink">{file.nombre}</span>
              <StatusBadge status={file.estado} size="sm" />
            </div>
            {file.mensaje && <p className="mt-1 text-xs text-danger-700">{file.mensaje}</p>}
            {file.documentos.length > 0 && (
              <ul className="mt-1">
                {file.documentos.map((doc, i) => (
                  <DocumentResult key={i} doc={doc} />
                ))}
              </ul>
            )}
            {file.estado === 'TERMINADO' && file.documentos.length === 0 && (
              <p className="mt-1 text-xs text-muted">No se encontraron documentos.</p>
            )}
          </li>
        ))}
      </ul>
    </li>
  )
}

/** Inicio: subir archivos y seguir el avance de los trabajos recientes. */
export default function Upload() {
  const jobs = useLoad(() => api.jobs.list())
  usePolling(jobs.reload, jobs.data?.some((job) => RUNNING.has(job.estado)))

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <div className="lg:sticky lg:top-24 lg:self-start">
        <UploadZone onUploaded={jobs.reload} />
      </div>

      <Card
        title="Trabajos recientes"
        subtitle="Desde que se inició el servidor. Si se reinicia, esta lista se borra, pero los documentos guardados quedan."
      >
        <ErrorBox message={jobs.error} />
        {!jobs.data && jobs.loading && <Loading />}
        {jobs.data?.length === 0 && (
          <Empty icon="inbox" title="Aún no hay trabajos">
            Sube imágenes o PDF para que los agentes los procesen.
          </Empty>
        )}
        {jobs.data?.length > 0 && (
          <ul className="-mx-5 divide-y divide-line sm:-mx-6">
            {jobs.data.map((job) => (
              <Job key={job.id} job={job} />
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
