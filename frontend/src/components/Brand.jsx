import symbol from '../assets/veriq-symbol.webp'

/** Proporción del símbolo oficial (ancho / alto), para no deformarlo nunca. */
const RATIO = 824 / 455

/** El símbolo de Veriq tal como lo entregó la marca (sin redibujar). */
export function VeriqSymbol({ height = 22, className = '' }) {
  return (
    <img
      src={symbol}
      alt=""
      aria-hidden="true"
      width={Math.round(height * RATIO)}
      height={height}
      className={`shrink-0 select-none ${className}`}
      draggable="false"
    />
  )
}

/** Símbolo + nombre del producto. */
export function Logo({ height = 22, className = '' }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <VeriqSymbol height={height} />
      <span className="text-[19px] leading-none font-semibold tracking-[-0.03em] text-brand-950">Veriq</span>
    </span>
  )
}
