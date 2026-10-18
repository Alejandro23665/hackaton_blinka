import { useRef, useState } from 'react'
import { api } from '../api'
import { dateTime, fileSize } from '../format'
import { useLoad } from '../hooks'
import Icon from './icons'
import { textareaClass } from './styles'
import { Button, Card, ErrorBox, Segmented } from './ui'

const ACCEPT = '.pdf,.png,.jpg,.jpeg,.webp,application/pdf,image/png,image/jpeg,image/webp'
const MAX_MB = 10

const DOC_STATUS = {
  processing: { label: 'Leyendo…', className: 'bg-brand-100 text-brand-800' },
  processed: { label: 'Procesada', className: 'bg-success-50 text-success-700' },
  failed: { label: 'No se pudo leer', className: 'bg-danger-50 text-danger-700' },
  not_invoice: { label: 'No es una factura', className: 'bg-surface-strong text-muted' },
}

const isNotInvoice = (doc) => doc.status === 'failed' && doc.error?.startsWith('El archivo no es una factura')

/** Subida de facturas: el agente lee el archivo, crea la factura y la evalúa. */
export default function UploadCard({ version, onChange, openInvoice }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)
  const [current, setCurrent] = useState(null) // { name, size }
  const [error, setError] = useState(null)
  const [mode, setMode] = useState('file') // 'file' | 'text'
  const [text, setText] = useState('')
  const [source, setSource] = useState('email')
  const documents = useLoad(() => api.documents.list({ limit: 5 }), version)

  // Mismo final para archivo y texto: abrir la factura o explicar por qué no se pudo
  function afterUpload(doc) {
    onChange()
    if (doc.status === 'processed' && doc.invoice_id) openInvoice(doc.invoice_id)
    else setError(doc.error ?? 'El agente no pudo leer la factura.')
  }

  async function handleText(e) {
    e.preventDefault()
    if (current) return
    if (text.trim().length < 20) {
      setError('Pega el texto completo del correo o mensaje (al menos 20 caracteres).')
      return
    }
    setError(null)
    setCurrent({ name: source === 'email' ? 'Correo pegado' : 'Mensaje de chat', size: new Blob([text]).size })
    try {
      afterUpload(await api.documents.uploadText(text, source))
      setText('')
    } catch (err) {
      setError(err.message)
    } finally {
      setCurrent(null)
    }
  }

  async function handleFile(file) {
    if (!file || current) return
    setError(null)
    if (file.size > MAX_MB * 1024 * 1024) {
      setError(`El archivo supera ${MAX_MB} MB.`)
      return
    }
    setCurrent({ name: file.name, size: file.size })
    try {
      afterUpload(await api.documents.upload(file))
    } catch (err) {
      setError(err.message)
    } finally {
      setCurrent(null)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  const busy = Boolean(current)

  return (
    <Card title="Recibir factura" subtitle="El agente lee el archivo o el mensaje, extrae los datos y decide">
      <Segmented
        className="mb-4 w-full [&>button]:flex-1 [&>button]:justify-center"
        value={mode}
        onChange={(value) => {
          setMode(value)
          setError(null)
        }}
        options={[
          { value: 'file', label: 'Archivo' },
          { value: 'text', label: 'Correo o chat' },
        ]}
      />

      {mode === 'text' ? (
        <form onSubmit={handleText} noValidate className="space-y-3">
          <Segmented
            size="sm"
            value={source}
            onChange={setSource}
            options={[
              { value: 'email', label: 'Correo' },
              { value: 'chat', label: 'Chat' },
            ]}
          />
          <label htmlFor="invoice-text" className="sr-only">Texto del correo o mensaje</label>
          <textarea
            id="invoice-text"
            className={`${textareaClass} min-h-[170px] font-mono text-[13px]`}
            placeholder={
              source === 'email'
                ? 'De: proveedor@empresa.com\nAsunto: Cuenta de cobro N.º 123\n\nPega aquí el correo completo…'
                : '[12/10 09:41] Proveedor: Te paso el cobro de octubre…\n\nPega aquí la conversación…'
            }
            value={text}
            disabled={Boolean(current)}
            onChange={(e) => {
              setText(e.target.value)
              setError(null)
            }}
          />
          <Button type="submit" icon={current ? 'sparkles' : 'bot'} disabled={Boolean(current)} className="w-full">
            {current ? 'El agente está leyendo el mensaje…' : 'Enviar al agente'}
          </Button>
        </form>
      ) : (
        <label
          onDragOver={(e) => {
            e.preventDefault()
            if (!busy) setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragging(false)
            handleFile(e.dataTransfer.files?.[0])
          }}
          className={`relative flex cursor-pointer flex-col items-center justify-center rounded-card border-2 border-dashed px-4 py-8 text-center transition-colors ${
            busy
              ? 'cursor-wait border-brand-300 bg-brand-50'
              : dragging
                ? 'border-brand-600 bg-brand-50'
                : 'border-line-strong bg-surface hover:border-brand-300 hover:bg-brand-50/60'
          } has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-brand-600`}
        >
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            className="sr-only"
            disabled={busy}
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
          {busy ? (
            <>
              <span className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-brand-600 text-white">
                <Icon name="sparkles" size={20} className="animate-pulse" />
              </span>
              <p className="text-sm font-semibold text-ink">El agente está leyendo la factura…</p>
              <p className="mt-1 max-w-56 truncate text-xs text-muted">
                {current.name} · {fileSize(current.size)}
              </p>
              <div className="mt-4 h-1 w-40 overflow-hidden rounded-full bg-brand-100">
                <div className="h-full w-1/3 animate-[upload_1.2s_ease-in-out_infinite] rounded-full bg-brand-600" />
              </div>
            </>
          ) : (
            <>
              <span className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-canvas text-brand-600 shadow-control">
                <Icon name="upload" size={20} />
              </span>
              <p className="text-sm font-semibold text-ink">
                Arrastra la factura aquí o <span className="text-brand-700 underline underline-offset-2">elige un archivo</span>
              </p>
              <p className="mt-1 text-xs text-muted">PDF, PNG, JPG o WEBP · máx. {MAX_MB} MB</p>
            </>
          )}
        </label>
      )}

      <div className="mt-3">
        <ErrorBox message={error} />
      </div>

      {documents.data?.length > 0 && (
        <div className="mt-5">
          <p className="mb-2 text-xs font-medium text-muted">Últimas subidas</p>
          <ul className="divide-y divide-line rounded-control border border-line">
            {documents.data.map((doc) => {
              const s = DOC_STATUS[isNotInvoice(doc) ? 'not_invoice' : doc.status]
              const clickable = doc.invoice_id != null
              const body = (
                <>
                  <Icon name={doc.content_type === 'text/plain' ? 'inbox' : 'file'} size={16} className="mt-0.5 text-subtle" />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center justify-between gap-2">
                      <span className="truncate text-[13px] font-medium text-ink" title={doc.original_name}>
                        {doc.original_name}
                      </span>
                      <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${s.className}`}>{s.label}</span>
                    </span>
                    <span className="mt-0.5 block truncate text-[11px] text-subtle" title={doc.error ?? undefined}>
                      {doc.error ?? `${fileSize(doc.size_bytes)} · ${dateTime(doc.created_at)}`}
                    </span>
                  </span>
                </>
              )
              return (
                <li key={doc.id}>
                  {clickable ? (
                    <button
                      onClick={() => openInvoice(doc.invoice_id)}
                      className="flex w-full items-start gap-2.5 px-3 py-2.5 text-left transition-colors hover:bg-surface"
                    >
                      {body}
                    </button>
                  ) : (
                    <div className="flex items-start gap-2.5 px-3 py-2.5">{body}</div>
                  )}
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </Card>
  )
}
