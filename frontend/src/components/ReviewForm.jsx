import { useId, useState } from 'react'
import { api } from '../api'
import { textareaClass } from './styles'
import { Button, ErrorBox } from './ui'

/** Decisión humana sobre una factura escalada. */
export default function ReviewForm({ invoiceId, onDone }) {
  const id = useId()
  const [explanation, setExplanation] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(null)

  async function submit(outcome) {
    if (!explanation.trim()) {
      setError('Escribe el motivo de la decisión')
      return
    }
    setBusy(outcome)
    setError(null)
    try {
      await api.invoices.review(invoiceId, { outcome, explanation: explanation.trim() })
      setExplanation('')
      onDone?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="space-y-3">
      <label htmlFor={id} className="sr-only">Motivo de la decisión</label>
      <textarea
        id={id}
        className={textareaClass}
        rows={2}
        placeholder="Motivo de la decisión (ej. contrato anual aprobado por finanzas)"
        value={explanation}
        onChange={(e) => {
          setExplanation(e.target.value)
          setError(null)
        }}
      />
      <ErrorBox message={error} />
      <div className="flex flex-wrap gap-2">
        <Button icon="check" disabled={!!busy} onClick={() => submit('approved')} className="flex-1 sm:flex-none">
          {busy === 'approved' ? 'Aprobando…' : 'Aprobar'}
        </Button>
        <Button variant="danger" icon="x" disabled={!!busy} onClick={() => submit('blocked')} className="flex-1 sm:flex-none">
          {busy === 'blocked' ? 'Bloqueando…' : 'Bloquear'}
        </Button>
      </div>
    </div>
  )
}
