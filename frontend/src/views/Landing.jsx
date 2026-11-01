import { VeriqSymbol } from '../components/Brand'
import { PublicFooter, PublicHeader, publicNavClass } from '../components/PublicLayout'
import { Reveal, SectionHeading } from '../components/Reveal'
import Icon from '../components/icons'
import { ReviewFlag, StatusBadge, Tag } from '../components/ui'
import { href } from '../hooks'

const APPOINTMENT = href('cita')

/** Las secciones se recorren con scroll (no con #ancla: el hash es la ruta de la app). */
function scrollToSection(id) {
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  document.getElementById(id)?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' })
}

/* ---------- Encabezado ---------- */

const NAV = [
  ['como-funciona', 'Cómo funciona'],
  ['beneficios', 'Beneficios'],
  ['precios', 'Precios'],
]

function Header() {
  return (
    <PublicHeader
      nav={
        <>
          {NAV.map(([id, label]) => (
            <button key={id} type="button" onClick={() => scrollToSection(id)} className={publicNavClass}>
              {label}
            </button>
          ))}
          <a href={href('nosotros')} className={publicNavClass}>
            Sobre nosotros
          </a>
        </>
      }
    />
  )
}

/* ---------- Portada ---------- */

/** Las comprobaciones que hace Veriq con cada documento, en el orden en que ocurren. */
const CHECKS = [
  ['layers', 'Tipo de documento', 'Clasificado'],
  ['copy', 'Dos lecturas independientes', 'Coinciden'],
  ['list', 'Datos obligatorios', 'Completos'],
  ['notEqual', 'Importes frente al total', 'Coherentes'],
]

/** Esquema del producto: un documento y lo que Veriq comprueba de él (sin datos de ejemplo). */
function HeroVisual() {
  return (
    <div className="relative mx-auto w-full max-w-[520px] lg:mx-0" aria-hidden="true">
      {/* Hoja del documento */}
      <div className="relative ml-auto w-[78%] rotate-[-2deg] rounded-[10px] border border-line bg-canvas p-5 shadow-pop">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-2">
            <div className="h-2.5 w-24 rounded-full bg-surface-strong" />
            <div className="h-2 w-36 rounded-full bg-surface" />
            <div className="h-2 w-28 rounded-full bg-surface" />
          </div>
          <div className="rounded-md border-2 border-brand-600/70 px-3 py-2 text-center">
            <div className="mx-auto h-1.5 w-14 rounded-full bg-brand-200" />
            <p className="mt-1.5 font-mono text-[9px] font-medium tracking-wider text-brand-700">FACTURA</p>
            <div className="mx-auto mt-1.5 h-1.5 w-10 rounded-full bg-brand-200" />
          </div>
        </div>
        <div className="mt-6 space-y-2.5">
          {[100, 92, 96, 88, 94, 70].map((w, i) => (
            <div key={i} className="flex gap-3">
              <div className="h-2 rounded-full bg-surface" style={{ width: `${w * 0.55}%` }} />
              <div className="h-2 flex-1 rounded-full bg-surface" />
            </div>
          ))}
        </div>
        <div className="mt-6 ml-auto w-1/2 space-y-2 border-t border-dashed border-line-strong pt-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="flex justify-between">
              <div className="h-2 w-10 rounded-full bg-surface-strong" />
              <div className="h-2 w-14 rounded-full bg-surface-strong" />
            </div>
          ))}
        </div>
      </div>

      {/* Panel de verificación */}
      <div className="relative -mt-40 w-[94%] rounded-card sm:w-[82%] border border-line bg-canvas/95 p-4 shadow-pop backdrop-blur-md sm:-mt-44 sm:p-5">
        <div className="flex items-center gap-2.5 border-b border-line pb-3">
          <VeriqSymbol height={14} />
          <p className="text-[13px] font-semibold text-ink">Verificación</p>
          <span className="ml-auto inline-flex items-center gap-1.5 text-[11.5px] text-subtle">
            <span className="h-1.5 w-1.5 rounded-full bg-success-600" />
            automática
          </span>
        </div>
        <ul className="mt-2">
          {CHECKS.map(([icon, label, result], i) => (
            <li
              key={label}
              className="flex animate-enter items-center gap-3 py-2 [animation-fill-mode:backwards]"
              style={{ animationDelay: `${450 + i * 120}ms`, animationDuration: '420ms' }}
            >
              <span className="flex h-7 w-7 items-center justify-center rounded-md bg-surface text-subtle">
                <Icon name={icon} size={14} />
              </span>
              <span className="min-w-0 flex-1 text-[13px] leading-snug text-ink">{label}</span>
              <span className="inline-flex shrink-0 items-center gap-1 text-[12px] font-medium text-success-700">
                <Icon name="check" size={13} strokeWidth={2.4} />
                {result}
              </span>
            </li>
          ))}
        </ul>
        <div
          className="mt-2 flex animate-enter items-center justify-between rounded-control bg-surface/70 px-3 py-2.5 [animation-fill-mode:backwards]"
          style={{ animationDelay: '950ms', animationDuration: '420ms' }}
        >
          <span className="text-[12px] text-muted">Resultado</span>
          <StatusBadge status="LEGIBLE" size="sm" />
        </div>
      </div>

      {/* Lo dudoso va a una persona */}
      <div
        className="absolute right-0 -bottom-5 flex animate-enter items-center gap-2 rounded-control border border-line bg-canvas px-3 py-2 shadow-pop [animation-fill-mode:backwards] sm:-right-4"
        style={{ animationDelay: '1150ms', animationDuration: '420ms' }}
      >
        <Tag tone="warning" icon="eyeOff">
          Con dudas
        </Tag>
        <Icon name="arrowLeft" size={14} className="rotate-180 text-subtle" />
        <ReviewFlag size="sm" label="A revisión" />
      </div>
    </div>
  )
}

