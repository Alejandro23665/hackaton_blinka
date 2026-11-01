import { useEffect, useRef, useState } from 'react'

/** Aparece una sola vez al entrar en pantalla (opacidad y un leve desplazamiento). */
export function Reveal({ children, className = '', delay = 0, as: Tag = 'div' }) {
  const ref = useRef(null)
  const [shown, setShown] = useState(() => typeof IntersectionObserver === 'undefined')
  useEffect(() => {
    if (shown) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return
        setShown(true)
        observer.disconnect()
      },
      { rootMargin: '0px 0px -80px 0px' },
    )
    observer.observe(ref.current)
    return () => observer.disconnect()
  }, [shown])
  return (
    <Tag
      ref={ref}
      data-shown={shown}
      style={{ transitionDelay: `${delay}ms` }}
      className={`transition-[opacity,transform] duration-500 ease-out ${
        shown ? 'translate-y-0 opacity-100' : 'translate-y-3 opacity-0'
      } ${className}`}
    >
      {children}
    </Tag>
  )
}

export function SectionHeading({ eyebrow, title, children, dark = false, className = '' }) {
  return (
    <Reveal className={`max-w-2xl ${className}`}>
      <p className={`text-[12px] font-semibold tracking-[0.1em] uppercase ${dark ? 'text-brand-300' : 'text-brand-600'}`}>
        {eyebrow}
      </p>
      <h2
        className={`mt-3 text-[30px] leading-[1.12] font-semibold tracking-[-0.03em] text-balance sm:text-[38px] ${
          dark ? 'text-white' : 'text-ink'
        }`}
      >
        {title}
      </h2>
      {children && <p className={`mt-4 text-[16px] leading-relaxed ${dark ? 'text-white/70' : 'text-muted'}`}>{children}</p>}
    </Reveal>
  )
}
