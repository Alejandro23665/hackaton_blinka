import { api } from '../api'
import Icon from '../components/icons'
import UploadZone from '../components/UploadZone'
import { Card, Empty, ErrorBox, Loading, Notice, PageHeader, StatusBadge } from '../components/ui'
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
  if (doc.id == null) return <li className="flex flex-wrap items-center gap-x-2 gap-y-1 px-2 py-1.5 text-[13px]">{content}</li>
  return (
    <li>
      <a
        href={href('documentos', doc.id)}
        className="group flex flex-wrap items-center gap-x-2 gap-y-1 rounded-control px-2 py-1.5 text-[13px] transition-colors hover:bg-brand-25"
      >
        {content}
        <Icon name="chevronRight" size={14} className="ml-auto text-subtle transition-transform group-hover:translate-x-0.5" />
      </a>
    </li>
  )
}

const FINISHED = new Set(['TERMINADO', 'ERROR', 'OMITIDO', 'DETENIDO'])

/** Avance del trabajo: archivos terminados sobre el total (indeterminado mientras no termina ninguno). */
function Progress({ job }) {
  const total = job.archivos.length
  const done = job.archivos.filter((f) => FINISHED.has(f.estado)).length
  const pct = total ? (done / total) * 100 : 0
  return (
    <div className="mt-3">
      <div className="mb-1.5 flex justify-between text-xs text-muted">
        <span>
          {done} de {total} archivo{total === 1 ? '' : 's'} terminado{total === 1 ? '' : 's'}
        </span>
        <span className="tabular">{Math.round(pct)} %</span>
      </div>
      <div
        className="relative h-1.5 overflow-hidden rounded-full bg-info-50 ring-1 ring-info-600/10 ring-inset"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={done}
        aria-label="Archivos terminados"
      >
        {done === 0 ? (
          <span className="absolute inset-y-0 left-0 w-2/5 animate-progress rounded-full bg-info-600" />
        ) : (
          <span className="block h-full rounded-full bg-info-600 transition-[width] duration-500 ease-out" style={{ width: `${pct}%` }} />
        )}
      </div>
    </div>
  )
}

function Job({ job }) {
  const saved = job.archivos.flatMap((f) => f.documentos).filter((d) => d.resultado === 'GUARDADO').length
  const running = RUNNING.has(job.estado)
  return (
    <li className={`px-5 py-5 sm:px-6 ${running ? 'bg-info-50/30' : ''}`}>
      <div className="flex flex-wrap items-start gap-3">
        <span
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-[9px] ring-1 ring-inset ${
            job.carpeta ? 'bg-brand-50 text-brand-600 ring-brand-600/15' : 'bg-surface text-muted ring-line'
          }`}
        >
          <Icon name={job.carpeta ? 'folder' : 'upload'} size={17} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-semibold text-ink">{job.carpeta || 'Archivos sueltos'}</span>
          <span className="block text-xs text-muted">
            {dateTime(job.creado_en)} · {job.archivos.length} archivo{job.archivos.length === 1 ? '' : 's'} · {saved} documento
            {saved === 1 ? '' : 's'} guardado{saved === 1 ? '' : 's'}
          </span>
        </span>
        <StatusBadge status={job.estado} size="sm" />
      </div>

      {running && <Progress job={job} />}
      {job.etapa && (
        <p className="mt-3 flex items-start gap-2 text-[13px] text-info-700">
          <Icon name="loader" size={15} className="mt-[2px] animate-spin [animation-duration:1.4s]" />
          <span>
            {job.etapa}
            <span className="text-muted"> · hace {minutesSince(job.etapa_desde)}</span>
          </span>
        </p>
      )}
      {job.mensaje && (
        <Notice tone="warning" className="mt-3">
          {job.mensaje}
        </Notice>
      )}

      <ul className="mt-4 space-y-2">
        {job.archivos.map((file) => (
          <li key={file.imagen} className="rounded-control border border-line bg-canvas">
            <div className="flex flex-wrap items-center gap-2 px-3 py-2 text-[13px]">
              <Icon name={file.tipo_contenido === 'application/pdf' ? 'file' : 'image'} size={15} className="text-subtle" />
              <span className="min-w-0 flex-1 truncate font-medium text-ink">{file.nombre}</span>
              <StatusBadge status={file.estado} size="sm" />
            </div>
            {file.mensaje && <p className="border-t border-line px-3 py-2 text-xs text-danger-700">{file.mensaje}</p>}
            {file.documentos.length > 0 && (
              <ul className="border-t border-line p-1">
                {file.documentos.map((doc, i) => (
                  <DocumentResult key={i} doc={doc} />
                ))}
              </ul>
            )}
            {file.estado === 'TERMINADO' && file.documentos.length === 0 && (
              <p className="border-t border-line px-3 py-2 text-xs text-muted">No se encontraron documentos.</p>
            )}
          </li>
        ))}
      </ul>
    </li>
  )
}

/** Subir archivos y seguir el avance de los trabajos recientes. */
export default function Upload() {
  const jobs = useLoad(() => api.jobs.list())
  usePolling(jobs.reload, jobs.data?.some((job) => RUNNING.has(job.estado)))
  const running = jobs.data?.filter((job) => RUNNING.has(job.estado)).length ?? 0

  return (
    <div className="space-y-6 lg:space-y-8">
      <PageHeader
        eyebrow="Ingreso"
        title="Subir documentos"
        meta="Sube los archivos y sigue cómo los agentes los procesan."
      />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <div className="lg:sticky lg:top-6 lg:self-start">
          <UploadZone onUploaded={jobs.reload} />
        </div>

        <Card
          title="Trabajos recientes"
          subtitle="Desde que se inició el servidor. Si se reinicia, esta lista se borra, pero los documentos guardados quedan."
          action={
            running > 0 && (
              <span className="inline-flex items-center gap-1.5 rounded-md bg-info-50 px-2 py-1 text-xs font-medium text-info-700 ring-1 ring-info-600/20 ring-inset">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-info-600" />
                {running} en curso
              </span>
            )
          }
        >
          <ErrorBox message={jobs.error} />
          {!jobs.data && jobs.loading && <Loading />}
          {jobs.data?.length === 0 && (
            <Empty icon="inbox" title="Aún no hay trabajos">
              Cuando subas imágenes o PDF, aquí verás cada archivo, los documentos que se encontraron en él y su estado.
            </Empty>
          )}
          {jobs.data?.length > 0 && (
            <ul className="-mx-5 -mb-5 divide-y divide-line border-t border-line sm:-mx-6 sm:-mb-6">
              {jobs.data.map((job) => (
                <Job key={job.id} job={job} />
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}
