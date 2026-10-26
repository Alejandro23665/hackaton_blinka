import { useCallback, useEffect, useState } from 'react'
import { api } from './api'

/** Carga datos con `loader` y vuelve a cargar cuando cambia `reloadKey` o se llama a reload().
 * Al recargar conserva los datos anteriores (sin parpadeo): `loading` sin `data` es la primera carga. */
export function useLoad(loader, reloadKey) {
  const [state, setState] = useState({ data: null, error: null, loading: true })
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let cancelled = false
    setState((s) => ({ ...s, loading: true }))
    loader()
      .then((data) => !cancelled && setState({ data, error: null, loading: false }))
      .catch((error) => !cancelled && setState((s) => ({ data: s.data, error: error.message, loading: false })))
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reloadKey, tick])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { ...state, reload }
}

/** Llama a reload() cada `ms` mientras `active` sea verdadero (por ejemplo, un trabajo en proceso). */
export function usePolling(reload, active, ms = 3000) {
  useEffect(() => {
    if (!active) return
    const timer = setInterval(reload, ms)
    return () => clearInterval(timer)
  }, [reload, active, ms])
}

/** Ruta a partir del hash: #/documentos/<id> → { section: 'documentos', id }. Permite enlaces directos. */
function parseHash() {
  const [section = 'inicio', id = null] = window.location.hash.replace(/^#\/?/, '').split('/').filter(Boolean)
  return { section, id }
}

export function useRoute() {
  const [route, setRoute] = useState(parseHash)
  useEffect(() => {
    const onChange = () => {
      setRoute(parseHash())
      window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return route
}

export function href(section, id) {
  return id ? `#/${section}/${id}` : `#/${section}`
}

/** URL local (blob) del archivo original de un documento: se descarga con la sesión. */
export function useDocumentImage(id) {
  const [state, setState] = useState({ url: null, type: null, error: null })
  useEffect(() => {
    let url = null
    let cancelled = false
    setState({ url: null, type: null, error: null })
    api.documents
      .image(id)
      .then((blob) => {
        if (cancelled) return
        url = URL.createObjectURL(blob)
        setState({ url, type: blob.type, error: null })
      })
      .catch((error) => !cancelled && setState({ url: null, type: null, error: error.message }))
    return () => {
      cancelled = true
      if (url) URL.revokeObjectURL(url)
    }
  }, [id])
  return state
}