function Hero() {
  return (
    <section className="relative overflow-hidden">
      {/* Bandas diagonales con el ángulo de la V, muy tenues */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-y-0 right-0 hidden w-[55%] lg:block"
        style={{
          background:
            'linear-gradient(-56deg, transparent 0 30%, var(--color-brand-25) 30% 52%, transparent 52% 58%, var(--color-brand-50) 58% 72%, transparent 72%)',
        }}
      />
      <div className="relative mx-auto grid max-w-[1200px] items-center gap-14 px-5 pt-14 pb-20 sm:px-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:pt-24 lg:pb-28">
        <div>
          <p
            className="inline-flex animate-enter items-center gap-2 rounded-full border border-brand-200 bg-brand-25 py-1 pr-3 pl-1.5 text-[12.5px] font-medium text-brand-700 [animation-fill-mode:backwards]"
            style={{ animationDuration: '420ms' }}
          >
            <span className="rounded-full bg-brand-600 px-2 py-0.5 text-[11px] text-white">IA</span>
            Verificación documental
          </p>
          <h1
            className="mt-6 animate-enter text-[40px] leading-[1.04] font-semibold tracking-[-0.04em] text-balance text-ink [animation-fill-mode:backwards] sm:text-[54px] lg:text-[60px]"
            style={{ animationDelay: '60ms', animationDuration: '420ms' }}
          >
            Cada documento, leído y <span className="text-brand-600">verificado</span>.
          </h1>
          <p
            className="mt-6 max-w-xl animate-enter text-[17px] leading-relaxed text-muted [animation-fill-mode:backwards]"
            style={{ animationDelay: '120ms', animationDuration: '420ms' }}
          >
            Veriq lee facturas y documentos comerciales, comprueba sus datos con reglas y solo le pide a una persona lo
            que de verdad necesita revisión.
          </p>
          <div
            className="mt-9 flex animate-enter flex-wrap gap-3 [animation-fill-mode:backwards]"
            style={{ animationDelay: '180ms', animationDuration: '420ms' }}
          >
            <a
              href={APPOINTMENT}
              className="inline-flex h-12 items-center gap-2 rounded-control bg-brand-600 px-5 text-[15px] font-medium text-white shadow-brand transition-[background-color,transform] duration-150 ease-out hover:bg-brand-700 active:scale-[0.97]"
            >
              Agendar una cita
              <Icon name="calendar" size={17} />
            </a>
            <button
              type="button"
              onClick={() => scrollToSection('como-funciona')}
              className="inline-flex h-12 items-center gap-2 rounded-control border border-line-strong bg-canvas px-5 text-[15px] font-medium text-ink shadow-control transition-[border-color,color,transform] duration-150 ease-out hover:border-brand-300 hover:text-brand-800 active:scale-[0.97]"
            >
              Ver cómo funciona
            </button>
          </div>
          <ul
            className="mt-10 flex animate-enter flex-wrap gap-x-6 gap-y-2 text-[13px] text-muted [animation-fill-mode:backwards]"
            style={{ animationDelay: '240ms', animationDuration: '420ms' }}
          >
            {['Imágenes y PDF de varias páginas', 'Carpetas completas', 'Trazabilidad de cada corrección'].map((item) => (
              <li key={item} className="inline-flex items-center gap-1.5">
                <Icon name="check" size={14} strokeWidth={2.2} className="text-brand-600" />
                {item}
              </li>
            ))}
          </ul>
        </div>
        <HeroVisual />
      </div>
    </section>
  )
}

/* ---------- Cómo funciona ---------- */

const STEPS = [
  ['upload', 'Sube', 'Imágenes o PDF de varias páginas: archivos sueltos o una carpeta completa, con sus subcarpetas.'],
  ['layers', 'Clasifica', 'Separa las páginas y reconoce el tipo de cada documento, aunque lleguen mezclados en un mismo archivo.'],
  ['copy', 'Lee dos veces', 'Dos lecturas independientes de cada documento. Si no coinciden, el dato queda marcado con dudas.'],
  ['shield', 'Verifica', 'Comprueba los datos obligatorios y la coherencia de los importes antes de guardar.'],
]

function HowItWorks() {
  return (
    <section id="como-funciona" className="scroll-mt-20 border-t border-line bg-surface py-20 sm:py-28">
      <div className="mx-auto max-w-[1200px] px-5 sm:px-8">
        <SectionHeading eyebrow="Cómo funciona" title="De la foto del documento a un dato en el que puedes confiar.">
          Un recorrido de agentes de IA y reglas de negocio. Mientras trabaja, ves en qué etapa está cada archivo.
        </SectionHeading>
        <ol className="mt-14 grid gap-px overflow-hidden rounded-card border border-line bg-line sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map(([icon, title, text], i) => (
            <Reveal as="li" key={title} delay={i * 60} className="relative bg-canvas p-6 sm:p-7">
              <div className="flex items-center justify-between">
                <span className="v-cut flex h-11 w-11 items-center justify-center rounded-[10px] bg-brand-50 text-brand-600 ring-1 ring-brand-600/15 ring-inset">
                  <Icon name={icon} size={20} />
                </span>
                <span className="font-mono text-xs text-subtle tabular">0{i + 1}</span>
              </div>
              <h3 className="mt-6 text-[17px] font-semibold tracking-[-0.01em] text-ink">{title}</h3>
              <p className="mt-2 text-[14px] leading-relaxed text-muted">{text}</p>
            </Reveal>
          ))}
        </ol>
      </div>
    </section>
  )
}

