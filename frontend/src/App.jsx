import { api, BASE_URL } from './api'
import { Card } from './components/ui'
import { useLoad } from './hooks'

/**
 * Interfaz provisional mientras se construye el procesamiento de documentos (etapa 5.6).
 * Por ahora la API se prueba desde /docs.
 */
export default function App() {
  const health = useLoad(() => api.health())
  const online = health.data?.status === 'ok'

  return (
    <main className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
      <Card title="Procesamiento de documentos" subtitle="Interfaz en construcción">
        <div className="space-y-3 text-sm text-muted">
          <p>
            El sistema recibe guías de despacho, controles internos y facturas electrónicas, extrae sus datos con
            agentes de IA y valida los montos.
          </p>
          <p>
            Mientras se construye la interfaz, la API se prueba en{' '}
            <a className="font-medium text-brand-700 underline" href={`${BASE_URL}/docs`}>
              /docs
            </a>
            .
          </p>
          <p>API: {health.loading ? 'conectando…' : online ? 'en línea' : 'sin conexión'}</p>
        </div>
      </Card>
    </main>
  )
}
