import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
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

// --- Volver a una vista donde se dejó --------------------------------------------------------
// El estado de cada vista (filtros, búsqueda, página) y la posición de la página se guardan en la
// sesión del navegador: al volver a una vista (botón Atrás, "Volver" o la pestaña), se recuperan.

function readStored(key) {
  try {
    const raw = sessionStorage.getItem(key)
    return raw === null ? undefined : JSON.parse(raw)
  } catch {
    return undefined
  }
}

function writeStored(key, value) {
  try {
    sessionStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Sin almacenamiento (modo privado, cuota llena): la vista funciona igual, solo no se recuerda
  }
}

/** Como useState, pero el valor sobrevive al salir de la vista y volver a ella (durante la sesión). */
export function useViewState(key, initial) {
  const storageKey = `vista:${key}`
  const [value, setValue] = useState(() => {
    const stored = readStored(storageKey)
    return stored === undefined ? initial : stored
  })
  useEffect(() => writeStored(storageKey, value), [storageKey, value])
  return [value, setValue]
}

const scrollKey = (hash) => `scroll:${hash || '#/inicio'}`

/** Vuelve a la posición guardada de una lista. Los datos llegan después de mostrar la vista: se
 * reintenta hasta que la página sea lo bastante alta (o pase un momento). */
function restoreScroll(hash, id) {
  // Un detalle (documento, revisión) siempre empieza arriba
  const target = id ? 0 : (readStored(scrollKey(hash)) ?? 0)
  const started = performance.now()
  const attempt = () => {
    window.scrollTo(0, target)
    const reached = Math.abs(window.scrollY - target) < 2
    if (!reached && performance.now() - started < 1500) requestAnimationFrame(attempt)
  }
  attempt()
}

export function useRoute() {
  const [route, setRoute] = useState(parseHash)
  const current = useRef(window.location.hash)

  useEffect(() => {
    // La posición la maneja la app, no el navegador
    if ('scrollRestoration' in window.history) window.history.scrollRestoration = 'manual'
    const onScroll = () => writeStored(scrollKey(current.current), window.scrollY)
    const onChange = () => {
      current.current = window.location.hash
      setRoute(parseHash())
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('hashchange', onChange)
    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('hashchange', onChange)
    }
  }, [])

  // Tras mostrar la vista nueva, la posición donde se dejó
  useLayoutEffect(() => restoreScroll(current.current, route.id), [route])
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