/* ---------- Beneficios ---------- */

const FORMATS = ['Fotos de celular', 'PDF de varias páginas', 'Documentos mezclados', 'Carpetas completas']

function Benefit({ icon, title, children, className = '', delay = 0, dark = false }) {
  return (
    <Reveal
      delay={delay}
      className={`group flex flex-col rounded-card p-6 sm:p-8 ${
        dark ? 'bg-brand-950 text-white shadow-pop' : 'border border-line bg-canvas shadow-card'
      } ${className}`}
    >
      <span
        className={`v-cut flex h-11 w-11 items-center justify-center rounded-[10px] ${
          dark ? 'bg-white/10 text-brand-200' : 'bg-brand-50 text-brand-600 ring-1 ring-brand-600/15 ring-inset'
        }`}
      >
        <Icon name={icon} size={20} />
      </span>
      <h3 className={`mt-6 text-[20px] font-semibold tracking-[-0.02em] ${dark ? 'text-white' : 'text-ink'}`}>{title}</h3>
      {children}
    </Reveal>
  )
}

function Benefits() {
  return (
    <section id="beneficios" className="scroll-mt-20 py-20 sm:py-28">
      <div className="mx-auto max-w-[1200px] px-5 sm:px-8">
        <SectionHeading eyebrow="Beneficios" title="Más documentos verificados, con menos esfuerzo y menos costo.">
          Lo que gana tu equipo desde el primer lote.
        </SectionHeading>

        <div className="mt-14 grid gap-4 lg:grid-cols-3 lg:grid-rows-[auto_auto] lg:gap-5">
          <Benefit icon="layers" title="Se adapta a tus documentos" className="lg:col-span-2">
            <p className="mt-2 max-w-xl text-[15px] leading-relaxed text-muted">
              El agente se adapta a los distintos tipos de documento de cada cliente, sin importar su dificultad: formatos
              propios, imágenes de mala calidad o varios documentos en un mismo archivo.
            </p>
            <ul className="mt-6 flex flex-wrap gap-2">
              {FORMATS.map((format) => (
                <li key={format} className="rounded-md bg-surface px-2.5 py-1 text-[13px] text-muted ring-1 ring-line ring-inset">
                  {format}
                </li>
              ))}
            </ul>
          </Benefit>

          <Benefit icon="bolt" title="Rapidez" dark delay={60} className="relative overflow-hidden lg:row-span-2">
            <div aria-hidden="true" className="v-hatch absolute inset-0" />
            <p className="relative mt-2 text-[15px] leading-relaxed text-white/70">
              Lo que a una persona le toma días, el modelo lo resuelve en minutos.
            </p>
            <div className="relative mt-auto pt-10">
              <p className="text-[64px] leading-none font-semibold tracking-[-0.05em] tabular sm:text-[76px]">500</p>
              <p className="mt-2 text-[15px] text-white/80">documentos verificados en 5 minutos, en promedio</p>
              <div className="mt-6 h-1.5 overflow-hidden rounded-full bg-white/10" aria-hidden="true">
                <div className="h-full w-full origin-left scale-x-0 rounded-full bg-brand-400 transition-transform delay-300 duration-[1600ms] ease-out group-data-[shown=true]:scale-x-100" />
              </div>
              <p className="mt-3 text-xs text-white/50">El tiempo depende del volumen y del tipo de documento.</p>
            </div>
          </Benefit>

          <Benefit icon="wallet" title="Económico" delay={120}>
            <p className="mt-2 text-[15px] leading-relaxed text-muted">
              Un costo bajo por documento, y siempre a la vista: las métricas muestran cuánto cuesta la IA por cada
              documento leído.
            </p>
          </Benefit>

          <Benefit icon="checkCircle" title="Calidad" delay={180}>
            <p className="mt-2 text-[15px] leading-relaxed text-muted">
              Hay revisión humana: lo dudoso lo confirma una persona antes de darse por bueno, y cada corrección queda
              registrada.
            </p>
          </Benefit>
        </div>
      </div>
    </section>
  )
}

