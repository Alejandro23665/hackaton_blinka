import { useState } from 'react'
import { api } from '../api'
import Icon from '../components/icons'
import { Button, Card, ErrorBox, Eyebrow, Loading, Segmented, StatusBadge, Tag, Tile } from '../components/ui'
import {
  DOC_TYPES,
  FIELD_LABELS,
  SEVERITY_TONE,
  STEP_LABELS,
  clp,
  dateTime,
  duration,
  percent,
  rut,
  shortDate,
} from '../format'
import { href, useLoad, usePolling } from '../hooks'

/** Imagen de cada hoja del documento; si comparte página con otros, se marca su zona. */
function Viewer({ regions }) {
  const [index, setIndex] = useState(0)
  const [crop, setCrop] = useState(false)
  const region = regions[Math.min(index, regions.length - 1)]
  if (!region) return null
  const showCrop = crop && region.has_crop

  return (
    <Card
      title="Documento original"
      subtitle={`Página ${region.page_number} del archivo${region.bbox ? ` · ${region.position_hint ?? 'zona marcada'}` : ''}`}
      action={
        <a
          href={api.fileUrl(region.file_id)}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-[13px] font-medium text-brand-700 hover:underline"
        >
          Archivo <Icon name="external" size={14} />
        </a>
      }
    >
      {(regions.length > 1 || region.has_crop) && (
        <div className="mb-3 flex flex-wrap gap-2">
          {regions.length > 1 && (
            <Segmented
              size="sm"
              value={index}
              onChange={(value) => setIndex(value)}
              options={regions.map((r, i) => ({ value: i, label: `Hoja ${i + 1}` }))}
            />
          )}
          {region.has_crop && (
            <Segmented
              size="sm"
              value={showCrop ? 'crop' : 'page'}
              onChange={(value) => setCrop(value === 'crop')}
              options={[
                { value: 'page', label: 'Página' },
                { value: 'crop', label: 'Recorte' },
              ]}
            />
          )}
        </div>
      )}
      <div className="relative overflow-hidden rounded-control border border-line bg-surface">
        <img
          src={showCrop ? api.cropUrl(region.id) : api.pageImageUrl(region.page_id)}
          alt={`Página ${region.page_number}`}
          className="block h-auto w-full"
        />
        {region.bbox && !showCrop && (
          <div
            className="pointer-events-none absolute rounded-sm border-2 border-brand-600 bg-brand-600/5"
            style={{
              left: `${region.bbox.x * 100}%`,
              top: `${region.bbox.y * 100}%`,
              width: `${region.bbox.w * 100}%`,
              height: `${region.bbox.h * 100}%`,
            }}
          />
        )}
      </div>
    </Card>
  )
}

function fieldValue(name, run) {
  switch (name) {
    case 'PROVIDER_RUT':
      return run.rut_is_substitute ? '1-9' : rut(run.provider_rut)
    case 'DOCUMENT_NUMBER':
      return run.document_number ?? '—'
    case 'ISSUE_DATE':
      return shortDate(run.issue_date)
    case 'NET_AMOUNT':
      return clp(run.net_amount)
    case 'TAX_AMOUNT':
      return clp(run.tax_amount)
    case 'EXEMPT_AMOUNT':
      return clp(run.exempt_amount)
    default:
      return clp(run.total_amount)
  }
}

