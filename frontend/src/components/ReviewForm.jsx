import { useState } from 'react'
import { api } from '../api'
import { Button, ErrorBox, inputClass } from './ui'

/** Decisión humana sobre una factura escalada. */
export default function ReviewForm({ invoiceId, onDone }) {
  const [explanation, setExplanation] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function submit(outcome) {
    if (!explanation.trim()) {
      setError('Escribe el motivo de la decisión')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await api.invoices.review(invoiceId, { outcome, explanation: explanation.trim() })
      setExplanation('')
      onDone?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-2">
      <textarea
        className={inputClass}
        rows={2}
        placeholder="Motivo (ej. contrato anual aprobado por finanzas)"
        value={explanation}
        onChange={(e) => {
          setExplanation(e.target.value)
          setError(null)
        }}
      />
      <ErrorBox message={error} />
      <div className="flex gap-2">
        <Button variant="success" disabled={busy} onClick={() => submit('approved')}>
          Aprobar
        </Button>
        <Button variant="danger" disabled={busy} onClick={() => submit('blocked')}>
          Bloquear
        </Button>
      </div>
    </div>
  )
}