/* ---------- Efectividad ---------- */

/** Medido el 1 nov 2026: 390 documentos de una tanda real comparados con la referencia del cliente
 * (tipo, emisor y número en el nombre de cada archivo) y 58 muestras revisadas campo a campo
 * (backend/app/evaluation, corrida «landing»). */
const RESULTS = [
  { value: 96, label: 'Documentos clasificados correctamente' },
  { value: 94, label: 'Datos clave leídos correctamente' },
  { value: 95, label: 'Todos los datos, incluidos montos y fechas' },
]

function Effectiveness() {
  return (
    <section id="efectividad" className="scroll-mt-20 border-t border-line py-20 sm:py-28">
      <div className="mx-auto max-w-[1200px] px-5 sm:px-8">
        <SectionHeading eyebrow="Efectividad" title="Resultados medidos con documentos reales.">
          Comparamos lo que leyeron los agentes con la referencia del cliente y con respuestas revisadas por una persona.
        </SectionHeading>

        <ul className="mt-14 grid gap-px overflow-hidden rounded-card border border-line bg-line md:grid-cols-3">
          {RESULTS.map((r, i) => (
            <Reveal as="li" key={r.label} delay={i * 80} className="group bg-canvas p-6 sm:p-8">
              <p className="flex items-baseline gap-1 text-ink">
                <span className="text-[56px] leading-none font-semibold tracking-[-0.05em] tabular sm:text-[64px]">{r.value}</span>
                <span className="text-[24px] font-semibold text-brand-600">%</span>
              </p>
              <div className="mt-5 h-1.5 overflow-hidden rounded-full bg-surface" aria-hidden="true">
                <div
                  className="h-full origin-left scale-x-0 rounded-full bg-brand-600 transition-transform delay-200 duration-[1200ms] ease-out group-data-[shown=true]:scale-x-100"
                  style={{ width: `${r.value}%` }}
                />
              </div>
              <p className="mt-5 text-[16px] font-semibold tracking-[-0.01em] text-ink">{r.label}</p>
            </Reveal>
          ))}
        </ul>

      </div>
    </section>
  )
}

