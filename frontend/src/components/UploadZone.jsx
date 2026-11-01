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

  const tooMany = folder && files.length > MAX_FOLDER_FILES

  return (
    <Card title="Subir documentos" subtitle="Guías de despacho, controles internos o facturas electrónicas, en imagen o PDF.">
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
        className={`group relative flex cursor-pointer flex-col items-center justify-center overflow-hidden rounded-[12px] border-[1.5px] border-dashed px-5 py-10 text-center transition-[border-color,background-color] duration-150 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-brand-600 ${
          dragging ? 'border-brand-600 bg-brand-50' : 'border-line-strong bg-surface/50 hover:border-brand-400 hover:bg-brand-25'
        }`}
      >
        <span
          className={`mb-4 flex h-12 w-12 items-center justify-center rounded-[12px] bg-canvas text-brand-600 shadow-card ring-1 ring-line transition-transform duration-200 ease-out ${
            dragging ? '-translate-y-1 scale-105' : 'group-hover:-translate-y-0.5'
          }`}
        >
          <Icon name="upload" size={22} />
        </span>
        <span className="text-[15px] font-semibold text-ink">
          {dragging ? 'Suelta los archivos para añadirlos' : 'Arrastra los archivos aquí'}
        </span>
        <span className="mt-1 text-[13px] text-muted">
          o <span className="font-medium text-brand-700 underline decoration-brand-300 underline-offset-2">elígelos en tu equipo</span>
        </span>
        <span className="mt-4 flex flex-wrap justify-center gap-1.5">
          {['PDF', 'JPG', 'PNG', 'WEBP'].map((ext) => (
            <span key={ext} className="rounded-md bg-canvas px-1.5 py-0.5 font-mono text-[10.5px] text-subtle ring-1 ring-line">
              {ext}
            </span>
          ))}
        </span>
        <span className="mt-2 text-xs text-subtle">PDF de varias páginas y varios archivos a la vez</span>
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

      <label className="mt-3 flex cursor-pointer items-center gap-3 rounded-control border border-line px-3.5 py-2.5 text-sm transition-colors hover:border-brand-300 hover:bg-brand-25 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-brand-600">
        <Icon name="folder" size={18} className="text-brand-600" />
        <span className="min-w-0 flex-1">
          <span className="block font-medium text-ink">Subir una carpeta completa</span>
          <span className="block text-xs text-subtle">Con sus subcarpetas · hasta {MAX_FOLDER_FILES} archivos</span>
        </span>
        <Icon name="chevronRight" size={16} className="text-subtle" />
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
        <div className="mt-4 flex items-center gap-3 rounded-control bg-brand-50 px-3 py-2.5 text-sm text-brand-800 ring-1 ring-brand-600/15 ring-inset">
          <Icon name="folder" size={18} />
          <span className="min-w-0 flex-1">
            <span className="block truncate font-medium">{folder}</span>
            <span className="block text-xs text-brand-700">
              {files.length} archivo{files.length === 1 ? '' : 's'} (incluye subcarpetas)
              {skipped > 0 && ` · ${skipped} ignorado${skipped === 1 ? '' : 's'} por no ser imagen ni PDF`}
            </span>
          </span>
          <button
            type="button"
            aria-label="Quitar la carpeta"
            onClick={clear}
            className="inline-flex h-8 w-8 items-center justify-center rounded-control text-brand-700 hover:bg-brand-100"
          >
            <Icon name="x" size={15} />
          </button>
        </div>
      )}

      {files.length > 0 && (
        <div className="mt-4">
          <div className="mb-2 flex items-center justify-between text-xs">
            <span className="font-medium text-muted">
              {files.length} archivo{files.length === 1 ? '' : 's'} listo{files.length === 1 ? '' : 's'} ·{' '}
              <span className="tabular">{fileSize(files.reduce((sum, f) => sum + f.size, 0))}</span>
            </span>
            <button type="button" onClick={clear} className="rounded font-medium text-muted hover:text-danger-600">
              Quitar todos
            </button>
          </div>
          <ul className="max-h-72 divide-y divide-line overflow-y-auto rounded-control border border-line">
            {files.map((file) => (
              <li key={(file.webkitRelativePath || file.name) + file.size} className="flex items-center gap-3 py-1.5 pr-1.5 pl-3 text-sm">
                <Icon name={file.type === 'application/pdf' ? 'file' : 'image'} size={16} className="text-subtle" />
                <span className="min-w-0 flex-1 truncate">{file.webkitRelativePath || file.name}</span>
                <span className="tabular text-xs text-subtle">{fileSize(file.size)}</span>
                <button
                  type="button"
                  aria-label={`Quitar ${file.name}`}
                  onClick={() => setFiles((current) => current.filter((f) => f !== file))}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-control text-subtle hover:bg-surface hover:text-ink"
                >
                  <Icon name="x" size={14} />
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-5 space-y-3">
        <ErrorBox message={error} />
        <Button icon="sparkles" className="w-full" disabled={!files.length || busy || tooMany} onClick={upload}>
          {busy ? 'Subiendo…' : `Procesar ${files.length || ''} archivo${files.length === 1 ? '' : 's'}`}
        </Button>
        <p className="text-xs leading-relaxed text-subtle">
          Los agentes separan cada documento, lo clasifican, leen sus datos y validan los montos. Los que no se reconocen pasan a revisión.
        </p>
      </div>
    </Card>
  )
}
