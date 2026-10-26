import { useState } from 'react'
import { useDocumentImage } from '../hooks'
import Icon from './icons'
import { Card, ErrorBox, Loading, Segmented } from './ui'

/** El archivo original de un documento: imagen (con zoom para revisarla) o PDF. */
export default function DocumentViewer({ id }) {
  const [zoom, setZoom] = useState(1)
  const image = useDocumentImage(id)
  const isPdf = image.type === 'application/pdf'

  return (
    <Card
      title="Documento original"
      subtitle={isPdf ? 'PDF' : 'Imagen tal como se subió'}
      action={
        image.url && (
          <div className="flex items-center gap-3">
            {!isPdf && (
              <Segmented
                size="sm"
                value={zoom}
                onChange={setZoom}
                options={[
                  { value: 1, label: 'Ajustar' },
                  { value: 2, label: '200 %' },
                  { value: 3, label: '300 %' },
                ]}
              />
            )}
            <a
              href={image.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-[13px] font-medium text-brand-700 hover:underline"
            >
              Abrir <Icon name="external" size={14} />
            </a>
          </div>
        )
      }
    >
      <ErrorBox message={image.error} />
      {!image.url && !image.error && <Loading rows={4} />}
      {image.url &&
        (isPdf ? (
          <iframe src={image.url} title="Documento original" className="h-[75vh] w-full rounded-control border border-line" />
        ) : (
          <div className="max-h-[75vh] overflow-auto rounded-control border border-line bg-surface">
            <img src={image.url} alt="Documento original" className="block h-auto max-w-none" style={{ width: `${zoom * 100}%` }} />
          </div>
        ))}
    </Card>
  )
}