/* ---------- Verificación ---------- */

const RULES = [
  ['list', 'Datos obligatorios por tipo', 'Cada tipo de documento tiene los datos que debe traer. Si falta uno, se marca.'],
  ['copy', 'Doble lectura', 'Dos lecturas independientes de cada dato. Si no coinciden, queda marcado con dudas.'],
  ['notEqual', 'Totales coherentes', 'Los importes del documento se comprueban contra su total antes de guardarlo.'],
  ['layers', 'Sin duplicados', 'Un documento que ya está guardado no se registra dos veces.'],
  ['eyeOff', 'Nada inventado', 'Lo que no se puede leer queda vacío y marcado, nunca se rellena con una suposición.'],
]

const STATES = [
  ['LEGIBLE', 'Datos completos y verificados. No necesita a nadie.'],
  ['NO_LEGIBLE', 'Falta un dato o no fue fiable. Se guarda con los campos marcados.'],
]

function Verification() {
  return (
    <section id="verificacion" className="scroll-mt-20 border-t border-line py-20 sm:py-28">
      <div className="mx-auto grid max-w-[1200px] gap-14 px-5 sm:px-8 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-20">
        <div className="lg:sticky lg:top-28 lg:self-start">
          <SectionHeading eyebrow="Verificación" title="Reglas claras, no cajas negras.">
            La IA lee; las reglas deciden. Cada documento termina en un estado que se entiende de un vistazo, también sin
            depender del color.
          </SectionHeading>
          <Reveal delay={80} className="mt-8 rounded-card border border-line bg-canvas p-5 shadow-card">
            <ul className="space-y-3.5">
              {STATES.map(([status, text]) => (
                <li key={status} className="grid grid-cols-[7.5rem_minmax(0,1fr)] items-start gap-3">
                  <span>
                    <StatusBadge status={status} size="sm" />
                  </span>
                  <span className="text-[13px] leading-relaxed text-muted">{text}</span>
                </li>
              ))}
              <li className="grid grid-cols-[7.5rem_minmax(0,1fr)] items-start gap-3 border-t border-line pt-3.5">
                <span>
                  <ReviewFlag size="sm" label="Revisión" />
                </span>
                <span className="text-[13px] leading-relaxed text-muted">Aparte del estado: espera a una persona.</span>
              </li>
            </ul>
          </Reveal>
        </div>

        <ul className="divide-y divide-line border-y border-line">
          {RULES.map(([icon, title, text], i) => (
            <Reveal as="li" key={title} delay={i * 50} className="flex gap-5 py-7">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] bg-surface text-ink ring-1 ring-line ring-inset">
                <Icon name={icon} size={19} />
              </span>
              <span>
                <h3 className="text-[17px] font-semibold tracking-[-0.01em] text-ink">{title}</h3>
                <p className="mt-1.5 text-[15px] leading-relaxed text-muted">{text}</p>
              </span>
            </Reveal>
          ))}
        </ul>
      </div>
    </section>
  )
}

/* ---------- Revisión humana ---------- */

const QUEUE = [
  ['notEqual', 'Importes que no cuadran', 'Se leyeron todos y no coinciden con el total.'],
  ['help', 'Clasificación dudosa', 'El tipo de documento no quedó claro.'],
  ['layers', 'Documentos no reconocidos', 'Lo que no corresponde a ningún tipo conocido.'],
]

const REVIEW_TOOLS = [
  'El documento original al lado del formulario, con zoom',
  'Cada campo marcado: falta o con dudas',
  'Los valores más habituales de cada tipo, a un clic',
  'Lo ilegible se deja vacío; no se inventa',
  'Cada corrección queda a nombre de quien la hizo',
]

