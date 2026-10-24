import { useId, useState } from 'react'
import { api } from '../api'
import { fileSize } from '../format'
import Icon from './icons'
import { Button, Card, ErrorBox } from './ui'

const ACCEPT = '.pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/jpeg,image/png,image/webp'

/** Subida de un lote: una o varias imágenes o PDF, arrastrando o eligiendo archivos. */
export default function UploadZone({ onUploaded }) {
  const inputId = useId()
  const [files, setFiles] = useState([])
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  function add(list) {
    setError(null)
    setFiles((current) => {
      const names = new Set(current.map((f) => f.name + f.size))
      return [...current, ...Array.from(list).filter((f) => !names.has(f.name + f.size))]
    })
  }

  async function upload() {
    setBusy(true)
    setError(null)
    try {
      const lot = await api.submissions.upload(files)
      setFiles([])
      onUploaded(lot)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title="Nuevo lote" subtitle="Imágenes o PDF con guías de despacho, controles internos o facturas electrónicas">
      <label
        htmlFor={inputId}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          add(e.dataTransfer.files)
        }}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-control border-2 border-dashed px-4 py-8 text-center transition-colors ${
          dragging ? 'border-brand-600 bg-brand-50' : 'border-line-strong hover:border-brand-300 hover:bg-brand-50/50'
        }`}
      >
        <span className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-brand-100 text-brand-700">
          <Icon name="upload" size={20} />
        </span>
        <span className="text-sm font-medium text-ink">Arrastra los archivos aquí o haz clic para elegirlos</span>
        <span className="mt-1 text-xs text-muted">PDF (de varias páginas), JPG, PNG o WEBP · varios archivos a la vez</span>
        <input
          id={inputId}
          type="file"
          multiple
          accept={ACCEPT}
          className="sr-only"
          onChange={(e) => {
            add(e.target.files)
            e.target.value = ''
          }}
        />
      </label>

      {files.length > 0 && (
        <ul className="mt-4 divide-y divide-line rounded-control border border-line">
          {files.map((file) => (
            <li key={file.name + file.size} className="flex items-center gap-3 px-3 py-2 text-sm">
              <Icon name={file.type === 'application/pdf' ? 'file' : 'image'} size={16} className="text-subtle" />
              <span className="min-w-0 flex-1 truncate">{file.name}</span>
              <span className="tabular text-xs text-subtle">{fileSize(file.size)}</span>
              <button
                type="button"
                aria-label={`Quitar ${file.name}`}
                onClick={() => setFiles((current) => current.filter((f) => f !== file))}
                className="rounded-full p-1 text-subtle hover:bg-surface hover:text-ink"
              >
                <Icon name="x" size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-4 space-y-3">
        <ErrorBox message={error} />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-muted">
            Los agentes separan cada documento, lo clasifican, leen sus datos y validan los montos.
          </p>
          <Button icon="sparkles" disabled={!files.length || busy} onClick={upload}>
            {busy ? 'Subiendo…' : `Procesar ${files.length || ''} archivo${files.length === 1 ? '' : 's'}`}
          </Button>
        </div>
      </div>
    </Card>
  )
}
