import { VeriqSymbol } from '../components/Brand'
import Icon from '../components/icons'
import { PublicFooter, PublicHeader, publicNavClass } from '../components/PublicLayout'
import { Reveal, SectionHeading } from '../components/Reveal'
import { href } from '../hooks'

/** Lo que guía cada decisión del producto. */
const PRINCIPLES = [
  ['Nada inventado', 'Lo que no se puede leer queda vacío y marcado. Preferimos un dato pendiente a un dato falso.'],
  ['Personas donde importan', 'La IA resuelve lo claro; lo dudoso lo decide alguien de tu equipo, y queda registrado quién y cuándo.'],
  ['Reglas a la vista', 'Cada documento termina en un estado que se explica. Nada de cajas negras.'],
  ['Costos transparentes', 'El costo de la IA por documento se ve en las métricas, día a día.'],
]

const STEPS = [
  ['calendar', 'Conversamos', 'Una cita para conocer tus documentos y cómo los procesa hoy tu equipo.'],
  ['layers', 'Adaptamos el agente', 'Veriq se ajusta a los tipos de documento de tu empresa, sin importar su dificultad.'],
  ['checkCircle', 'Verificas con tu equipo', 'Tu equipo sube, revisa lo dudoso y sigue los resultados desde el primer lote.'],
]

