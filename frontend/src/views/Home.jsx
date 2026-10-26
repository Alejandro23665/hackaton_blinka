import { useState } from 'react'
import { api } from '../api'
import Icon from '../components/icons'
import { inputClass } from '../components/styles'
import { Button, Card, ErrorBox, Loading } from '../components/ui'
import { longDate } from '../format'
import { href, useLoad, usePolling } from '../hooks'

const TILES = [
  { key: 'registrados', label: 'Documentos subidos', hint: 'Guardados durante el día (FC, CI y GD)', tone: 'text-ink', icon: 'upload' },
  { key: 'procesados_ia', label: 'Procesados por la IA', hint: 'Legibles, sin intervención de una persona', tone: 'text-success-700', icon: 'bot' },
  { key: 'requieren_revision', label: 'Requieren revisión humana', hint: 'No legibles o con descuadre, pendientes', tone: 'text-warning-700', icon: 'alert' },
  { key: 'revisados', label: 'Revisados por una persona', hint: 'Corregidos o confirmados', tone: 'text-brand-700', icon: 'user' },
]

/** Pantalla principal: totales de un día (por defecto, hoy). */
export default function Home() {
  const [fecha, setFecha] = useState('')
  const day = useLoad(() => api.documents.day(fecha || undefined), fecha)
  // Mientras se mira el día de hoy, las cifras se actualizan solas
  usePolling(day.reload, !fecha, 15000)
  const data = day.data

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[13px] font-medium text-muted">{fecha ? 'Día seleccionado' : 'Hoy'}</p>
          <h1 className="mt-0.5 text-2xl font-semibold tracking-tight text-ink first-letter:uppercase">
            {data ? longDate(data.fecha) : '…'}
          </h1>
        </div>
        <div className="flex items-end gap-2">
          <label className="block">
            <span className="mb-1.5 block text-[13px] font-medium text-ink">Ver otro día</span>
            <input
              type="date"
              value={fecha || data?.fecha || ''}
              onChange={(e) => setFecha(e.target.value)}
              className={`${inputClass} w-44`}
            />
          </label>
          {fecha && (
            <Button variant="ghost" onClick={() => setFecha('')}>
              Hoy
            </Button>
          )}
        </div>
      </div>

      <ErrorBox message={day.error} />
      {!data && day.loading && <Loading rows={2} />}

      {data && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {TILES.map((tile) => (
              <div key={tile.key} className="rounded-card border border-line bg-canvas p-5 shadow-card">
                <div className="flex items-center justify-between">
                  <p className="text-[13px] font-medium text-muted">{tile.label}</p>
                  <Icon name={tile.icon} size={17} className="text-subtle" />
                </div>
                <p className={`mt-2 text-3xl font-semibold tabular ${tile.tone}`}>{data[tile.key]}</p>
                <p className="mt-1 text-xs text-subtle">{tile.hint}</p>
              </div>
            ))}
          </div>

          <Card
            title="Revisión humana"
            subtitle="Documentos no legibles o con descuadre que esperan a una persona, de todos los días"
            action={
              <Button
                icon="list"
                variant={data.pendientes_total ? 'primary' : 'secondary'}
                onClick={() => (window.location.hash = href('revision'))}
              >
                Ir a revisión
              </Button>
            }
          >
            <p className="text-sm text-ink">
              {data.pendientes_total === 0 ? (
                'No hay documentos pendientes de revisión.'
              ) : (
                <>
                  <span className="text-2xl font-semibold tabular text-warning-700">{data.pendientes_total}</span>{' '}
                  documento{data.pendientes_total === 1 ? '' : 's'} pendiente{data.pendientes_total === 1 ? '' : 's'}.
                </>
              )}
            </p>
          </Card>
        </>
      )}
    </div>
  )
}