function Review() {
  return (
    <section id="revision" className="relative scroll-mt-20 overflow-hidden bg-brand-950 py-20 text-white sm:py-28">
      <div aria-hidden="true" className="v-hatch absolute inset-0" />
      <div aria-hidden="true" className="absolute -top-40 -left-32 h-[480px] w-[480px] rounded-full bg-brand-600/25 blur-3xl" />
      <div className="relative mx-auto max-w-[1200px] px-5 sm:px-8">
        <SectionHeading dark eyebrow="Revisión humana" title="La IA resuelve. Las personas deciden lo dudoso.">
          La revisión es selectiva: una imagen de mala calidad no basta para mandar un documento a la cola. Solo llega lo
          que necesita criterio.
        </SectionHeading>

        <div className="mt-14 grid gap-6 lg:grid-cols-2">
          <Reveal className="rounded-card border border-white/10 bg-white/[0.04] p-6 sm:p-8">
            <p className="text-[13px] font-medium text-white/60">Llega a la cola</p>
            <ul className="mt-5 space-y-5">
              {QUEUE.map(([icon, title, text]) => (
                <li key={title} className="flex gap-4">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[9px] bg-white/10 text-brand-200">
                    <Icon name={icon} size={18} />
                  </span>
                  <span>
                    <span className="block text-[15px] font-semibold">{title}</span>
                    <span className="block text-sm text-white/60">{text}</span>
                  </span>
                </li>
              ))}
            </ul>
            <p className="mt-7 border-t border-white/10 pt-5 text-sm text-white/60">
              Se atiende del más antiguo al más reciente. Al guardar, Veriq abre el siguiente pendiente.
            </p>
          </Reveal>
          <Reveal delay={80} className="rounded-card bg-canvas p-6 text-ink shadow-pop sm:p-8">
            <p className="text-[13px] font-medium text-muted">Corregir sin perder tiempo</p>
            <ul className="mt-5 divide-y divide-line">
              {REVIEW_TOOLS.map((item) => (
                <li key={item} className="flex items-start gap-3 py-3 text-[15px]">
                  <Icon name="check" size={17} strokeWidth={2.2} className="mt-0.5 text-brand-600" />
                  {item}
                </li>
              ))}
            </ul>
          </Reveal>
        </div>
      </div>
    </section>
  )
}

/* ---------- Equipos ---------- */

const TEAMS = [
  ['upload', 'Operaciones', 'Sube lotes de documentos y sigue el avance de cada archivo: etapa, documentos encontrados y resultado.'],
  ['shield', 'Auditoría', 'Cada documento conserva su archivo original y registra quién lo procesó o corrigió, y cuándo.'],
  ['chart', 'Supervisión', 'Métricas de uso de la IA, costo estimado por documento, campos que más fallan y rendimiento del sistema.'],
]