/** Página pública: quiénes somos, qué buscamos y cómo trabajamos con cada empresa. */
export default function About() {
  return (
    <div className="min-h-dvh bg-canvas">
      <PublicHeader
        nav={
          <>
            <a href={href('')} className={publicNavClass}>
              Producto
            </a>
            <a href={href('nosotros')} aria-current="page" className={publicNavClass}>
              Sobre nosotros
            </a>
          </>
        }
      />

      <main>
        {/* Portada */}
        <section className="relative overflow-hidden">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-y-0 right-0 hidden w-1/2 lg:block"
            style={{
              background:
                'linear-gradient(-56deg, transparent 0 34%, var(--color-brand-25) 34% 54%, transparent 54% 60%, var(--color-brand-50) 60% 70%, transparent 70%)',
            }}
          />
          <div className="relative mx-auto max-w-[1200px] px-5 pt-16 pb-20 sm:px-8 lg:pt-24 lg:pb-28">
            <p
              className="animate-enter text-[12px] font-semibold tracking-[0.1em] text-brand-600 uppercase [animation-fill-mode:backwards]"
              style={{ animationDuration: '420ms' }}
            >
              Sobre nosotros
            </p>
            <h1
              className="mt-4 max-w-3xl animate-enter text-[38px] leading-[1.05] font-semibold tracking-[-0.04em] text-balance text-ink [animation-fill-mode:backwards] sm:text-[52px] lg:text-[58px]"
              style={{ animationDelay: '60ms', animationDuration: '420ms' }}
            >
              Que verificar documentos deje de ser trabajo manual.
            </h1>
            <p
              className="mt-6 max-w-2xl animate-enter text-[17px] leading-relaxed text-muted [animation-fill-mode:backwards]"
              style={{ animationDelay: '120ms', animationDuration: '420ms' }}
            >
              Veriq existe para un problema concreto: equipos que pasan horas leyendo facturas y documentos comerciales,
              copiando sus datos y comprobando que cuadren. Lo resolvemos con IA, reglas claras y personas donde hacen
              falta.
            </p>
          </div>
        </section>

        {/* Misión */}
        <section className="relative overflow-hidden bg-brand-950 py-20 text-white sm:py-28">
          <div aria-hidden="true" className="v-hatch absolute inset-0" />
          <div aria-hidden="true" className="absolute -right-32 -bottom-40 h-[480px] w-[480px] rounded-full bg-brand-600/25 blur-3xl" />
          <Reveal className="relative mx-auto max-w-[1200px] px-5 sm:px-8">
            <span className="inline-flex h-12 w-12 items-center justify-center rounded-[12px] bg-white shadow-pop">
              <VeriqSymbol height={17} />
            </span>
            <p className="mt-8 text-[12px] font-semibold tracking-[0.1em] text-brand-300 uppercase">Nuestra misión</p>
            <p className="mt-4 max-w-4xl text-[28px] leading-[1.2] font-semibold tracking-[-0.03em] text-balance sm:text-[40px]">
              Que cada dato que entra a tu empresa desde un documento sea correcto, y que sepas por qué lo es.
            </p>
          </Reveal>
        </section>

        {/* Experiencia */}
        <section className="py-20 sm:py-28">
          <div className="mx-auto grid max-w-[1200px] gap-12 px-5 sm:px-8 lg:grid-cols-[minmax(0,6fr)_minmax(0,5fr)] lg:items-center lg:gap-20">
            <div>
              <SectionHeading eyebrow="Experiencia" title="Lo construimos porque lo vivimos.">
                Veriq lo crearon dos jóvenes que, durante sus días como estudiantes, trabajaron como capturadores de datos
                en una empresa local. Documento a documento, aprendieron cómo es ese flujo de trabajo desde adentro.
              </SectionHeading>
              <Reveal delay={80} as="p" className="mt-5 max-w-2xl text-[16px] leading-relaxed text-muted">
                Por eso sabemos y entendemos el dolor de las empresas que necesitan sistemas eficientes y una entrega de
                calidad de sus documentos.
              </Reveal>
            </div>

            <Reveal delay={120} className="relative isolate">
              <div
                aria-hidden="true"
                className="absolute -inset-3 -z-10 rounded-[24px] sm:-inset-5"
                style={{
                  background:
                    'linear-gradient(-56deg, var(--color-brand-25) 0 40%, var(--color-brand-50) 40% 58%, var(--color-brand-25) 58%)',
                }}
              />
              <figure className="rounded-[18px] border border-line bg-canvas p-7 shadow-pop sm:p-9">
                <VeriqSymbol height={18} />
                <blockquote className="mt-6 text-[21px] leading-[1.35] font-semibold tracking-[-0.02em] text-balance text-ink sm:text-[24px]">
                  “Sabemos lo que es capturar un documento a mano, porque lo hicimos.”
                </blockquote>
                <figcaption className="mt-6 flex items-center gap-3 border-t border-line pt-5">
                  <span aria-hidden="true" className="flex -space-x-2">
                    <span className="h-8 w-8 rounded-full bg-brand-950 ring-2 ring-canvas" />
                    <span className="h-8 w-8 rounded-full bg-brand-600 ring-2 ring-canvas" />
                  </span>
                  <span className="text-[13px] leading-snug text-muted">
                    <span className="block font-medium text-ink">Los fundadores de Veriq</span>
                    Excapturadores de datos
                  </span>
                </figcaption>
              </figure>
            </Reveal>
          </div>
        </section>

        {/* Principios */}
        <section className="border-t border-line py-20 sm:py-28">
          <div className="mx-auto max-w-[1200px] px-5 sm:px-8">
            <SectionHeading eyebrow="Principios" title="Cómo pensamos el producto." />
            <ol className="mt-14 grid gap-x-16 border-t border-line md:grid-cols-2">
              {PRINCIPLES.map(([title, text], i) => (
                <Reveal as="li" key={title} delay={(i % 2) * 60} className="flex gap-6 border-b border-line py-8">
                  <span className="font-mono text-sm text-brand-600 tabular">0{i + 1}</span>
                  <div>
                    <h3 className="text-[19px] font-semibold tracking-[-0.02em] text-ink">{title}</h3>
                    <p className="mt-2 text-[15px] leading-relaxed text-muted">{text}</p>
                  </div>
                </Reveal>
              ))}
            </ol>
          </div>
        </section>

        {/* Cómo trabajamos */}
        <section className="border-t border-line bg-surface py-20 sm:py-28">
          <div className="mx-auto max-w-[1200px] px-5 sm:px-8">
            <SectionHeading eyebrow="Cómo trabajamos" title="Cada empresa tiene sus documentos. Empezamos por conocerlos.">
              No todas las empresas tienen las mismas necesidades, así que Veriq no llega con una plantilla fija.
            </SectionHeading>
            <ol className="mt-14 grid gap-px overflow-hidden rounded-card border border-line bg-line md:grid-cols-3">
              {STEPS.map(([icon, title, text], i) => (
                <Reveal as="li" key={title} delay={i * 60} className="bg-canvas p-6 sm:p-8">
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

        {/* Cierre */}
        <section className="px-5 py-20 sm:px-8 sm:py-28">
          <Reveal className="mx-auto flex max-w-[1200px] flex-col items-start justify-between gap-8 rounded-[20px] border border-brand-200 bg-brand-25 px-6 py-12 sm:px-12 md:flex-row md:items-center">
            <div>
              <h2 className="text-[28px] leading-[1.15] font-semibold tracking-[-0.03em] text-balance text-ink sm:text-[34px]">
                Conozcámonos.
              </h2>
              <p className="mt-2 max-w-md text-[16px] leading-relaxed text-muted">
                Cuéntanos qué documentos maneja tu empresa y te mostramos cómo Veriq los verifica.
              </p>
            </div>
            <a
              href={href('cita')}
              className="inline-flex h-12 shrink-0 items-center gap-2 rounded-control bg-brand-600 px-6 text-[15px] font-medium text-white shadow-brand transition-[background-color,transform] duration-150 ease-out hover:bg-brand-700 active:scale-[0.97]"
            >
              Agendar una cita
              <Icon name="calendar" size={17} />
            </a>
          </Reveal>
        </section>
      </main>

      <PublicFooter />
    </div>
  )
}
