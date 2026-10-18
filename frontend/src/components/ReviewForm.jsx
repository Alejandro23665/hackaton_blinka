import { useId, useState } from 'react'
import { api } from '../api'
import { inputClass, textareaClass } from './styles'
import { Button, ErrorBox } from './ui'

/** Decisión humana sobre una factura escalada. */
const REVIEWER_KEY = 'blinka.reviewer'

function savedReviewer() {
  try {
    return localStorage.getItem(REVIEWER_KEY) ?? ''
  } catch {
    return ''
  }
}

export default function ReviewForm({ invoiceId, onDone }) {
  const id = useId()
  const [reviewer, setReviewer] = useState(savedReviewer)
  const [explanation, setExplanation] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(null)

  async function submit(outcome) {
    if (!reviewer.trim()) {
      setError('Indica tu nombre: cada decisión humana queda registrada con su responsable')
      return
    }
    if (!explanation.trim()) {
      setError('Escribe el motivo de la decisión')
      return
    }
    setBusy(outcome)
    setError(null)
    try {
      await api.invoices.review(invoiceId, { outcome, explanation: explanation.trim(), reviewer: reviewer.trim() })
      try {
        localStorage.setItem(REVIEWER_KEY, reviewer.trim())
      } catch {
        // Sin almacenamiento disponible: se pedirá el nombre la próxima vez
      }
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
      <label htmlFor={`${id}-reviewer`} className="sr-only">Tu nombre</label>
      <input
        id={`${id}-reviewer`}
        className={inputClass}
        placeholder="Tu nombre (queda en el registro)"
        maxLength={100}
        value={reviewer}
        onChange={(e) => {
          setReviewer(e.target.value)
          setError(null)
        }}
      />
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