function Fields({ fields, run }) {
  return (
    <div className="-mx-5 overflow-x-auto sm:-mx-6">
      <table className="w-full min-w-[560px] text-left text-sm">
        <thead>
          <tr className="border-b border-line text-xs text-subtle">
            <th className="px-5 py-2 font-medium sm:pl-6">Campo</th>
            <th className="px-3 py-2 font-medium">Valor</th>
            <th className="px-3 py-2 font-medium">Leído en el documento</th>
            <th className="px-5 py-2 text-right font-medium sm:pr-6">Estado</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {fields.map((f) => (
            <tr key={f.field_name} className="align-top">
              <td className="px-5 py-3 sm:pl-6">
                <span className="font-medium text-ink">{FIELD_LABELS[f.field_name]}</span>
                {!f.is_required && <span className="block text-[11px] text-subtle">opcional</span>}
              </td>
              <td className="px-3 py-3 tabular">
                {fieldValue(f.field_name, run)}
                {f.field_name === 'PROVIDER_RUT' && run.rut_is_substitute && (
                  <span className="ml-1.5">
                    <Tag tone="warning">sustituto</Tag>
                  </span>
                )}
              </td>
              <td className="px-3 py-3">
                {f.raw_text ? <code className="rounded bg-surface px-1.5 py-0.5 text-[12px]">{f.raw_text}</code> : '—'}
                {f.invalid_reason && f.status !== 'AUSENTE' && (
                  <span className="mt-1 block text-xs text-warning-700">{f.invalid_reason}</span>
                )}
              </td>
              <td className="px-5 py-3 text-right sm:pr-6">
                <StatusBadge status={f.status} size="sm" />
                {f.confidence != null && (
                  <span className="mt-1 block text-[11px] whitespace-nowrap text-subtle">confianza {percent(f.confidence)}</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** neto + impuestos + exento = calculado, frente al total declarado. */
function Sum({ run }) {
  const parts = [
    ['Neto', run.net_amount],
    ['Impuestos', run.tax_amount],
    ['Exento', run.exempt_amount],
  ]
  return (
    <Card title="Validación de montos" action={<StatusBadge status={run.validation_status} />}>
      {run.validation_status === 'NO_APLICA' ? (
        <p className="text-sm text-muted">No aplica: el documento no tiene montos (guía sin valorizar).</p>
      ) : (
        <dl className="space-y-2 text-sm">
          {parts.map(([label, value]) => (
            <div key={label} className="flex justify-between">
              <dt className="text-muted">{label}</dt>
              <dd className="tabular">{value == null ? <span className="text-subtle">sin valor</span> : clp(value)}</dd>
            </div>
          ))}
          <div className="flex justify-between border-t border-line pt-2">
            <dt className="text-muted">Calculado</dt>
            <dd className="tabular font-medium">{clp(run.calculated_total)}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted">Total declarado</dt>
            <dd className="tabular font-medium">{clp(run.total_amount)}</dd>
          </div>
          {run.difference != null && Number(run.difference) !== 0 && (
            <div className="flex justify-between rounded-control bg-danger-50 px-3 py-2 text-danger-700">
              <dt className="font-medium">Diferencia</dt>
              <dd className="tabular font-semibold">{clp(run.difference)}</dd>
            </div>
          )}
          <p className="pt-1 text-xs text-subtle">Tolerancia: {clp(run.total_tolerance)}</p>
        </dl>
      )}
    </Card>
  )
}

/** Detalle de un documento: imagen, estados, campos, validación, alertas y bitácora. */
export default function DocumentDetail({ id }) {
  const doc = useLoad(() => api.documents.get(id), id)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const latest = doc.data?.history.at(-1)
  const running = latest?.technical_status === 'EN_PROCESO'
  usePolling(doc.reload, running)

  if (!doc.data) {
    return doc.loading ? <Loading rows={5} /> : <ErrorBox message={doc.error} />
  }
  const { run, fields, issues, steps, history, regions } = doc.data
  const status = run?.overall_status ?? run?.technical_status
  const unknown = run?.doc_type === 'DESCONOCIDO'

  async function reprocess() {
    setBusy(true)
    setError(null)
    try {
      await api.documents.reprocess(id)
      doc.reload()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <a
            href={href('lotes', doc.data.submission_id)}
            className="inline-flex items-center gap-1.5 text-[13px] text-muted hover:text-brand-700"
          >
            <Icon name="arrowLeft" size={14} /> Lote del {dateTime(doc.data.received_at)}
          </a>
          <h2 className="mt-1 flex flex-wrap items-center gap-3 text-xl font-semibold tracking-tight">
            {DOC_TYPES[run?.doc_type] ?? 'Documento'}
            {run?.document_number && <span className="tabular text-muted">N° {run.document_number}</span>}
            {status && <StatusBadge status={status} />}
          </h2>
        </div>
        {run && !unknown && (
          <Button variant="secondary" icon="refresh" disabled={busy || running} onClick={reprocess}>
            {running ? 'Procesando…' : busy ? 'Enviando…' : 'Reprocesar'}
          </Button>
        )}
      </div>

      <ErrorBox message={error} />
      {latest && !latest.is_current && latest.technical_status === 'FALLIDO' && run?.is_current && (
        <ErrorBox message={`El reproceso n.º ${latest.run_number} falló; se mantiene el resultado anterior.`} />
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <div className="lg:sticky lg:top-24 lg:self-start">
          <Viewer regions={regions} />
        </div>

        <div className="space-y-6">
          {run && (
            <Card>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <Tile>
                  <Eyebrow>Clasificación</Eyebrow>
                  <p className="mt-1 text-sm font-medium">{DOC_TYPES[run.doc_type] ?? '—'}</p>
                  <p className="mt-0.5 text-xs text-muted">
                    {run.classification_evidence ? `“${run.classification_evidence}”` : 'sin título visible'} ·{' '}
                    {percent(run.classification_confidence)}
                  </p>
                </Tile>
                <Tile>
                  <Eyebrow>Extracción</Eyebrow>
                  <div className="mt-1.5">{run.extraction_status ? <StatusBadge status={run.extraction_status} size="sm" /> : '—'}</div>
                </Tile>
                <Tile>
                  <Eyebrow>Firma</Eyebrow>
                  <p className="mt-1 text-sm font-medium">
                    {run.has_signature == null ? '—' : run.has_signature ? 'Firmado' : 'Sin firma'}
                  </p>
                  {run.signature_confidence != null && (
                    <p className="mt-0.5 text-xs text-muted">confianza {percent(run.signature_confidence)}</p>
                  )}
                </Tile>
                <Tile>
                  <Eyebrow>Validación</Eyebrow>
                  <div className="mt-1.5">{run.validation_status ? <StatusBadge status={run.validation_status} size="sm" /> : '—'}</div>
                </Tile>
              </div>
              {(run.review_reason || run.error_message) && (
                <p className="mt-4 rounded-control bg-surface px-3 py-2.5 text-sm text-ink">
                  {run.error_message ?? run.review_reason}
                </p>
              )}
            </Card>
          )}

          {issues.length > 0 && (
            <Card title="Alertas" subtitle="Todos los problemas detectados, también los secundarios">
              <ul className="space-y-2">
                {issues.map((issue, i) => (
                  <li key={i} className="flex items-start gap-3 text-sm">
                    <Tag tone={SEVERITY_TONE[issue.severity]}>{issue.code}</Tag>
                    <span className="min-w-0 flex-1 text-ink">{issue.message}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {fields.length > 0 && (
            <Card title="Campos extraídos" subtitle="Valor normalizado, texto original y estado de cada campo">
              <Fields fields={fields} run={run} />
            </Card>
          )}

          {run && run.validation_status && !unknown && <Sum run={run} />}

          <Card title="Trazabilidad" subtitle="Pasos de este procesamiento e historial">
            {steps.length > 0 && (
              <ul className="mb-4 space-y-2 text-sm">
                {steps.map((s, i) => (
                  <li key={i} className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <StatusBadge status={s.status} size="sm" />
                    <span className="font-medium">{STEP_LABELS[s.step] ?? s.step}</span>
                    {s.model && <code className="text-xs text-muted">{s.model}</code>}
                    <span className="text-xs text-subtle">{duration(s.duration_ms)}</span>
                    {s.error_message && <span className="w-full text-xs text-danger-700">{s.error_message}</span>}
                  </li>
                ))}
              </ul>
            )}
            <Eyebrow className="mb-2">Procesamientos</Eyebrow>
            <ul className="space-y-1.5 text-sm">
              {history.map((h) => (
                <li key={h.run_number} className="flex flex-wrap items-center gap-3">
                  <span className="tabular text-muted">n.º {h.run_number}</span>
                  <StatusBadge status={h.overall_status ?? h.technical_status} size="sm" />
                  <span className="text-xs text-subtle">{dateTime(h.finished_at ?? h.started_at)}</span>
                  {h.is_current && <Tag tone="brand">actual</Tag>}
                </li>
              ))}
            </ul>
            {run?.ocr_text && (
              <details className="mt-4">
                <summary className="cursor-pointer text-[13px] font-medium text-brand-700">Texto leído por la IA</summary>
                <pre className="mt-2 max-h-80 overflow-auto rounded-control bg-surface p-3 text-xs whitespace-pre-wrap">
                  {run.ocr_text}
                </pre>
              </details>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}