function Teams() {
  return (
    <section id="equipos" className="scroll-mt-20 py-20 sm:py-28">
      <div className="mx-auto max-w-[1200px] px-5 sm:px-8">
        <SectionHeading eyebrow="Equipos" title="Una sola fuente de verdad para quien opera, audita y supervisa.">
          Perfiles con roles: cada persona entra con su cuenta y los administradores gestionan los accesos.
        </SectionHeading>
        <div className="mt-14 grid gap-10 md:grid-cols-3 md:gap-0 md:divide-x md:divide-line">
          {TEAMS.map(([icon, title, text], i) => (
            <Reveal key={title} delay={i * 60} className="md:px-8 md:first:pl-0 md:last:pr-0">
              <Icon name={icon} size={22} className="text-brand-600" />
              <h3 className="mt-5 text-[19px] font-semibold tracking-[-0.02em] text-ink">{title}</h3>
              <p className="mt-2 text-[15px] leading-relaxed text-muted">{text}</p>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ---------- Precios ---------- */

/** Lo que trae cualquier plan. */
const INCLUDED = [
  'Doble lectura y reglas de verificación',
  'Cola de revisión humana',
  'Documento original junto a cada dato',
  'Métricas de uso y costo',
]

const PLANS = [
  {
    name: 'Inicial',
    price: 'US$149',
    docs: '2.000 documentos al mes',
    unit: '≈ US$0,075 por documento',
    extra: 'Documento adicional: US$0,08',
    hint: 'Para equipos que empiezan a dejar la captura manual.',
  },
  {
    name: 'Empresa',
    price: 'US$499',
    docs: '10.000 documentos al mes',
    unit: '≈ US$0,05 por documento',
    extra: 'Documento adicional: US$0,05',
    hint: 'Para operaciones con volumen diario de documentos.',
    featured: true,
  },
  {
    name: 'Corporativo',
    price: 'Adaptativo',
    custom: true, // precio a medida: sin «/ mes»
    docs: '50.000 documentos o más al mes',
    unit: 'Se ajusta a tu volumen y a tus necesidades',
    extra: 'Integraciones y nivel de servicio a convenir',
    hint: 'Para grupos con varias sedes o centros de distribución.',
  },
]

const EXTRAS = [
  ['layers', 'Adaptación inicial', 'US$65, pago único', 'Ajustamos el agente a los tipos de documento de tu empresa.'],
  ['sparkles', 'Piloto', '500 documentos sin costo', 'Pruébalo con tus propios documentos antes de decidir.'],
  ['user', 'Revisión gestionada', 'US$0,10 – 0,15 por documento revisado', 'Nuestro equipo hace la revisión humana por ti.'],
]

function Pricing() {
  return (
    <section id="precios" className="scroll-mt-20 border-t border-line bg-surface py-20 sm:py-28">
      <div className="mx-auto max-w-[1200px] px-5 sm:px-8">
        <SectionHeading eyebrow="Precios" title="Pagas por documento, sin sorpresas.">
          Planes mensuales con documentos incluidos. Mientras más documentos, menor el costo por documento.
        </SectionHeading>

        <div className="mt-14 grid gap-4 lg:grid-cols-3 lg:items-stretch lg:gap-5">
          {PLANS.map((plan, i) => (
            <Reveal
              key={plan.name}
              delay={i * 60}
              className={`relative flex flex-col rounded-card p-6 sm:p-8 ${
                plan.featured
                  ? 'bg-brand-950 text-white shadow-pop'
                  : 'border border-line bg-canvas text-ink shadow-card'
              }`}
            >
              {plan.featured && <div aria-hidden="true" className="v-hatch pointer-events-none absolute inset-0 rounded-card" />}
              <div className="relative flex items-center justify-between gap-3">
                <h3 className="text-[17px] font-semibold">{plan.name}</h3>
                {plan.featured && (
                  <span className="rounded-md bg-white/10 px-2 py-0.5 text-[11.5px] font-medium text-brand-200">Recomendado</span>
                )}
              </div>
              <p className={`relative mt-1 text-[13px] ${plan.featured ? 'text-white/65' : 'text-muted'}`}>{plan.hint}</p>
              <p className="relative mt-7 flex items-baseline gap-1.5">
                <span className="text-[38px] leading-none font-semibold tracking-[-0.04em] tabular">{plan.price}</span>
                {!plan.custom && <span className={`text-sm ${plan.featured ? 'text-white/60' : 'text-subtle'}`}>/ mes</span>}
              </p>
              <p className={`relative mt-2 text-sm font-medium ${plan.featured ? 'text-brand-200' : 'text-brand-700'}`}>{plan.unit}</p>
              <ul className={`relative mt-6 space-y-2.5 border-t pt-6 text-[14px] ${plan.featured ? 'border-white/15' : 'border-line'}`}>
                <li className="flex gap-2.5 font-medium">
                  <Icon name="file" size={16} className={`mt-0.5 ${plan.featured ? 'text-brand-200' : 'text-brand-600'}`} />
                  {plan.docs}
                </li>
                <li className={`flex gap-2.5 ${plan.featured ? 'text-white/75' : 'text-muted'}`}>
                  <Icon name="plus" size={16} className={`mt-0.5 ${plan.featured ? 'text-brand-200' : 'text-brand-600'}`} />
                  {plan.extra}
                </li>
              </ul>
              <p className={`relative mt-6 flex gap-2 text-xs leading-relaxed ${plan.featured ? 'text-white/60' : 'text-subtle'}`}>
                <Icon name="help" size={14} className="mt-px shrink-0" />
                El precio puede variar según las necesidades del cliente y el volumen de documentos.
              </p>
              <a
                href={APPOINTMENT}
                className={`relative mt-6 inline-flex h-11 items-center justify-center gap-2 rounded-control text-sm font-medium transition-[background-color,border-color,transform] duration-150 ease-out active:scale-[0.97] lg:mt-auto ${
                  plan.featured
                    ? 'bg-white text-brand-950 hover:bg-brand-50'
                    : 'border border-line-strong bg-canvas text-ink shadow-control hover:border-brand-300 hover:text-brand-800'
                }`}
              >
                Agendar una cita
              </a>
            </Reveal>
          ))}
        </div>

        <Reveal className="mt-5 rounded-card border border-line bg-canvas p-6 sm:p-8">
          <p className="text-[13px] font-medium text-muted">Todos los planes incluyen</p>
          <ul className="mt-4 grid gap-x-6 gap-y-2.5 text-[14px] text-ink sm:grid-cols-2 lg:grid-cols-4">
            {INCLUDED.map((item) => (
              <li key={item} className="flex gap-2">
                <Icon name="check" size={16} strokeWidth={2.2} className="mt-0.5 shrink-0 text-brand-600" />
                {item}
              </li>
            ))}
          </ul>
        </Reveal>

        <ul className="mt-5 grid gap-4 md:grid-cols-3">
          {EXTRAS.map(([icon, title, price, text], i) => (
            <Reveal as="li" key={title} delay={i * 60} className="flex gap-4 rounded-card border border-dashed border-line-strong p-5">
              <span className="v-cut flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] bg-brand-50 text-brand-600 ring-1 ring-brand-600/15 ring-inset">
                <Icon name={icon} size={18} />
              </span>
              <div>
                <p className="text-[15px] font-semibold text-ink">{title}</p>
                <p className="text-sm font-medium text-brand-700 tabular">{price}</p>
                <p className="mt-1 text-[13px] leading-relaxed text-muted">{text}</p>
              </div>
            </Reveal>
          ))}
        </ul>

        <p className="mt-6 text-xs text-subtle">Precios en dólares estadounidenses. El volumen se cuenta por documento verificado.</p>
      </div>
    </section>
  )
}

/* ---------- Cierre ---------- */

function ClosingCta() {
  return (
    <section className="px-5 pb-20 sm:px-8 sm:pb-28">
      <Reveal className="relative mx-auto max-w-[1200px] overflow-hidden rounded-[20px] border border-brand-200 bg-brand-25 px-6 py-14 text-center sm:px-12 sm:py-20">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              'linear-gradient(-56deg, transparent 0 62%, var(--color-brand-50) 62% 74%, transparent 74% 78%, var(--color-brand-100) 78% 84%, transparent 84%)',
          }}
        />
        <div className="relative">
          <VeriqSymbol height={30} className="mx-auto" />
          <h2 className="mx-auto mt-7 max-w-xl text-[30px] leading-[1.12] font-semibold tracking-[-0.03em] text-balance text-ink sm:text-[40px]">
            Deja que la IA lea. Tú decides lo importante.
          </h2>
          <p className="mx-auto mt-4 max-w-md text-[16px] leading-relaxed text-muted">
            Agenda una cita: te mostramos cómo Veriq se adapta a los documentos de tu empresa.
          </p>
          <a
            href={APPOINTMENT}
            className="mt-9 inline-flex h-12 items-center gap-2 rounded-control bg-brand-600 px-6 text-[15px] font-medium text-white shadow-brand transition-[background-color,transform] duration-150 ease-out hover:bg-brand-700 active:scale-[0.97]"
          >
            Agendar una cita
            <Icon name="calendar" size={17} />
          </a>
        </div>
      </Reveal>
    </section>
  )
}

/** Página pública de Veriq: qué hace el producto y acceso al inicio de sesión. */
export default function Landing() {
  return (
    <div className="min-h-dvh bg-canvas">
      <Header />
      <main>
        <Hero />
        <HowItWorks />
        <Benefits />
        <Effectiveness />
        <Verification />
        <Review />
        <Teams />
        <Pricing />
        <ClosingCta />
      </main>
      <PublicFooter />
    </div>
  )
}
