import { useId, useState } from 'react'
import { api } from '../api'
import { fileSize } from '../format'
import Icon from './icons'
import { Button, Card, ErrorBox } from './ui'

const ACCEPT = '.pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/jpeg,image/png,image/webp'
const EXTENSIONS = /\.(pdf|jpe?g|png|webp)$/i
// Igual que MAX_FILES_PER_FOLDER del backend
const MAX_FOLDER_FILES = 500

/** Subida de imágenes o PDF sueltos (arrastrando o eligiéndolos) o de una carpeta completa. */
export default function UploadZone({ onUploaded }) {
  const inputId = useId()
  const [files, setFiles] = useState([])
  // Nombre de la carpeta elegida; vacío si son archivos sueltos
  const [folder, setFolder] = useState(null)
  const [skipped, setSkipped] = useState(0)
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  /** Archivos sueltos: se suman a los elegidos. Si había una carpeta elegida, se reemplaza. */
  function add(list) {
    setError(null)
    if (folder) {
      setFolder(null)
      setSkipped(0)
    }
    setFiles((current) => {
      const base = folder ? [] : current
      const names = new Set(base.map((f) => f.name + f.size))
      return [...base, ...Array.from(list).filter((f) => !names.has(f.name + f.size))]
    })
  }

  /** Una carpeta (con sus subcarpetas): reemplaza lo elegido. Solo se suben imágenes y PDF. */
  function addFolder(list) {
    const all = Array.from(list)
    if (!all.length) return
    const valid = all.filter((f) => EXTENSIONS.test(f.name))
    setError(
      !valid.length
        ? 'La carpeta no tiene imágenes ni PDF.'
        : valid.length > MAX_FOLDER_FILES
          ? `La carpeta tiene ${valid.length} archivos; el máximo es ${MAX_FOLDER_FILES}. Divídela en partes.`
          : null,
    )
    setFolder(all[0].webkitRelativePath.split('/')[0])
    setSkipped(all.length - valid.length)
    setFiles(valid)
  }

  function clear() {
    setFiles([])
    setFolder(null)
    setSkipped(0)
  }

  async function upload() {
    setBusy(true)
    setError(null)
    try {
      const job = await api.jobs.create(files, folder)
      clear()
      onUploaded(job)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title="Subir documentos" subtitle="Imágenes o PDF con guías de despacho, controles internos o facturas electrónicas">
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
          add(Array.from(e.dataTransfer.files).filter((f) => EXTENSIONS.test(f.name)))
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

      <label className="mt-3 flex cursor-pointer items-center justify-center gap-2 rounded-control border border-line px-4 py-2.5 text-sm font-medium text-ink transition-colors hover:border-brand-300 hover:bg-brand-50/50">
        <Icon name="folder" size={16} className="text-brand-700" />
        Subir una carpeta completa
        <input
          type="file"
          webkitdirectory=""
          className="sr-only"
          onChange={(e) => {
            addFolder(e.target.files)
            e.target.value = ''
          }}
        />
      </label>

      {folder && (
        <div className="mt-4 flex items-center gap-3 rounded-control bg-brand-50 px-3 py-2.5 text-sm text-brand-800">
          <Icon name="folder" size={18} />
          <span className="min-w-0 flex-1">
            <span className="block truncate font-medium">{folder}</span>
            <span className="block text-xs text-brand-700/80">
              {files.length} archivo{files.length === 1 ? '' : 's'} (incluye subcarpetas)
              {skipped > 0 && ` · ${skipped} ignorado${skipped === 1 ? '' : 's'} por no ser imagen ni PDF`}
            </span>
          </span>
          <button
            type="button"
            aria-label="Quitar la carpeta"
            onClick={clear}
            className="rounded-full p-1 text-brand-700 hover:bg-brand-100"
          >
            <Icon name="x" size={14} />
          </button>
        </div>
      )}

      {files.length > 0 && (
        <ul className="mt-4 max-h-72 divide-y divide-line overflow-y-auto rounded-control border border-line">
          {files.map((file) => (
            <li key={(file.webkitRelativePath || file.name) + file.size} className="flex items-center gap-3 px-3 py-2 text-sm">
              <Icon name={file.type === 'application/pdf' ? 'file' : 'image'} size={16} className="text-subtle" />
              <span className="min-w-0 flex-1 truncate">{file.webkitRelativePath || file.name}</span>
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
            Los agentes separan cada documento, lo clasifican, leen sus datos y validan los montos. Los desconocidos se descartan.
          </p>
          <Button
            icon="sparkles"
            disabled={!files.length || busy || (folder && files.length > MAX_FOLDER_FILES)}
            onClick={upload}
          >
            {busy ? 'Subiendo…' : `Procesar ${files.length || ''} archivo${files.length === 1 ? '' : 's'}`}
          </Button>
        </div>
      </div>
    </Card>
  )
}
